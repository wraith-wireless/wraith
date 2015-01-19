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
__version__ = '0.1.1'
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
import uuid                                            # for frame id
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
    def __new__(cls,ts,fid,mac,lFrame,l1,l2):
        return super(StoreTask,cls).__new__(cls,tuple([ts,fid,mac,lFrame,l1,l2]))
    @property
    def ts(self): return self[0]
    @property
    def fid(self): return self[1]
    @property
    def mac(self): return self[2]
    @property
    def length(self): return self[3]
    @property
    def l1(self): return self[4]
    @property
    def l2(self): return self[5]

class ExtractTask(tuple):
    # noinspection PyInitNewSignature
    def __new__(cls,ts,fid,l2):
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

    def run(self):
        # connect to db
        conn = None
        try:
            conn = psql.connect(host="localhost",dbname="nidus",
                                user="nidus",password="nidus")
            curs = conn.cursor()
            curs.execute("set time zone 'UTC';")
            curs.close()
            conn.commit()
        except psql.OperationalError as e:
            if e.__str__().find('connect') > 0:
                raise NidusDBServerException("Postgresql not running")
            elif e.__str__().find('authentication') > 0:
                raise NidusDBAuthException("Invalid connection string")
            else:
                raise NidusDBException("Database failure: %s" % e)

        # processing loop
        while True:
            item = self._qT.get()
            if item == '!STOP!': break
            try:
                self._consume(item,conn)
            except NidusDBSubmitException as e:
                print "Error: ", e
            except Exception as e:
                print "Error: ", e

        # cleanup
        self._cleanup()
        if conn and not conn.closed: conn.close()

    def _consume(self,item,conn): raise NotImplementedError
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
        self._fout = None

    def _cleanup(self):
        """ close file if it is open """
        if self._fout: self._fout.close()

    def _consume(self,item,conn):
        """ write the packet in item to file """
        fid = item.fid
        frame = item.frame
        (left,right) = item.offsets
        fname = None
        if not self._fout or os.path.getsize(self._fout.name) > self._sz:
            if self._fout:
                self._fout.close()
                self._fout = None
            fname = os.path.join(self._path,"%d_%s_%s.pcap" % (item.sid,
                                                               item.ts,
                                                               item.mac))
        curs = conn.cursor()
        try:
            # need to open a new file?
            if not self._fout: self._fout = pcap.pcapopen(fname)

            # if private, only write the layer 1, layer 2
            if self._private:
                if left < right: frame = frame[:left] + frame[right:]
            pcap.pktwrite(self._fout,item.ts,frame)

            # store in datastore
            sql = "insert into frame_path (id,filepath) values (%s,%s);"
            curs.execute(sql,(fid,os.path.join(self._path,
                                               os.path.split(self._fout.name)[1])))
        except pcap.PCAPException:
            # try closing the file
            self._fout.close()
            raise
        except psql.Error as e:
            conn.rollback()
            raise NidusDBSubmitException(e.pgcode,e.pgerror)
        else:
            conn.commit()
        finally:
            curs.close()

