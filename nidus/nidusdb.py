#!/usr/bin/env python

""" nidusdb.py: interface to underlying nidus storage system

Provides a common interface and access methods from Nidus request handlers to the
underlying storage system, serving a two-fold service:
 1) remove necessity for request handler to 'understand' underlying storage system
    protocols
 2) allow for easier changes to storage system - NOTE: this file will have to be
    modified to fit the storage system
"""
__name__ = 'nidusdb'
__license__ = 'GPL'
__version__ = '0.1.2'
__date__ = 'January 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@hushmail.com'
__status__ = 'Development'

import os                                              # file paths
import time                                            # timestamps
import psycopg2 as psql                                # postgresql api
import ConfigParser                                    # config file
import threading                                       # sse threads
import Queue                                           # thread-safe queue
from dateutil import parser as dtparser                # parsing dates
import wraith.radio.radiotap as rtap                   # 802.11 layer 1 parsing
from wraith.radio import mpdu                          # 802.11 layer 2 parsing
from wraith.radio import mcs                           # 802.11 mcs fcts
from wraith.radio import channels                      # 802.11 channels
from wraith.radio.oui import parseoui,manufacturer     # oui functions
from wraith.nidus import nmp                           # message protocol
import wraith.nidus.simplepcap as pcap                 # pcap writing
from wraith import ts2iso                              # timestamp convesion

class NidusDBException(Exception): pass                          # generic exception
class NidusDBServerException(NidusDBException): pass             # no server/failed to connect
class NidusDBAuthException(NidusDBException): pass               # authentication failure
class NidusDBSubmitException(NidusDBException): pass             # submit failed
class NidusDBSubmitParseException(NidusDBSubmitException): pass  # submit failed due to parsing
class NidusDBSubmitParamException(NidusDBSubmitException): pass  # one or more params are invalid
class NidusDBInvalidFrameException(NidusDBSubmitException): pass # frame does not follow standard

#### SSE functionality

# Task Definitions

class SaveTask(tuple):
    # noinspection PyInitNewSignature
    def __new__(cls,ts,fid,sid,mac,frame,lr):
        """
         ts - timestamp
         fid - frame id
         sid - session id
         mac - capture source mac
         frame - actual frame
         lr - left/right offsets into layer 1 and layer 2
        """
        return super(SaveTask,cls).__new__(cls,tuple([ts,fid,sid,mac,frame,lr]))
    @property
    def ts(self): return self[0]
    @property
    def fid(self): return self[1]
    @property
    def sid(self): return self[2]
    @property
    def mac(self): return self[3]
    @property
    def frame(self): return self[4]
    @property
    def offsets(self): return self[5]

class StoreTask(tuple):
    # noinspection PyInitNewSignature
    def __new__(cls,fid,mac,l1,l2):
        """
         fid - frame id
         mac - capture source mac
         l1 - radiotap dict
         l2 - mpdu dict
        """
        return super(StoreTask,cls).__new__(cls,tuple([fid,mac,l1,l2]))
    @property
    def fid(self): return self[0]
    @property
    def mac(self): return self[1]
    @property
    def l1(self): return self[2]
    @property
    def l2(self): return self[3]

class ExtractTask(tuple):
    # noinspection PyInitNewSignature
    def __new__(cls,ts,fid,l2):
        """
         ts - timestamp
         fid - frame id
         l2 - MPDU dict
        """
        return super(ExtractTask,cls).__new__(cls,tuple([ts,fid,l2]))
    @property
    def ts(self): return self[0]
    @property
    def fid(self): return self[1]
    @property
    def l2(self): return self[2]

# Worker definitions

class SSEThread(threading.Thread):
    """ Super Class for a SaveStoreExtract worker thread """
    def __init__(self,tasks):
        """
         sid - current session id
         halt - stop event
         task - queue of tasks to pull from
        """
        threading.Thread.__init__(self)
        self._qT = tasks
        self._conn = None # connection to database
        self._err = None  # internal err information
        try:
            self._conn = psql.connect(host="localhost",dbname="nidus",
                                      user="nidus",password="nidus")
            curs = self._conn.cursor()
            curs.execute("set time zone 'UTC';")
            curs.close()
            self._conn.commit()
        except psql.OperationalError as e:
            if e.__str__().find('connect') > 0:
                raise NidusDBServerException("Postgresql not running")
            elif e.__str__().find('authentication') > 0:
                raise NidusDBAuthException("Invalid connection string")
            else:
                raise NidusDBException("Database failure: %s" % e)

    def run(self):
        """ processing loop - calls consume until told to stop """
        while True:
            item = self._qT.get()
            if item == '!STOP!': break
            try:
                self._consume(item)
            except NidusDBSubmitException as e:
                print "DB Error: ", e
            except Exception as e:
                print "Error: ", e
        self._clean() # cleanup

    def _clean(self):
        """ closes database and call _cleanup for any subthread closing taks """
        if self._conn and not self._conn.closed: self._conn.close()
        self._cleanup()

    # the following must be implemented by subclasses
    def _consume(self,item): raise NotImplementedError
    def _cleanup(self): raise NotImplementedError