class StoreThread(SSEThread):
    """ stores the frames in the task queue to the db """
    def __init__(self,tasks,sid):
        """
         tasks - the tasks queue
         sid - session id
        """
        SSEThread.__init__(self,tasks)
        self._sid = sid

    def _cleanup(self): pass

    def _consume(self,item,conn):
        # get our cursor & extract vars from item
        curs = conn.cursor()
        ts = item.ts
        fid = item.fid
        rdo = item.mac
        lF = item.length
        dR = item.l1
        dM = item.l2

        try:
            # insert the frame - if invalid stop after insertion and commit it
            sql = """
                   insert into frame (id,sid,ts,bytes,bRTAP,bMPDU,data,ampdu,crypt,fcs)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
                  """
            if not dR:
                curs.execute(sql,(fid,self._sid,ts,lF,0,0,[0,lF],0,'none',0))
                conn.commit()
                return

            # valid header, continue
            curs.execute(sql,(fid,self._sid,ts,lF,dR['sz'],dM.offset,
                              [(dR['sz']+dM.offset),(lF-dM.stripped)],
                              int('a-mpdu' in dR['present']),
                              dM.crypt['type'] if dM.crypt else 'none',
                              rtap.flags_get(dR['flags'],'fcs')))

            # insert ampdu?
            if 'a-mpdu' in dR['present']:
                sql = "insert into ampdu (fid,refnum,flags) values (%s,%s,%s);"
                curs.execute(sql,(fid,dR['a-mpdu'][0],dR['a-mpdu'][1]))

            # insert the source record
            ant = dR['antenna'] if 'antenna' in dR else 0
            pwr = dR['antsignal'] if 'antsignal' in dR else 0
            sql = "insert into source (fid,src,antenna,rfpwr) values (%s,%s,%s,%s);"
            curs.execute(sql,(fid,rdo,ant,pwr))

            # insert signal record
            # determine the standard, rate and mcs fields # NOTE: we assume that
            # channels will always be present in radiotap
            sql = """
                   insert into signal (fid,std,rate,channel,chflags,rf,ht,
                                       mcs_bw,mcs_gi,mcs_ht,mcs_index)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
                  """
            try:
                std = 'n'
                mcsflags = rtap.mcsflags_params(dR['mcs'][0],dR['mcs'][1])
                if mcsflags['bw'] == rtap.MCS_BW_20: bw = '20'
                elif mcsflags['bw'] == rtap.MCS_BW_40: bw = '40'
                elif mcsflags['bw'] == rtap.MCS_BW_20L: bw = '20L'
                else: bw = '20U'
                width = 40 if bw == '40' else 20
                gi = 1 if 'gi' in mcsflags and mcsflags['gi'] > 0 else 0
                ht = 1 if 'ht' in mcsflags and mcsflags['ht'] > 0 else 0
                index = dR['mcs'][2]
                rate = mcs.mcs_rate(dR['mcs'][2],width,gi)
                hasMCS = 1
            except:
                if dR['channel'][0] in channels.ISM_24_F2C:
                    if rtap.chflags_get(dR['channel'][1],'cck'):
                        std = 'b'
                    else:
                        std = 'g'
                else:
                    std = 'a'
                rate = dR['rate'] * 0.5 if 'rate' in dR else 0
                bw = None
                gi = None
                ht = None
                index = None
                hasMCS = 0
            curs.execute(sql,(fid,std,rate,channels.f2c(dR['channel'][0]),
                              dR['channel'][1],dR['channel'][0],hasMCS,bw,gi,
                              ht,index))

            # insert traffic
            if dM:
                sql = """
                       insert into traffic (fid,type,subtype,td,fd,mf,rt,pm,md,pf,so,
                                            dur_type,dur_val,addr1,addr2,addr3,
                                            fragnum,seqnum,addr4)
                       values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                               %s,%s,%s,%s,%s,%s,%s,%s,%s);
                      """
                dVal = None
                if dM.duration['type'] == 'vcs': dVal = dM.duration['dur']
                elif dM.duration['type'] == 'aid': dVal = dM.duration['aid']
                curs.execute(sql,(fid,mpdu.FT_TYPES[dM.type],
                                  mpdu.subtypes(dM.type,dM.subtype),
                                  dM.flags['td'],dM.flags['fd'],
                                  dM.flags['mf'],dM.flags['r'],
                                  dM.flags['pm'],dM.flags['md'],
                                  dM.flags['pf'],dM.flags['o'],
                                  dM.duration['type'],dVal,
                                  dM.addr1,dM.addr2,dM.addr3,
                                  dM.seqctrl['fragno'] if dM.seqctrl else None,
                                  dM.seqctrl['seqno'] if dM.seqctrl else None,
                                  dM.addr4))

                # insert qos if present
                if dM.qosctrl:
                    sql = """
                           insert into qosctrl (fid,tid,eosp,ackpol,amsdu,txop)
                           values (%s,%s,%s,%s,%s,%s);
                          """
                    curs.execute(sql,(fid,dM.qosctrl['tid'],
                                          dM.qosctrl['eosp'],
                                          dM.qosctrl['ack-policy'],
                                          dM.qosctrl['a-msdu'],
                                          dM.qosctrl['txop']))

                # insert encyption if present
                if dM.crypt and False:
                    # setup sql statement and insert values
                    if dM.crypt['type'] == 'wep':
                        sql = """
                               insert into wepcrypt (fid,iv,key_id,icv)
                               values (%s,%s,%s,%s);
                              """
                        vs = (fid,dM.crypt['iv'],dM.crypt['key-id'],dM.crypt['icv'])
                    elif dM.crypt['type'] == 'tkip':
                        sql = """
                               insert into tkipcrypt (fid,ts1,wepseed,ts0,key_id,
                                                      tsc2,tsc3,tsc4,tsc5,mic,icv)
                               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
                              """
                        vs = (fid,dM.crypt['iv']['tsc1'],dM.crypt['iv']['wep-seed'],
                              dM.crypt['iv']['tsc0'],dM.crypt['iv']['key-id']['key-id'],
                              dM.crypt['ext-iv']['tsc2'],dM.crypt['ext-iv']['tsc3'],
                              dM.crypt['ext-iv']['tsc4'],dM.crypt['ext-iv']['tsc5'],
                              dM.crypt['mic'],dM.crypt['icv'])
                    elif dM.crypt['type'] == 'ccmp':
                        sql = """
                               insert into ccmpcrypt (fid,pn0,pn1,key_id,pn2,
                                                      pn3,pn4,pn5,mic)
                               values (%s,%s,%s,%s,%s,%s,%s,%s,%s);
                              """
                        vs = (fid,dM.crypt['pn0'],dM.crypt['pn1'],dM.crypt['key-id']['key-id'],
                              dM.crypt['pn2'],dM.crypt['pn3'],dM.crypt['pn4'],
                              dM.crypt['pn5'],dM.crypt['mic'])

                    # insert crypt if present
                    if sql and vs: curs.execute(sql,vs)
        except psql.Error as e:
            conn.rollback()
            curs.close()
            raise NidusDBSubmitException(e.pgcode,e.pgerror)

        conn.commit()
        curs.close()

class ExtractThread(SSEThread):
    """  extracts & stores details of nets/stas etc from mpdus in tasks queue """
    def __init__(self,tasks,stas,lSta,sid,oui):
        """
         stas - the session sta dictionary -> this is created by the caller
         lSta - lock on the stay dictionary
         sid - session id
         oui - oui dict
        """
        SSEThread.__init__(self,tasks)
        self._stas = stas
        self._l = lSta
        self._sid = sid
        self._oui = oui

    def _cleanup(self): pass

    def _consume(self,item,conn):
        # make a cursor and extract variables
        curs = conn.cursor()
        ts = item.ts
        fid = item.fid
        dM = item.l2
        return

        # sta addresses
        # Function To DS From DS Address 1 Address 2 Address 3 Address 4
        # IBSS/Intra   0    0        RA=DA     TA=SA     BSSID       N/A
        # From AP      0    1        RA=DA  TA=BSSID        SA       N/A
        # To AP        1    0     RA=BSSID     TA=SA        DA       N/A
        # Wireless DS  1    1     RA=BSSID  TA=BSSID     DA=WDS    SA=WDS

        # determine if each station exists already addr1 will always be present
        sql = "select sid,id,mac from sta where mac=%s"
        addrs = {dM['addr1'].lower():{'loc':[1],'id':None}}
        if 'addr2' in dM:
            a = dM['addr2'].lower()
            if a in addrs:
                addrs[a]['loc'].append(2)
            else:
                addrs[a] = {'loc':[2],'id':None}
                sql += " or mac=%s"
            if 'addr3' in dM:
                a = dM['addr3'].lower()
                if a in addrs:
                    addrs[a]['loc'].append(3)
                else:
                    addrs[a] = {'loc':[3],'id':None}
                    sql += " or mac=%s"
                if 'addr4' in dM:
                    a = dM['addr4'].lower()
                    if a in addrs:
                        addrs[a]['loc'].append(4)
                    else:
                        addrs[a] = {'loc':[4],'id':None}
                        sql += " or mac=%s"

        # main try-except block
        try:
            # add any non-broadcast addr(s) if not already present
            curs.execute(sql,tuple(addrs.keys())) # get rows sta w/ given mac addr
            rows = curs.fetchall()

            for addr in addrs:
                # if not broadcast, add sta id if found
                if addr == mpdu.BROADCAST: continue
                for row in rows:
                    if addr == row[2]:
                        addrs[addr]['id'] = row[1]
                        break

                # check current addr for an id, if not present add it
                if not addrs[addr]['id']:
                    sql = """
                           insert into sta (sid,spotted,mac,manuf,note)
                           values (%s,%s,%s,%s,%s)
                           RETURNING id;
                          """
                    curs.execute(sql,(self._sid,ts,addr,manufacturer(self._oui,addr),''))
                    addrs[addr]['id'] = curs.fetchone()[0]

                # addr2 is transmitting (i.e. heard) others are seen
                mode = 'tx' if 2 in addrs[addr]['loc'] else 'rx'

                # add/update shared sta activity timestamps
                #### ENTER CS
                try:
                    self._l.acquire()

                    if addr in self._stas:
                        if mode == 'tx':
                            self._stas[addr]['fh'] = self._stas[addr]['lh'] = ts
                        else:
                            self._stas[addr]['fs'] = self._stas[addr]['ls'] = ts

                        # update the record
                        sql = """
                               update sta_activity
                               set firstSeen=%s,lastSeen=%s,firstHeard=%s,lastHeard=%s
                               where sid = %s and staid = %s;
                              """
                        vs = (self._stas[addr]['fs'],self._stas[addr]['ls'],
                              self._stas[addr]['fh'],self._stas[addr]['lh'],
                              self._sid,self._stas[addr]['id'])
                    else:
                        # create a new entry for this sta
                        self._stas[addr] = {'id':addrs[addr]['id'],'fs':None,
                                            'ls':None,'fh':None,'lh':None}
                        if mode == 'tx':
                            self._stas[addr]['fh'] = self._stas[addr]['lh'] = ts
                        else:
                            self._stas[addr]['fs'] = self._stas[addr]['ls'] = ts

                        sql = """
                               insert into sta_activity (sid,staid,firstSeen,lastSeen,
                                                         firstHeard,lastHeard)
                               values (%s,%s,%s,%s,%s,%s);
                              """
                        vs = (self._sid,self._stas[addr]['id'],self._stas[addr]['fs'],
                              self._stas[addr]['ls'],self._stas[addr]['fh'],
                              self._stas[addr]['lh'])
                finally:
                    #### EXIT CS
                    # NOTE: any exceptions will be rethrown after releasing the lock
                    self._l.release()

                # update the database
                curs.execute(sql,vs)
        except psql.Error as e:
            conn.rollback()
            raise NidusDBSubmitException("%s: %s" % (e.pgcode,e.pgerror))
        else:
            conn.commit()
        finally:
            curs.close()

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
        self._stas = {}             # stas seen this session
        self._lSta = None           # lock on the stas dict
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
        # close out database
        if self._conn and not self._conn.closed:
            self._curs.close()
            self._conn.close()

        # stop & wait on the sse threads
        # save
        for thread in self._tSave: # save threads
            self._qSave[thread].put('!STOP!')
            if self._tSave[thread].is_alive(): self._tSave[thread].join()

        # store
        for _ in self._tStore: self._qStore.put('!STOP!')
        for thread in self._tStore:
            if thread.is_alive(): thread.join()

        # extract
        for _ in self._tExtract: self._qExtract.put('!STOP!')
        for thread in self._tExtract:
            if thread.is_alive(): thread.join()

    def submitdevice(self,f,ip=None):
        """ submitdevice - submit the string fields to the database """
        try:
            # tokenize the string f, convert to dict
            ds = nmp.data2dict(nmp.tokenize(f),"DEVICE")

            # what type of device
            if not ds['type'] in ['sensor','radio','gpsd']:
                raise NidusDBSubmitParamException("Invalid Device type %s" % ds['type'])
            if ds['type'] == "sensor":
                self._setsensor(ds['ts'],ds['id'],ds['state'],ip)
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

        # parse the radiotap and mpdu
        frame = ds['frame']
        try:
            dR = rtap.parse(frame)
            dM = mpdu.parse(frame[dR['sz']:],rtap.flags_get(dR['flags'],'fcs'))
        except rtap.RadiotapException:
            dR = {'sz':0}
            dM = mpdu.MPDU()
        except mpdu.MPDUException:
            dM = mpdu.MPDU()

        # send to SSE workers
        # store thread
        fid = uuid.uuid4().hex
        if self._raw['save']:
            self._qSave[ds['mac']].put(SaveTask(ds['ts'],fid,self._sid,ds['mac'],
                                                frame,(dR['sz']+dM.offset,
                                                       len(frame)-dM.stripped)))

        # send to queues
        self._qStore.put(StoreTask(ds['ts'],fid,ds['mac'],len(frame),dR,dM))
        if dM: self._qExtract.put(ExtractTask(ds['ts'],fid,dM))

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
                                       self._stas,
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