class SaveThread(SSEThread):
    """ handles saving the frame in tasks queue to file """
    def __init__(self,tasks,path,private,sz):
        """
         path - directory to store pcaps in
         sz - max size of pcap file
        """
        SSEThread.__init__(self,tasks)
        self._path = path
        self._private = private
        self._sz = sz
        self._pkts = []
        self._fout = None

    def _cleanup(self):
        """ close file if it is open """
        # write any stored packets and close opened file
        try:
            if self._pkts: self._writepkts()
            if self._fout: self._fout.close()
        except:
            # blanket exception to catch everything on quit
            pass

    def _consume(self,item):
        """ write the packet in item to file """
        sid = item.sid
        mac = item.mac
        frame = item.frame
        (left,right) = item.offsets

        # save the packet as tuple (time,frameid,frame) for later writing
        if self._private and left < right: frame = frame[:left] + frame[right:]
        self._pkts.append((item.ts,item.fid,frame))

        # if there are (hardcoded: 20) number of stored frames, write them out
        if len(self._pkts) > 20:
            # close any open file exceeding specified size
            if self._fout and os.path.getsize(self._fout.name) > self._sz:
                self._fout.close()
                self._fout = None

            # if no file, open a new file (using ts from first pkt in name)
            if not self._fout:
                fname = os.path.join(self._path,
                                     "%d_%s_%s.pcap" % (sid,self._pkts[0][0],mac))
                try:
                    self._fout = pcap.pcapopen(fname)
                except pcap.PCAPException as e:
                    raise NidusDBSubmitException(e)

            self._writepkts()

    def _writepkts(self):
        """ write stored packets to file """
        curs = None
        try:
            # we'll catch db errors in the internal loop and attempt to
            # continue writing
            curs = self._conn.cursor()
            for pkt in self._pkts:
                sql = "insert into frame_path (fid,filepath) values (%s,%s);"
                try:
                    curs.execute(sql,(pkt[1],os.path.split(self._fout.name)[1]))
                except psql.Error as e:
                    print 'error writing frame_path', e
                    self._conn.rollback()
                else:
                    self._conn.commit()
                pcap.pktwrite(self._fout,pkt[0],pkt[2])
        except pcap.PCAPException:
            self._fout.close()
            self._fout = None
        finally:
            # make sure to reset packet list and close the cursor
            self._pkts = []
            curs.close()

class StoreThread(SSEThread):
    """ stores the frame details in the task queue to the db """
    def __init__(self,tasks,sid):
        """
         tasks - the tasks queue
         sid - session id
        """
        SSEThread.__init__(self,tasks)
        self._sid = sid

    def _cleanup(self): pass

    def _consume(self,item):
        # get our cursor & extract vars from item
        curs = self._conn.cursor()
        fid = item.fid
        rdo = item.mac
        dR = item.l1
        dM = item.l2

        # each _insert function will reraise psql related errors after
        # setting the internal err tuple
        try:
            # insert radiotap data
            if 'a-mpdu' in dR['present']: self._insertampdu(fid,dR,curs)
            self._insertsource(fid,rdo,dR,curs)
            self._insertsignal(fid,dR,curs)

            # insert mpdu data
            if dM.offset > 0:
                self._inserttraffic(fid,dM,curs)
                if dM.qosctrl: self._insertqos(fid,dM,curs)
                if dM.crypt: self._insertcrypt(fid,dM,curs)
        except psql.Error as e:
            self._conn.rollback()
            curs.close()
            raise NidusDBSubmitException(e.pgcode,e.pgerror,self._err[0],self._err[1])
        else:
            self._conn.commit()
        finally:
            curs.close()

    def _insertampdu(self,fid,r,curs):
        """
         insert ampdu from frame fid (as defined in radiotap r) in db using
         cursor curs
        """
        try:
            sql = "insert into ampdu fid,refnum,flags) values (%s,%s,%s);"
            curs.execute(sql,(fid,r['a-mpdu'][0],r['a-mpdu'][1]))
        except psql.Error:
            self._err = ('ampdu',fid)
            raise

    def _insertsource(self,fid,rdo,r,curs):
        """
         insert source from frame fid (as defined in radiotap r), collected by
         rdo in db using cursor curs
        """
        try:
            ant = r['antenna'] if 'antenna' in r else 0
            pwr = r['antsignal'] if 'antsignal' in r else 0
            sql = "insert into source (fid,src,antenna,rfpwr) values (%s,%s,%s,%s);"
            curs.execute(sql,(fid,rdo,ant,pwr))
        except psql.Error:
            self._err = ('source',fid)
            raise

    def _insertsignal(self,fid,r,curs):
        """
         insert signal record from frame fid (as defined in radiotap r) in db
         using cursors curs
        """
        try:
            # determine what standard, the data rate and any mcs fields
            # assuming channels will always be present in radiotap r
            try:
                std = 'n'
                mcsflags = rtap.mcsflags_params(r['mcs'][0],r['mcs'][1])
                if mcsflags['bw'] == rtap.MCS_BW_20: bw = '20'
                elif mcsflags['bw'] == rtap.MCS_BW_40: bw = '40'
                elif mcsflags['bw'] == rtap.MCS_BW_20L: bw = '20L'
                else: bw = '20U'
                width = 40 if bw == '40' else 20
                gi = 1 if 'gi' in mcsflags and mcsflags['gi'] > 0 else 0
                ht = 1 if 'ht' in mcsflags and mcsflags['ht'] > 0 else 0
                index = r['mcs'][2]
                rate = mcs.mcs_rate(r['mcs'][2],width,gi)
                hasMCS = 1
            except:
                if r['channel'][0] in channels.ISM_24_F2C:
                    if rtap.chflags_get(r['channel'][1],'cck'):
                        std = 'b'
                    else:
                        std = 'g'
                else:
                    std = 'a'
                rate = r['rate'] * 0.5 if 'rate' in r else 0
                bw = None
                gi = None
                ht = None
                index = None
                hasMCS = 0
            sql = """
                   insert into signal (fid,std,rate,channel,chflags,rf,ht,
                                       mcs_bw,mcs_gi,mcs_ht,mcs_index)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
                  """
            curs.execute(sql,(fid,std,rate,channels.f2c(r['channel'][0]),
                              r['channel'][1],r['channel'][0],hasMCS,bw,gi,
                              ht,index))
        except psql.Error:
            self._err = ('signal',fid)
            raise

    def _inserttraffic(self,fid,m,curs):
        """
         insert traffic from frame fid (defined in mpdu m) into db using
         cursor curs
        """
        try:
            # get out duration type and value
            dVal = None
            if m.duration['type'] == 'vcs': dVal = m.duration['dur']
            elif m.duration['type'] == 'aid': dVal = m.duration['aid']

            sql = """
                   insert into traffic (fid,type,subtype,td,fd,mf,rt,pm,md,pf,so,
                                        dur_type,dur_val,addr1,addr2,addr3,
                                        fragnum,seqnum,addr4,crypt)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                           %s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
                  """
            curs.execute(sql,(fid,mpdu.FT_TYPES[m.type],
                                  mpdu.subtypes(m.type,m.subtype),
                                  m.flags['td'],m.flags['fd'],
                                  m.flags['mf'],m.flags['r'],
                                  m.flags['pm'],m.flags['md'],
                                  m.flags['pf'],m.flags['o'],
                                  m.duration['type'],dVal,
                                  m.addr1,m.addr2,m.addr3,
                                  m.seqctrl['fragno'] if m.seqctrl else None,
                                  m.seqctrl['seqno'] if m.seqctrl else None,
                                  m.addr4,
                                  m.crypt['type'] if m.crypt else 'none',))
        except psql.Error:
            self._err = ('traffic',fid)
            raise

    def _insertqos(self,fid,m,curs):
        """
         inserts the qos ctrl from frame id (defined in mpdu m) into the db
         using cursor curs
        """
        try:
            sql = """
                   insert into qosctrl (fid,tid,eosp,ackpol,amsdu,txop)
                   values (%s,%s,%s,%s,%s,%s);
                  """
            curs.execute(sql,(fid,m.qosctrl['tid'],
                                  m.qosctrl['eosp'],
                                  m.qosctrl['ack-policy'],
                                  m.qosctrl['a-msdu'],
                                  m.qosctrl['txop']))
        except psql.Error:
            self._err = ('qosctrl',fid)
            raise

    def _insertcrypt(self,fid,m,curs):
        """
         insert the encryption scheme/data from frame fid (as defined in mpdu m)
         into the db using the cursor curs
        """
        try:
            if m.crypt['type'] == 'wep':
                sql = """
                       insert into wepcrypt (fid,iv,key_id,icv) values (%s,%s,%s,%s);
                      """
                curs.execute(sql,(fid,m.crypt['iv'],
                                      m.crypt['key-id'],
                                      m.crypt['icv']))
            elif m.crypt['type'] == 'tkip':
                sql = """
                       insert into tkipcrypt (fid,tsc1,wepseed,tsc0,key_id,
                                              tsc2,tsc3,tsc4,tsc5,mic,icv)
                       values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
                      """
                curs.execute(sql,(fid,m.crypt['iv']['tsc1'],
                                      m.crypt['iv']['wep-seed'],
                                      m.crypt['iv']['tsc0'],
                                      m.crypt['iv']['key-id']['key-id'],
                                      m.crypt['ext-iv']['tsc2'],
                                      m.crypt['ext-iv']['tsc3'],
                                      m.crypt['ext-iv']['tsc4'],
                                      m.crypt['ext-iv']['tsc5'],
                                      m.crypt['mic'],
                                      m.crypt['icv']))
            elif m.crypt['type'] == 'ccmp':
                sql = """
                       insert into ccmpcrypt (fid,pn0,pn1,key_id,pn2,
                                              pn3,pn4,pn5,mic)
                       values (%s,%s,%s,%s,%s,%s,%s,%s,%s);
                      """
                curs.execute(sql,(fid,m.crypt['pn0'],
                                      m.crypt['pn1'],
                                      m.crypt['key-id']['key-id'],
                                      m.crypt['pn2'],
                                      m.crypt['pn3'],
                                      m.crypt['pn4'],
                                      m.crypt['pn5'],
                                      m.crypt['mic']))
            else:
                # undefined crypt type
                pass
        except psql.Error:
            self._err = ('crypt',fid)
            raise

class ExtractThread(SSEThread):
    """  extracts & stores details of nets/stas etc from mpdus in tasks queue """
    def __init__(self,tasks,lSta,sid,oui):
        """
         lSta - lock on the stay dictionary
         sid - session id
         oui - oui dict
        """
        SSEThread.__init__(self,tasks)
        self._l = lSta
        self._sid = sid
        self._oui = oui

    def _cleanup(self): pass

    def _consume(self,item):
        # make a cursor and extract variables
        curs = self._conn.cursor()
        ts = item.ts
        fid = item.fid
        l2 = item.l2

        # sta addresses
        # Function To DS From DS Address 1 Address 2 Address 3 Address 4
        # IBSS/Intra   0    0        RA=DA     TA=SA     BSSID       N/A
        # From AP      0    1        RA=DA  TA=BSSID        SA       N/A
        # To AP        1    0     RA=BSSID     TA=SA        DA       N/A
        # Wireless DS  1    1     RA=BSSID  TA=BSSID     DA=WDS    SA=WDS

        # extract unique addresses of stas in the mpdu into the addr dict having
        # the form <hwaddr>->{'loc:[<i..n>],'id':<sta_id>} where i=1 through 4
        addrs = {}
        locations = ['addr1','addr2','addr3','addr4']
        for i in xrange(len(locations)):
            a = locations[i]
            if not a in l2: break         # no more stas to process
            if l2[a] in addrs:
                addrs[l2[a]]['loc'].append(i+1)
            else:
                addrs[l2[a]] = {'loc':[i+1],'id':None}
        saddrs = set(addrs.keys())
        if len(saddrs) != len(addrs.keys()):
            print 'consume', addrs

        # each _insert function will reraise psql related errors after
        # setting the internal err tuple
        try:
            # NOTE: 1) insertstas modifies the addrs dict in place, assigning
            # ids to each nonbroadcast address 2) insertstas also commits
            # the connection after each insert
            self._insertstas(fid,ts,addrs,curs)
        except psql.Error as e:
            self._conn.rollback()
            curs.close()
            raise NidusDBSubmitException(e.pgcode,e.pgerror,self._err[0],self._err[1])
        else:
            self._conn.commit()
        finally:
            curs.close()

    def _insertstas(self,fid,ts,addrs,curs):
        """
         given the frame id fid with timestamp ts and address dict of stas in
         the frame, inserts unique sta's and sta activity in db using the
         cursor curs
         NOTE: as a side-effect will insert the sta id for each non-broadcast
          address
        """
        #### ENTER sta CS
        try:
            # do not process broadcast addresses
            nonbroadcast = [addr for addr in addrs if addr != mpdu.BROADCAST]
            if nonbroadcast:
                sql = "select id, mac from sta where "
                sql += " or ".join(["mac=%s" for _ in nonbroadcast])
                sql += ';'

                self._l.acquire()

                # get all rows with current sta(s) & add sta id if it is not new
                curs.execute(sql,tuple(nonbroadcast))
                for row in curs.fetchall():
                    if row[1] in addrs: addrs[row[1]]['id'] = row[0]

                # for each address
                for addr in nonbroadcast:
                    # if this one doesnt have an id (not seen before) add it
                    if not addrs[addr]['id']:
                        # insert the new sta - commit the transaction because
                        # we we're experiencing duplicate key issues w/o commit
                        sql = """
                               insert into sta (sid,fid,spotted,mac,manuf)
                               values (%s,%s,%s,%s,%s) RETURNING id;
                              """
                        curs.execute(sql,(self._sid,fid,ts,addr,
                                          manufacturer(self._oui,addr)))
                        addrs[addr]['id'] = curs.fetchone()[0]
                        self._conn.commit()

                    # check sta activity, addr2 is transmitting
                    mode = 'tx' if 2 in addrs[addr]['loc'] else 'rx'
                    fs = ls = fh = lh = None
                    sql = """
                           select firstSeen,lastSeen,firstHeard,lastHeard
                           from sta_activity where sid=%s and staid=%s;
                          """
                    curs.execute(sql,(self._sid,addrs[addr]['id']))
                    row = curs.fetchone()

                    if row:
                        # NOTE: frame ts needs to be converted to a datetime
                        # object w/ tz info before being compared to db's ts

                        # sta has been seen this session
                        if mode == 'tx':
                            # check 'heard' activities
                            if not row[2]:
                                # 1st tx heard by sta, update first/lastHeard
                                fh = lh = ts
                            elif dtparser.parse(ts+"+00:00") > row[3]:
                                # tx is later than lastHeard, update it
                                lh = ts
                        else:
                            # check 'seen' activities
                            if not row[0]:
                                # 1st time sta seen, update first/lastSeen
                                fs = ls = ts
                            elif dtparser.parse(ts+"+00:00") > row[1]:
                                # ts is later than lastSeen, update it
                                ls = ts

                        # build query if there is something to update
                        # commit the transaction because we were experiencing
                        # duplicate key issues w/o commit
                        if fs or ls or fh or lh:
                            vs = []
                            us = ""
                            if fs:
                                us = " firstSeen=%s"
                                vs.append(fs)
                            if ls:
                                if not us: us = " lastSeen=%s"
                                else: us += ", lastSeen=%s"
                                vs.append(ls)
                            if fh:
                                if not us: us = " firstHeard=%s"
                                else: us += ", firstHeard=%s"
                                vs.append(fh)
                            if lh:
                                if not us: us = " lastHeard=%s"
                                else: us += ", lastHeard=%s"
                                vs.append(lh)
                            sql = "update sta_activity set"
                            sql += us
                            sql += " where sid=%s and staid=%s;"
                            curs.execute(sql,tuple(vs+[self._sid,addrs[addr]['id']]))
                            self._conn.commit()
                    else:
                        # sta has not been seen this session
                        # commit the transaction because we were experiencing
                        # duplicate key issues w/o commit
                        if mode == 'tx':
                            fh = lh = ts
                        else:
                            fs = ls = ts
                        sql = """
                               insert into sta_activity (sid,staid,
                                                         firstSeen,lastSeen,
                                                         firstHeard,lastHeard)
                               values (%s,%s,%s,%s,%s,%s);
                              """
                        curs.execute(sql,(self._sid,addrs[addr]['id'],fs,ls,fh,lh))
                        self._conn.commit()
        except psql.Error:
            # tag the error & reraise (letting the finally block release the lock)
            self._err = ('sta',fid)
            raise # reraise
        finally:
            self._l.release()
        #### EXIT CS

class NidusDB(object):
    """ NidusDB - interface to nidus database """
    def __init__(self,cpath=None):
        """ initialize NidusDB """
        self._conn = None           # connection to datastore
        self._curs = None           # cursor to datastore
        self._sid  = None           # session id for this sensor
        self._gid  = None           # gpsd id
        self._raw = {'store':False} # raw frame storage config
        self._oui = {}              # oui dict (oui->manufacturer)

        # SSE variables
        self._lSta = None           # lock on the stas
        self._qSave = {}            # one (or two) queues for each radio(s) saving
        self._tSave = {}            # one (or two) threads for each radio(s) saving
        self._qStore = None         # queue for storage
        self._nStore = 1            # num threads for storing default is 1
        self._tStore = []           # thread(s) for storing
        self._qExtract = None       # queue for extraction
        self._nExtract = 1          # num threads for extracting default is 1
        self._tExtract = []         # thread(s) for extracting

        # parse the config file (if none set to defaults)
        if cpath:
            conf = ConfigParser.RawConfigParser()
            if not conf.read(cpath): raise NidusDBException('%s is invalid' % cpath)

            # save section of SSE
            try:
                # save section
                self._raw['save'] = conf.getboolean('SSE','save')
                if self._raw['save']:
                    self._raw['private'] = conf.get('SSE','save_private')
                    self._raw['path'] = conf.get('SSE','save_path')
                    self._raw['sz'] = conf.getint('SSE','save_maxsize') * 1048576
                    self._raw['nfiles'] = conf.getint('SSE','save_maxfiles')

                # number of storing and extracting threads
                self._nStore = conf.getint('SSE','store_threads')
                self._nExtract = conf.getint('SSE','extract_threads')
            except ValueError as e:
                raise NidusDBException("%s" % e)
            except (ConfigParser.NoSectionError,ConfigParser.NoOptionError) as e:
                raise NidusDBException("%s" % e)

            # oui file
            if conf.has_option('OUI','path'):
                self._oui = parseoui(conf.get('OUI','path'))


    def __del__(self):
        """ called during garbage collection forces shuts down connection """
        self.shutdown()

    def shutdown(self):
        """ closes open connections, cleans up """
        self.disconnect()

    def connect(self):
        """ client connects to NidusDB """
        try:
            # make connection, cursor and set session timezone to utc
            self._conn = psql.connect(host="localhost",
                                      dbname="nidus",
                                      user="nidus",
                                      password="nidus")
            self._curs = self._conn.cursor()
            self._curs.execute("set time zone 'UTC';")
            self._conn.commit()

        except psql.OperationalError as e:
            if e.__str__().find('connect') > 0:
                raise NidusDBServerException("Postgresql not running")
            elif e.__str__().find('authentication') > 0:
                raise NidusDBAuthException("Invalid connection string")
            else:
                raise NidusDBException("Database failure: %s" % e)
        except Exception as e:
            raise NidusDBException("Unknown failure: %s" % e)

    def disconnect(self):
        """ client disconnects from NidusDB """
        try:
            # stop & wait on the sse threads
            for _ in self._tStore: self._qStore.put('!STOP!')
            for thread in self._tStore:
                if thread.is_alive(): thread.join()

            for _ in self._tExtract: self._qExtract.put('!STOP!')
            for thread in self._tExtract:
                if thread.is_alive(): thread.join()

            for thread in self._tSave:
                self._qSave[thread].put('!STOP!')
                if self._tSave[thread].is_alive(): self._tSave[thread].join()
        except:
            # blanket exception
            pass
        finally:
            # close out database
            if self._conn and not self._conn.closed:
                self._curs.close()
                self._conn.close()

    def submitdevice(self,f,ip=None):
        """ submitdevice - submit the string fields to the database """
        try:
            # tokenize the string f, convert to dict
            ds = nmp.data2dict(nmp.tokenize(f),"DEVICE")

            # what type of device
            if not ds['type'] in ['sensor','radio','gpsd']:
                raise NidusDBSubmitParamException("Invalid Device type %s" % ds['type'])
            if ds['type'] == "sensor":
                try:
                    self._setsensor(ds['ts'],ds['id'],ds['state'],ip)
                except NidusDBException:
                    # one of our threads failed to connect to database - reraise
                    self._conn.rollback()
                    raise
            elif ds['type'] == "radio":
                self._setradio(ds['ts'],ds['id'],ds['state'])
            elif ds['type'] == 'gpsd':
                self._setgpsd(ds['ts'],ds['state'])
        except nmp.NMPException as e:
            raise NidusDBSubmitParseException(e)
        except psql.Error as e:
            # rollback so postgresql is not left in error state
            self._conn.rollback()
            raise NidusDBSubmitException("%s: %s" % (e.pgcode,e.pgerror))
        else:
            self._conn.commit()

    def submitdropped(self):
        """ sensor exited unexpectantly, close out open ended records """
        if not self._sid: return
        try:
            # get current time
            ts = ts2iso(time.time())

            # close out the sensor
            sql = """
                   update sensor set period = tstzrange(lower(period),%s)
                   where session_id = %s;
                  """
            self._curs.execute(sql,(ts,self._sid))

            # close out radios
            # get radios currently used by sensor
            sql = " select mac from using_radio where sid=%s;"
            self._curs.execute(sql,(self._sid,))
            for row in self._curs.fetchall():
                mac = row[0]

                # close out radio_epoch
                sql = """
                       update radio_epoch set period = tstzrange(lower(period),%s)
                       where mac = %s and upper(period) is NULL;
                      """
                self._curs.execute(sql,(ts,mac))

                # close out radio_period
                sql = """
                       update radio_period set period = tstzrange(lower(period),%s)
                       where mac = %s and upper(period) is NULL;
                      """
                self._curs.execute(sql,(ts,mac))

                # close out using_radio
                sql = """
                       update using_radio set period = tstzrange(lower(period),%s)
                       where sid=%s and mac=%s;
                      """
                self._curs.execute(sql,(ts,self._sid,mac))

            # close out gpsd
            sql = """
                   update using_gpsd set period = tstzrange(lower(period),%s)
                   where sid=%s;
                  """
            self._curs.execute(sql,(ts,self._sid))
        except psql.Error:
            # don't raise an exception here, nidus is already exiting
            self._conn.rollback()
        else:
            self._conn.commit()

    def submitgpsd(self,f):
        """ submitgpsd - submit the string fields to the database """
        try:
            # tokenize the string f and convert to dict
            ds = nmp.data2dict(nmp.tokenize(f),"GPSD")

            # submit to db
            # insert into the gpsd table (if it does not already exist)
            self._curs.execute("select id from gpsd where devid=%s;",(ds['id'],))
            row = self._curs.fetchone()
            if not row:
                sql = """
                       insert into gpsd (devid,version,flags,driver,bps,tty)
                       values (%s,%s,%s,%s,%s,%s) returning id;
                      """
                self._curs.execute(sql,(ds['id'],ds['vers'],ds['flags'],
                                        ds['driver'],ds['bps'],ds['path']))
                self._gid = self._curs.fetchone()[0]
            else:
                self._gid = row[0]

            # insert into the using table
            sql = """
                  insert into using_gpsd (sid,gid,period)
                  values (%s,%s,tstzrange(%s,NULL,'[]'));
                """
            self._curs.execute(sql,(self._sid,self._gid,ds['ts']))
        except nmp.NMPException as e:
            raise NidusDBSubmitParseException(e)
        except psql.Error as e:
            # rollback so postgresql is not left in error state
            self._conn.rollback()
            raise NidusDBSubmitException("%s: %s" % (e.pgcode,e.pgerror))
        else:
            self._conn.commit()

    def submitradio(self,f):
        """ submitradio - submit the string fields to the database """
        try:
            # tokenize the string f and convert to dict
            ds = nmp.data2dict(nmp.tokenize(f),"RADIO")

            # submit to db
            # insert radio into radio table if it does not exist
            self._curs.execute("select * from radio where mac=%s;",(ds['mac'],))
            if not self._curs.fetchone():
                # truncate the strings to max length 20
                sql = """
                       insert into radio (mac,driver,chipset,channels,standards)
                       values (%s,%s,%s,%s,%s);
                      """
                self._curs.execute(sql,(ds['mac'],ds['driver'][0:20],
                                        ds['chipset'][0:20],ds['channels'],
                                        ds['standards'][0:20]))

            # insert epochal
            sql = """
                   insert into radio_epoch
                    (mac,role,ant_offset,ant_gain,ant_loss,ant_type,description,period)
                   values (%s,%s,%s,%s,%s,%s,%s,tstzrange(%s,NULL,'[]'));
                  """
            self._curs.execute(sql,(ds['mac'],ds['role'],ds['ant_offset'],ds['ant_gain'],
                                    ds['ant_loss'],ds['ant_type'],ds['desc'],ds['ts']))

            # insert periodic
            sql = """
                   insert into radio_period (mac,spoofed,txpwr,period)
                   values (%s,%s,%s,tstzrange(%s,NULL,'[]'));
                  """
            self._curs.execute(sql,(ds['mac'],ds['spoofed'],ds['txpwr'],ds['ts']))

            # insert using_radio
            sql = """
                   insert into using_radio (sid,mac,phy,nic,vnic,period)
                   values (%s,%s,%s,%s,%s,tstzrange(%s,NULL,'[]'));
                  """
            self._curs.execute(sql,(self._sid,ds['mac'],ds['phy'],ds['nic'],
                                    ds['vnic'],ds['ts']))

            # start save thread if save is enabled
            if self._raw['save']:
                self._qSave[ds['mac']] = Queue.Queue()
                self._tSave[ds['mac']] = SaveThread(self._qSave[ds['mac']],
                                                    self._raw['path'],
                                                    self._raw['private'],
                                                    self._raw['sz'])
                self._tSave[ds['mac']].start()

        except nmp.NMPException as e:
            raise NidusDBSubmitParseException(e)
        except psql.Error as e:
            # rollback so postgresql is not left in error state
            self._conn.rollback()
            raise NidusDBSubmitException("%s: %s" % (e.pgcode,e.pgerror))
        except NidusDBException:
            # our thread failed to connect to database - reraise
            self._conn.rollback()
            raise
        else:
            self._conn.commit()

    def submitradioevent(self,f):
        """ submitradioevent - submit the string fields to the database """
        try:
            # tokenize the string f and convert to dict
            ds = nmp.data2dict(nmp.tokenize(f),"RADIO_EVENT")

            sql = "insert into radio_event values (%s,%s,%s,%s);"
            self._curs.execute(sql,(ds['mac'],ds['event'],ds['params'],ds['ts']))
        except nmp.NMPException as e:
            raise NidusDBSubmitParseException(e)
        except psql.Error as e:
            self._conn.rollback()
            raise NidusDBSubmitException("%s: %s" % (e.pgcode,e.pgerror))
        else:
            self._conn.commit()

    def submitframe(self,f):
        """
         submitframe - submit the string fields to the database
          s - save frame to file
          s - store frame in data store
          e - extract details on nets/stas
        """
        # tokenize the data
        try:
            ds = nmp.data2dict(nmp.tokenize(f),"FRAME")
        except nmp.NMPException as e:
            raise NidusDBSubmitParseException(e)

        # because each thread relies on a frame id and for that frame to exist
        # frames are inserted here. The worker threads will insert as necessary
        # remaining details

        # parse the radiotap and mpdu
        f = ds['frame']  # pull out the frame
        lF = len(f)      # & get the total length
        dR = {}          # make an empty rtap dict
        dM = mpdu.MPDU() # & an empty mpdu dict
        validRTAP = True # rtap was parsed correctly
        validMPDU = True # mpdu was parsed correctly
        try:
            dR = rtap.parse(f)
            dM = mpdu.parse(f[dR['sz']:],rtap.flags_get(dR['flags'],'fcs'))
        except rtap.RadiotapException:
            # the parsing failed at radiotap, set insert values to empty
            validRTAP = validMPDU = False
            vs = (self._sid,ds['ts'],lF,0,0,[0,lF],0,'none',0)
        except mpdu.MPDUException:
            # the radiotap was valid but mpdu failed - initialize empty mpdu
            validMPDU = False
            vs = (self._sid,ds['ts'],lF,dR['sz'],0,[dR['sz'],lF],
                  int('a-mpdu' in dR['present']),0,0)
        else:
            vs = (self._sid,ds['ts'],lF,dR['sz'],
                  dM.offset,[(dR['sz']+dM.offset),(lF-dM.stripped)],
                  int('a-mpdu' in dR['present']),
                  rtap.flags_get(dR['flags'],'fcs'))

        # insert the frame
        sql = """
               insert into frame (sid,ts,bytes,bRTAP,bMPDU,data,ampdu,fcs)
               values (%s,%s,%s,%s,%s,%s,%s,%s) returning id;
              """
        try:
            self._curs.execute(sql,vs)
            fid = self._curs.fetchone()[0]
        except psql.Error as e:
            self._conn.rollback()
            raise NidusDBSubmitException("%s: %s" % (e.pgcode,e.pgerror))
        else:
            self._conn.commit()

        # put task(s) on SSE queues
        # S: frame will always be saved (if specified in config file
        # S: frame will be 'stored' if radiotap is valid
        # E: frame will be 'extracted' if mpdu is valid
        if self._raw['save']:
            # setup our left/right boundaries for privacy feature
            l = r = 0
            if validRTAP: l += dR['sz']
            if validMPDU:
                l += dM.offset
                r = lF-dM.stripped
            self._qSave[ds['mac']].put(SaveTask(ds['ts'],fid,self._sid,ds['mac'],f,(l,r)))
        if validRTAP: self._qStore.put(StoreTask(fid,ds['mac'],dR,dM))
        if validMPDU: self._qExtract.put(ExtractTask(ds['ts'],fid,dM))

    def submitgeo(self,f):
        """ submitgeo - submit the string fields to the database """
        try:
            # tokenize the string f and convert to dict, convert lat/lon to mgrs
            ds = nmp.data2dict(nmp.tokenize(f),"GPS")

            # submit to db
            sql = """
                   insert into geo (gid,ts,coord,alt,spd,dir,
                                    fix,xdop,ydop,pdop,epx,epy)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
                  """
            self._curs.execute(sql,(self._gid,ds['ts'],ds['coord'],ds['alt'],
                                    ds['spd'],ds['dir'],ds['fix'],ds['xdop'],
                                    ds['ydop'],ds['pdop'],ds['epx'],ds['epy']))
        except nmp.NMPException as e:
            raise NidusDBSubmitParseException(e)
        except psql.Error as e:
            self._conn.rollback()
            raise NidusDBSubmitException("%s: %s" % (e.pgcode,e.pgerror))
        else:
            self._conn.commit()

    ### NOTE: for all _set* functions commit or rollback is executed from caller

    def _setsensor(self,ts,did,state,ip):
        """ set the state of the sensor """
        # up or down
        if state:
            # open the sensor record
            sql="""
                 insert into sensor (hostname,ip,period)
                 values (%s,%s,tstzrange(%s,NULL,'[]')) RETURNING session_id;
                """
            self._curs.execute(sql,(did,ip,ts))
            self._sid = self._curs.fetchone()[0]

            # start extract and store threads here - save threads will be
            # started in the submitradio function
            # store threads
            self._qStore = Queue.Queue()
            for i in xrange(self._nStore):
                thread = StoreThread(self._qStore,self._sid)
                thread.start()
                self._tStore.append(thread)

            # extract threads
            self._lSta = threading.Lock()
            self._qExtract = Queue.Queue()
            for i in xrange(self._nExtract):
                thread = ExtractThread(self._qExtract,
                                       self._lSta,
                                       self._sid,
                                       self._oui)
                thread.start()
                self._tExtract.append(thread)
        else:
            # close out the sensor record
            sql = """
                   update sensor set period = tstzrange(lower(period),%s)
                   where session_id = %s;
                  """
            self._curs.execute(sql,(ts,self._sid))

    def _setradio(self,ts,did,state):
        """ set the state of a radio """
        if not state:
            # close out radio_epochal,
            sql = """
                   update radio_epoch set period = tstzrange(lower(period),%s)
                   where mac = %s and upper(period) is NULL;
                  """
            self._curs.execute(sql,(ts,did))

            # radio_periodic
            sql = """
                   update radio_period set period = tstzrange(lower(period),%s)
                   where mac = %s and upper(period) is NULL;
                  """
            self._curs.execute(sql,(ts,did))

            # and using_radio record
            sql = """
                   update using_radio set period = tstzrange(lower(period),%s)
                   where sid = %s and mac = %s;
                  """
            self._curs.execute(sql,(ts,self._sid,did))

    def _setgpsd(self,ts,state):
        """ set the state of the gpsd """
        if not state:
            sql = """
                   update using_gpsd set period = tstzrange(lower(period),%s)
                   where sid = %s and gid = %s;
                  """
            self._curs.execute(sql,(ts,self._sid,self._gid))