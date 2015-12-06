#!/usr/bin/env python

""" thresh.py: frame and metadata extraction and file writes

Provides Thresher and PCAPWriter:
 Thresher: processes of frames, stores frame data/metadata to DB.
 PCAPWriter: saves frames to file (if desired)

Each Process is configured to all for future commands (via tokens) to be used
to assist in any as of yet unidentified issues or future upgrades that may be
desired. Additionally, while each process will stop if given a token !STOP!,
the calling process i.e. the Collator can also send a SIGUSR1 signal to stop
the process out of order, i.e preemptively
"""
__name__ = 'thresh'
__license__ = 'GPL v3.0'
__version__ = '0.0.4'
__date__ = 'October 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import signal                               # handle signals
import select                               # for select
import time                                 # timestamps
import multiprocessing as mp                # multiprocessing
import psycopg2 as psql                     # postgresql api
from wraith.utils.timestamps import ts2iso  # timestamp conversion
from dateutil import parser as dtparser     # parse out timestamps
from wraith.iyri.constants import N         # row size in buffer
import wraith.wifi.radiotap as rtap         # 802.11 layer 1 parsing
from wraith.wifi import mpdu                # 802.11 layer 2 parsing
from wraith.wifi import mcs                 # mcs functions
from wraith.wifi import channels            # 802.11 channels/RFs
from wraith.wifi.oui import manufacturer    # oui functions
import sys,traceback                        # error reporting

def extractie(dM):
    """
     extracts info-elements for ssid, supported rates, extended rates & vendors
     :param dM: mpdu dict
     :returns: ssid,supported_rates,extended_rates,vendors
    """
    ssids = []
    ss = []
    es = []
    vs = []
    for ie in dM.info_els:
        if ie[0] == mpdu.EID_SSID: ssids.append(ie[1])
        if ie[0] == mpdu.EID_SUPPORTED_RATES: ss = ie[1]
        if ie[0] == mpdu.EID_EXTENDED_RATES: es = ie[1]
        if ie[0] == mpdu.EID_VEND_SPEC: vs.append(ie[1][0])
    return ssids,ss,es,vs

def isutf8(s):
    """
     determines whether string is utf-8 encodable
     :param s: string to check
     :returns: True if s is utf-8 encodable
    """
    try:
        s.decode('utf-8')
        return True
    except:
        return False

class Thresher(mp.Process):
    """
     Thresher process frames and inserts frame data in database
    """
    def __init__(self,comms,q,conn,lSta,abad,shama,dbstr,ouis):
        """
         :param comms: internal communication (to Collator)
         :param q: task queue from Collator
         :param conn: token connection from Collator
         :param lSta: lock for sta and sta activity inserts/updates
         :param abad: Abad buffer
         :param shama: Shama buffer
         :param dbstr: db connection string
         :param ouis: oui dict
        """
        mp.Process.__init__(self)
        self._icomms = comms # communications queue
        self._tasks = q      # connection from Collator
        self._cC = conn      # token connection from Collator
        self._abuff = abad   # abad buffer
        self._sbuff = shama  # shama buffer
        self._conn = None    # db connection
        self._l = lSta       # sta lock
        self._curs = None    # our cursor
        self._ouis = ouis    # oui dict
        self._stop = False   # stop flag
        self._write = False  # write flag
        self._next = None    # next operation to execute
        self._setup(dbstr)

    def terminate(self): pass

    @property
    def cs(self): return 'thresher-{0}'.format(self.pid)

    def run(self):
        """ execute frame process loop """
        # ignore signals used by main program
        signal.signal(signal.SIGINT,signal.SIG_IGN)   # CTRL-C and kill -INT stop
        signal.signal(signal.SIGTERM,signal.SIG_IGN)  # kill -TERM stop
        signal.signal(signal.SIGUSR1,self.stop)       # kill signal from Collator

        # local variables
        sid = None                    # current session id
        rdos = {}                     # radio map hwaddr{'role','buffer','writer'}
        ouis = {}                     # oui dict

        # notify collator we're up
        self._icomms.put((self.cs,ts2iso(time.time()),'!THRESH!',self.pid))

        while not self._stop:
            # check for tasks or messages
            tkn = ts = d = None
            rs,_,_ = select.select([self._cC,self._tasks._reader],[],[])

            # get each message
            for r in rs:
                ts1 = ts2iso(time.time()) # get timestamp for this data read
                try:
                    # get data
                    if r == self._cC: tkn,ts,d = self._cC.recv()
                    else: tkn,ts,d = self._tasks.get(0.5)

                    # & process it
                    if tkn == '!STOP!': self._stop = True
                    elif tkn == '!SID!': sid = d[0]
                    elif tkn == '!RADIO!':
                        # fill in radio map, assigning buffer and writer
                        rdos[d[0]] = {'role':d[1],'buffer':None,'record':False}
                        if d[1] == 'abad': rdos[d[0]]['buffer'] = self._abuff
                        elif d[1] == 'shama': rdos[d[0]]['buffer'] = self._sbuff
                        else:
                            msg = "Invalid role for radio: {0}".format(d[1])
                            self._icomms.put((self.cs,ts1,'!THRESH_WARN!',msg))
                    elif tkn == '!WRITE!':
                        rdos[d[0]]['record'] = d[1]
                    elif tkn == '!FRAME!':
                        self._processframe(sid,rdos,ts,ts1,d)
                    else:
                        msg = "invalid token {0}".format(tkn)
                        self._icomms.put((self.cs,ts1,'!THRESH_WARN!',msg))
                except (IndexError,ValueError,KeyError) as e:
                    _,_,etrace = sys.exc_info()
                    msg = "{0} {1}\n{2}".format(type(e).__name__,e,
                                                repr(traceback.format_tb(etrace)))
                    self._icomms.put((self.cs,ts1,'!THRESH_WARN!',msg))
                except Exception as e:
                    _,_,etrace = sys.exc_info()
                    msg = "{0} {1}\n{2}".format(type(e).__name__,e,
                                                repr(traceback.format_tb(etrace)))
                    self._icomms.put((self.cs,ts1,'!THRESH_WARN!',msg))

        # notify collector we're down
        if self._curs: self._curs.close()
        if self._conn: self._conn.close()
        self._icomms.put((self.cs,ts2iso(time.time()),'!THRESH!',None))

    def stop(self,signum=None,stack=None): self._stop = True

    def _setup(self,dbstr):
        """
         initialize db connection

         :param dbstr: db connection string
        """
        try:
            # connect to db
            self._conn = psql.connect(host=dbstr['host'],
                                      port=dbstr['port'],
                                      dbname=dbstr['db'],
                                      user=dbstr['user'],
                                      password=dbstr['pwd'])
            self._curs = self._conn.cursor()
            self._curs.execute("set time zone 'UTC';")
            self._conn.commit()
        except Exception as e:
            if self._curs:
                self._conn.rollback()
                self._curs.close()
            if self._conn: self._conn.close()
            raise RuntimeError(e)

    def _processframe(self,sid,rdos,ts,ts1,d):
        """
         inserts frame into db

         :param rdos: radio dict
         :param d:  data
        """
        # pull frame out of buffer
        src,ix,b = d[0],d[1],d[2] # hwaddr,index,nBytes
        f = rdos[src]['buffer'][(ix*N):(ix*N)+b].tobytes()

        # parse the frame
        fid = None       # current frame id
        vs = ()          # values for db insert
        lF = len(f)      # & get the total length
        dR = {}          # make an empty rtap dict
        dM = mpdu.MPDU() # & an empty mpdu dict
        validRTAP = True # rtap was parsed correctly
        validMPDU = True # mpdu was parsed correctly
        try:
            dR = rtap.parse(f)
            dM = mpdu.parse(f[dR['sz']:],rtap.flags_get(dR['flags'],'fcs'))
        except rtap.RadiotapException: # parsing failed @ radiotap, set empty vals
            validRTAP = validMPDU = False
            vs = (sid,ts,lF,0,0,[0,lF],0,'none',0)
        except mpdu.MPDUException: # mpdu failed - initialize empty mpdu vals
            validMPDU = False
            vs = (sid,ts,lF,dR['sz'],0,[dR['sz'],lF],dR['flags'],
                  int('a-mpdu' in dR['present']),rtap.flags_get(dR['flags'],'fcs'))
        except Exception as e: # blanket error
            _,_,etrace = sys.exc_info()
            msg = "Parsing Error. {0} {1}\n{2}".format(type(e).__name__,e,
                                                       repr(traceback.format_tb(etrace)))
            self._icomms.put((self.cs,ts1,'!THRESH_WARN!',msg))
            return
        else:
            vs = (sid,ts,lF,dR['sz'],dM.offset,
                  [(dR['sz']+dM.offset),(lF-dM.stripped)],
                  dR['flags'],int('a-mpdu' in dR['present']),
                  rtap.flags_get(dR['flags'],'fcs'))

        # individual helper functions will commit database inserts/updates. All
        # db errors will be caught in this try & rollbacks will be executed here
        try:
            self._next = 'frame'

            # insert the frame and get frame's id
            sql = """
                   insert into frame (sid,ts,bytes,bRTAP,bMPDU,data,flags,ampdu,fcs)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s) returning frame_id;
                  """
            self._curs.execute(sql,vs)
            fid = self._curs.fetchone()[0]
            self._conn.commit()

            # notify collator & insert malformed if we had any issues
            if dM.error:
                self._icomms.put((self.cs,ts1,'!THRESH_WARN!',
                                  "Frame {0}. Bad MPDU".format(fid)))
                sql = """
                       insert into malformed (fid,location,reason)
                       values (%s,%s,%s);
                      """
                self._curs.execute(sql,(fid,dM.error[1],dM.error[2]))
                self._conn.commit()

            # pass fid, index, nBytes, left, right indices to writer
            if rdos[src]['record']:
                self._next = 'frame_raw'
                sql = "insert into frame_raw (fid,raw) values (%s,E%s);"
                self._curs.execute(sql,(fid,f))
                self._conn.commit()
            #if self._write:
            #    l = r = 0
            #    if validRTAP: l += dR['sz']
            #    if validMPDU:
            #        l += dM.offset
            #        r = lF-dM.stripped
            #    rdos[src]['writer'].put(('!FRAME!',ts,[fid,ix,b,l,r]))

            # NOTE: the next two "parts" storing and extracting are mutually
            # exlusive & are required to occur sequentially, thus could be
            # handled by threads/processes

            # (1) store frame details in db
            self._next = 'store'
            self._insertrtap(fid,src,dR)
            if not dM.isempty: self._insertmpdu(fid,dM)
            else: return

            # (2) extract
            self._next = 'extract'
            # sta addresses
            # Fct        To From    Addr1    Addr2  Addr3  Addr4
            # IBSS/Intra  0    0    RA=DA    TA=SA  BSSID    N/A
            # From AP     0    1    RA=DA TA=BSSID     SA    N/A
            # To AP       1    0 RA=BSSID    TA=SA     DA    N/A
            # Wireless DS 1    1 RA=BSSID TA=BSSID DA=WDS SA=WDS

            # pull unique addresses of stas from mpdu into the addr dict
            # having the form: <hwaddr>->{'loc:[<i..n>], where i=1..4
            #                             'id':<sta_id>}
            # NOTE: insertsta modifies the addrs dict in place assigning ids to
            # each nonbroadcast address
            addrs = {}
            for i,a in enumerate(['addr1','addr2','addr3','addr4']):
                if not a in dM: break
                if dM[a] in addrs: addrs[dM[a]]['loc'].append(i+1)
                else: addrs[dM[a]] = {'loc':[i+1],'id':None}

            # insert the sta, sta_activity
            self._insertsta(fid,sid,ts,addrs)
            self._insertsta_activity(fid,sid,ts,addrs)

            # further process mgmt frames?
            self._next = 'mgmt'
            if dM.type == mpdu.FT_MGMT: self._processmgmt(fid,sid,ts,addrs,dM)
        except psql.OperationalError as e: # unrecoverable
            if fid:
                msg = "Frame {0} insert failed at {1}. {2}: {3}.".format(fid,
                                                                         self._next,
                                                                         e.pgcode,
                                                                         e.pgerror)
            else:
                msg = "Failed to insert frame. {0}: {1}.".format(e.pgcode,e.pgerror)
            self._icomms.put((self.cs,ts1,'!THRESH_ERR!',msg))
        except psql.Error as e:
            self._conn.rollback()
            if fid:
                msg = "<PSQL> Frame {0} failed at {1}. {2}: {3}.".format(fid,
                                                                         self._next,
                                                                         e.pgcode,
                                                                         e.pgerror)
            else:
                msg = "<PSQL> Failed to insert frame. {0}: {1}.".format(e.pgcode,
                                                                        e.pgerror)
            self._icomms.put((self.cs,ts1,'!THRESH_WARN!',msg))
        except Exception as e:
            _,_,etrace = sys.exc_info()
            self._conn.rollback()
            if fid:
                msg = "{0} {1} in frame {2}\n{3}".format(type(e).__name__,
                                                         e,fid,
                                                         repr(traceback.format_tb(etrace)))
            else:
                msg = "{0} {1}\n{2}".format(type(e).__name__,e,
                                            repr(traceback.format_tb(etrace)))
            self._icomms.put((self.cs,ts1,'!THRESH_WARN!',msg))

    #### All below _insert functions will allow db exceptions to pass through to caller

    def _insertrtap(self,fid,src,dR):
        """
         insert radiotap data into db

         :param fid: frame id
         :param src: collectors hw addr
         :param dR: parsed radiotap dict
        """
        # ampdu info
        self._next = 'a-mpdu'
        if 'a-mpdu' in dR['present']:
            sql = "insert into ampdu fid,refnum,flags) values (%s,%s,%s);"
            self._curs.execute(sql,(fid,dR['a-mpdu'][0],dR['a-mpdu'][1]))
            self._conn.commit()

        # source info
        self._next = 'source'
        ant = dR['antenna'] if 'antenna' in dR else 0
        pwr = dR['antsignal'] if 'antsignal' in dR else 0
        sql = "insert into source (fid,src,antenna,rfpwr) values (%s,%s,%s,%s);"
        self._curs.execute(sql,(fid,src,ant,pwr))
        self._conn.commit()

        # signal info - determine what standard, data rate and any mcs fields
        # assuming channel info is always in radiotap
        self._next = 'signal'
        sql = """
               insert into signal (fid,std,rate,channel,chflags,rf,ht,mcs_bw,
                                   mcs_gi,mcs_ht,mcs_index,mcs_stbc)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
              """
        try:
            std = 'n'
            mcsflags = rtap.mcsflags_params(dR['mcs'][0],dR['mcs'][1])
            if mcsflags['bw'] == rtap.MCS_BW_20: bw = '20'
            elif mcsflags['bw'] == rtap.MCS_BW_40: bw = '40'
            elif mcsflags['bw'] == rtap.MCS_BW_20L: bw = '20L'
            else: bw = '20U'
            width = 40 if bw == '40' else 20
            stbc = mcsflags['stbc']
            gi = 1 if 'gi' in mcsflags and mcsflags['gi'] > 0 else 0
            ht = 1 if 'ht' in mcsflags and mcsflags['ht'] > 0 else 0
            index = dR['mcs'][2]
            rate = mcs.mcs_rate(index,width,gi)
            hasMCS = 1
        except:
            if dR['channel'][0] in channels.ISM_24_F2C:
                if rtap.chflags_get(dR['channel'][1],'cck'): std = 'b'
                else: std = 'g'
            else: std = 'a'
            rate = dR['rate'] * 0.5 if 'rate' in dR else 0
            bw = None
            gi = None
            ht = None
            index = None
            stbc = None
            hasMCS = 0
        self._curs.execute(sql,(fid,std,rate,channels.f2c(dR['channel'][0]),
                                dR['channel'][1],dR['channel'][0],hasMCS,bw,gi,
                                ht,index,stbc))
        self._conn.commit()

    def _insertmpdu(self,fid,dM):
        """
         insert mpdu data into db

         :param fid: frame id
         :param dM: parsed mpdu dict
        """
        # insert the traffic
        dVal = None
        if dM.duration['type'] == 'vcs': dVal = dM.duration['dur']
        elif dM.duration['type'] == 'aid': dVal = dM.duration['aid']

        self._next = 'traffic'
        sql = """
               insert into traffic (fid,type,subtype,td,fd,mf,rt,pm,md,pf,so,
                                    dur_type,dur_val,addr1,addr2,addr3,
                                    fragnum,seqnum,addr4,crypt)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
              """
        self._curs.execute(sql,(fid,mpdu.FT_TYPES[dM.type],
                                mpdu.subtypes(dM.type,dM.subtype),
                                dM.flags['td'],dM.flags['fd'],
                                dM.flags['mf'],dM.flags['r'],
                                dM.flags['pm'],dM.flags['md'],
                                dM.flags['pf'],dM.flags['o'],
                                dM.duration['type'],dVal,
                                dM.addr1,dM.addr2,dM.addr3,
                                dM.seqctrl['fragno'] if dM.seqctrl else None,
                                dM.seqctrl['seqno'] if dM.seqctrl else None,
                                dM.addr4,
                                dM.crypt['type'] if dM.crypt else 'none',))
        self._conn.commit()

        # qos
        if dM.qosctrl:
            self._next = 'qos'
            sql = """
                   insert into qosctrl (fid,tid,eosp,ackpol,amsdu,txop)
                   values (%s,%s,%s,%s,%s,%s);
                  """
            self._curs.execute(sql,(fid,dM.qosctrl['tid'],
                                        dM.qosctrl['eosp'],
                                        dM.qosctrl['ack-policy'],
                                        dM.qosctrl['a-msdu'],
                                        dM.qosctrl['txop']))
            self._conn.commit()

        # encryption
        if dM.crypt:
            self._next = 'crypt'
            if dM.crypt['type'] == 'wep':
                sql = "insert into wepcrypt (fid,iv,key_id,icv) values (%s,%s,%s,%s);"
                self._curs.execute(sql,(fid,dM.crypt['iv'],
                                            dM.crypt['key-id'],
                                            dM.crypt['icv']))
            elif dM.crypt['type'] == 'tkip':
                sql = """
                       insert into tkipcrypt (fid,tsc1,wepseed,tsc0,key_id,
                                              tsc2,tsc3,tsc4,tsc5,mic,icv)
                       values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
                      """
                self._curs.execute(sql,(fid,dM.crypt['iv']['tsc1'],
                                            dM.crypt['iv']['wep-seed'],
                                            dM.crypt['iv']['tsc0'],
                                            dM.crypt['iv']['key-id']['key-id'],
                                            dM.crypt['ext-iv']['tsc2'],
                                            dM.crypt['ext-iv']['tsc3'],
                                            dM.crypt['ext-iv']['tsc4'],
                                            dM.crypt['ext-iv']['tsc5'],
                                            dM.crypt['mic'],
                                            dM.crypt['icv']))
            elif dM.crypt['type'] == 'ccmp':
                sql = """
                       insert into ccmpcrypt (fid,pn0,pn1,key_id,pn2,pn3,pn4,pn5,mic)
                       values (%s,%s,%s,%s,%s,%s,%s,%s,%s);
                      """
                self._curs.execute(sql,(fid,dM.crypt['pn0'],
                                            dM.crypt['pn1'],
                                            dM.crypt['key-id']['key-id'],
                                            dM.crypt['pn2'],
                                            dM.crypt['pn3'],
                                            dM.crypt['pn4'],
                                            dM.crypt['pn5'],
                                            dM.crypt['mic']))
            self._conn.commit()

    def _insertsta(self,fid,sid,ts,addrs):
        """
         insert unique sta from frame into db

         :param fid: frame id
         :param sid: session id
         :param ts: timestamp frame collected
         :param addrs: address dict
        """
        self._next = 'sta'
        # get list of nonbroadcast address (exit if there are none)
        nonbroadcast = [addr for addr in addrs if addr != mpdu.BROADCAST]
        if not nonbroadcast: return

        # create our sql statement
        sql = "select sta_id, mac from sta where "
        sql += " or ".join(["mac=%s" for _ in nonbroadcast])
        sql += ';'

        #### sta Critical Section
        with self._l:
            # get all rows with current sta(s) & add sta id if it is not new
            self._curs.execute(sql,tuple(nonbroadcast))
            for row in self._curs.fetchall():
                if row[1] in addrs: addrs[row[1]]['id'] = row[0]

            # for each address
            for addr in nonbroadcast:
                # if this one doesnt have an id (not seen before) add it
                if not addrs[addr]['id']:
                    # insert the new sta
                    sql = """
                           insert into sta (sid,fid,spotted,mac,manuf)
                           values (%s,%s,%s,%s,%s) RETURNING sta_id;
                          """
                    self._curs.execute(sql,(sid,fid,ts,addr,manufacturer(self._ouis,addr)))
                    addrs[addr]['id'] = self._curs.fetchone()[0]
                    self._conn.commit()

    def _insertsta_activity(self,fid,sid,ts,addrs):
        """
         inserts activity of all stas in db

         :param fid: frame id
         :param sid: session id
         :param ts: timestamp frame collected
         :param addrs: address dict
        """
        self._next = 'sta_activity'
        # get list of nonbroadcast address (exit if there are none)
        nonbroadcast = [addr for addr in addrs if addr != mpdu.BROADCAST]
        if not nonbroadcast: return

        #### sta Critical Section
        with self._l:
            for addr in nonbroadcast:
                # check current sta activity
                sql = """
                       select firstSeen,lastSeen,firstHeard,lastHeard
                       from sta_activity where sid=%s and staid=%s;
                      """
                self._curs.execute(sql,(sid,addrs[addr]['id']))
                row = self._curs.fetchone()

                # setup mode and timestamps (addr2 is transmitting i.e. heard)
                mode = 'tx' if 2 in addrs[addr]['loc'] else 'rx'
                fs = ls = fh = lh = None

                if not row:
                    # sta has not been seen this session
                    # commit the transaction because we were experiencing
                    # duplicate key issues w/o commit
                    if mode == 'tx': fh = lh = ts
                    else: fs = ls = ts
                    sql = """
                           insert into sta_activity (sid,staid,firstSeen,lastSeen,
                                                     firstHeard,lastHeard)
                           values (%s,%s,%s,%s,%s,%s);
                          """
                    self._curs.execute(sql,(sid,addrs[addr]['id'],fs,ls,fh,lh))
                    self._conn.commit()
                else:
                    # sta has been seen this session
                    # we have to convert the frame ts to a datatime obj w/ tx
                    # to compare with the db's ts
                    tstz = dtparser.parse(ts+"+00:00")
                    if mode == 'tx':
                        # check 'heard' activities
                        if not row[2]: # 1st tx heard by sta, update first/lastHeard
                            fh = lh = ts
                        elif tstz > row[3]: # tx is later than lastHeard, update it
                            lh = ts
                    else:
                        # check 'seen' activities
                        if not row[0]: # 1st time sta seen, update first/lastSeen
                            fs = ls = ts
                        elif tstz > row[1]: # ts is later than lastSeen, update it
                            ls = ts

                    # build query if there is something to update
                    us = ""
                    vs = []
                    if fs or ls or fh or lh:
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
                        self._curs.execute(sql,tuple(vs+[sid,addrs[addr]['id']]))
                        self._conn.commit()

    def _processmgmt(self,fid,sid,ts,addrs,dM):
        """
         insert individual mgmt frames

         :param fid: frame id
         :param sid: session id
         :param sid: session id
         :param ts: timestamp of frame
         :param addrs: address dict
         :param dM: mpdu dict
        """
        if dM.subtype == mpdu.ST_MGMT_ASSOC_REQ:
            self._next = 'assocreq'
            self._insertassocreq(fid,addrs[dM.addr2]['id'],
                                 addrs[dM.addr1]['id'],dM)
        elif dM.subtype == mpdu.ST_MGMT_ASSOC_RESP:
            self._next = 'assocresp'
            self._insertassocresp('assoc',fid,addrs[dM.addr2]['id'],
                                  addrs[dM.addr1]['id'],dM)
        elif dM.subtype == mpdu.ST_MGMT_REASSOC_REQ:
            self._next = 'reassocreq'
            self._insertreassocreq(fid,sid,ts,addrs[dM.addr2]['id'],
                                   addrs[dM.addr1]['id'],dM)
        elif dM.subtype == mpdu.ST_MGMT_REASSOC_RESP:
            self._next = 'reassocresp'
            self._insertassocresp('reassoc',fid,addrs[dM.addr2]['id'],
                                  addrs[dM.addr1]['id'],dM)
        elif dM.subtype == mpdu.ST_MGMT_PROBE_REQ:
            self._next = 'probereq'
            self._insertprobereq(fid,addrs[dM.addr2]['id'],
                                 addrs[dM.addr3]['id'],dM)
        elif dM.subtype == mpdu.ST_MGMT_PROBE_RESP:
            self._next = 'proberesp'
            self._insertproberesp(fid,addrs[dM.addr2]['id'],
                                  addrs[dM.addr1]['id'],dM)
        elif dM.subtype == mpdu.ST_MGMT_TIMING_ADV: pass
        elif dM.subtype == mpdu.ST_MGMT_BEACON:
            self._next = 'beacon'
            self._insertbeacon(fid,addrs[dM.addr2]['id'],dM)
        elif dM.subtype == mpdu.ST_MGMT_ATIM: pass
        elif dM.subtype == mpdu.ST_MGMT_DISASSOC:
            self._next = 'disassoc'
            self._insertdisassaoc(fid,addrs[dM.addr1]['id'],
                                  addrs[dM.addr2]['id'],dM)
        elif dM.subtype == mpdu.ST_MGMT_AUTH:
            self._next = 'auth'
            self._insertauth(fid,addrs[dM.addr1]['id'],
                             addrs[dM.addr2]['id'],dM)
        elif dM.subtype == mpdu.ST_MGMT_DEAUTH:
            self._next = 'deauth'
            self._insertdeauth(fid,addrs[dM.addr1]['id'],
                               addrs[dM.addr2]['id'],dM)
        elif dM.subtype == mpdu.ST_MGMT_ACTION:
            self._next = 'action'
            self._insertaction(fid,addrs[dM.addr1]['id'],addrs[dM.addr2]['id'],
                               addrs[dM.addr3]['id'],False,dM)
        elif dM.subtype == mpdu.ST_MGMT_ACTION_NOACK:
            self._next = 'actionoack'
            self._insertaction(fid,addrs[dM.addr1]['id'],addrs[dM.addr2]['id'],
                               addrs[dM.addr3]['id'],True,dM)

    def _insertassocreq(self,fid,client,ap,dM):
        """
         inserts the association req from client ot ap

         :param fid: frame id
         :param client: associating client id
         :param ap: access point id
         :param dM: mpdu dict
        """
        sql = """
               insert into assocreq (fid,client,ap,ess,ibss,cf_pollable,
                                     cf_poll_req,privacy,short_pre,pbcc,
                                     ch_agility,spec_mgmt,qos,short_slot,
                                     apsd,rdo_meas,dsss_ofdm,del_ba,imm_ba,
                                     listen_int,ssid,sup_rates,ext_rates,vendors)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                       %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
              """
        ssid = None
        ssids,sup_rs,ext_rs,vendors = extractie(dM)
        if len(ssids) == 1 and isutf8(ssids[0]): ssid = ssids[0]
        #if len(ssids) == 1:
        #    if isutf8(ssids[0]): ssid = ssids[0]
        #    else:
        #        self._icomms.put((self.cs,ts2iso(time.time()),'!THRESH_WARN!',"non utf-8 found in ssid"))
        else:
            self._icomms.put((self.cs,ts2iso(time.time()),'!THRESH_WARN!','multiple ssids in assocreq'))
        self._curs.execute(sql,(fid,client,ap,
                                dM.fixed_params['capability']['ess'],
                                dM.fixed_params['capability']['ibss'],
                                dM.fixed_params['capability']['cfpollable'],
                                dM.fixed_params['capability']['cf-poll-req'],
                                dM.fixed_params['capability']['privacy'],
                                dM.fixed_params['capability']['short-pre'],
                                dM.fixed_params['capability']['pbcc'],
                                dM.fixed_params['capability']['ch-agility'],
                                dM.fixed_params['capability']['spec-mgmt'],
                                dM.fixed_params['capability']['qos'],
                                dM.fixed_params['capability']['time-slot'],
                                dM.fixed_params['capability']['apsd'],
                                dM.fixed_params['capability']['rdo-meas'],
                                dM.fixed_params['capability']['dsss-ofdm'],
                                dM.fixed_params['capability']['delayed-ba'],
                                dM.fixed_params['capability']['immediate-ba'],
                                dM.fixed_params['listen-int'],
                                ssid,sup_rs,ext_rs,vendors))
        self._conn.commit()

    def _insertassocresp(self,assoc,fid,ap,client,dM):
        """
         inserts the (re)association resp from ap to client NOTE: Since both
         association response and reassociation response have the same format,
         they are saved to the same table identified by the type 'assoc'

         :param fid: frame id
         :param assoc: association type
         :param client: associating client id
         :param ap: access point id
         :param dM: mpdu dict
        """
        sql = """
               insert into assocresp (fid,client,ap,type,ess,ibss,cf_pollable,
                                      cf_poll_req,privacy,short_pre,pbcc,
                                      ch_agility,spec_mgmt,qos,short_slot,
                                      apsd,rdo_meas,dsss_ofdm,del_ba,imm_ba,
                                      status,aid,ssid,sup_rates,ext_rates,vendors)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                       %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
              """
        ssid = None
        ssids,sup_rs,ext_rs,vendors = extractie(dM)
        if len(ssids) == 1 and isutf8(ssids[0]): ssid = ssids[0]
        #if len(ssids) == 1:
        #    if isutf8(ssids[0]): ssid = ssids[0]
        #    else:
        #        self._icomms.put((self.cs,ts2iso(time.time()),'!THRESH_WARN!',"non utf-8 found in ssid"))
        else:
            self._icomms.put((self.cs,ts2iso(time.time()),'!THRESH_WARN!','multiple ssids in assocresp'))
        aid = dM.fixed_params['status-code'] if 'status-code' in dM.fixed_params else None
        self._curs.execute(sql,(fid,client,ap,assoc,
                                dM.fixed_params['capability']['ess'],
                                dM.fixed_params['capability']['ibss'],
                                dM.fixed_params['capability']['cfpollable'],
                                dM.fixed_params['capability']['cf-poll-req'],
                                dM.fixed_params['capability']['privacy'],
                                dM.fixed_params['capability']['short-pre'],
                                dM.fixed_params['capability']['pbcc'],
                                dM.fixed_params['capability']['ch-agility'],
                                dM.fixed_params['capability']['spec-mgmt'],
                                dM.fixed_params['capability']['qos'],
                                dM.fixed_params['capability']['time-slot'],
                                dM.fixed_params['capability']['apsd'],
                                dM.fixed_params['capability']['rdo-meas'],
                                dM.fixed_params['capability']['dsss-ofdm'],
                                dM.fixed_params['capability']['delayed-ba'],
                                dM.fixed_params['capability']['immediate-ba'],
                                dM.fixed_params['status-code'],aid,
                                ssid,sup_rs,ext_rs,vendors))
        self._conn.commit()

    def _insertreassocreq(self,fid,sid,ts,client,ap,dM):
        """
         inserts the reassociation req from the sta with id client to the ap with
         id ap, seen in frame fid w/ further details in dM into the db using the
         cursors curs

         :param fid: frame id
         :param sid: session id
         :param ts: frame timestamp
         :param client: requesting client
         :param ap: access point
         :param dM: mpdu dict
        """
        # entering sta CS
        # if we have a matching sta for cur ap or if we need to add one
        with self._l:
            curAP = dM.fixed_params['current-ap']
            self._curs.execute("select id from sta where mac=%s;",(curAP,))
            row = self._curs.fetchone()
            if row: curid = row[0]
            else:
                # not present, need to add it
                sql = """
                       insert into sta (sid,fid,spotted,mac,manuf)
                       values (%s,%s,%s,%s,%s) RETURNING id;
                      """
                self._curs.execute(sql,(sid,fid,ts,curAP,manufacturer(self._ouis,curAP)))
                curid = self._curs.fetchone()[0]
                self._conn.commit()

        # now insert the reassoc request
        sql = """
               insert into reassocreq (fid,client,ap,ess,ibss,cf_pollable,
                                       cf_poll_req,privacy,short_pre,pbcc,
                                       ch_agility,spec_mgmt,qos,short_slot,
                                       apsd,rdo_meas,dsss_ofdm,del_ba,imm_ba,
                                       listen_int,cur_ap,ssid,sup_rates,ext_rates,
                                       vendors)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                       %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
              """
        ssid = None
        ssids,sup_rs,ext_rs,vendors = extractie(dM)
        if len(ssids) == 1 and isutf8(ssids[0]): ssid = ssids[0]
        #if len(ssids) == 1:
        #    if isutf8(ssids[0]): ssid = ssids[0]
        #    else:
        #        self._icomms.put((self.cs,ts2iso(time.time()),'!THRESH_WARN!',"non utf-8 found in ssid"))
        else:
            self._icomms.put((self.cs,ts2iso(time.time()),'!THRESH_WARN!','multiple ssids in reassocreq'))
        self._curs.execute(sql,(fid,client,ap,
                                dM.fixed_params['capability']['ess'],
                                dM.fixed_params['capability']['ibss'],
                                dM.fixed_params['capability']['cfpollable'],
                                dM.fixed_params['capability']['cf-poll-req'],
                                dM.fixed_params['capability']['privacy'],
                                dM.fixed_params['capability']['short-pre'],
                                dM.fixed_params['capability']['pbcc'],
                                dM.fixed_params['capability']['ch-agility'],
                                dM.fixed_params['capability']['spec-mgmt'],
                                dM.fixed_params['capability']['qos'],
                                dM.fixed_params['capability']['time-slot'],
                                dM.fixed_params['capability']['apsd'],
                                dM.fixed_params['capability']['rdo-meas'],
                                dM.fixed_params['capability']['dsss-ofdm'],
                                dM.fixed_params['capability']['delayed-ba'],
                                dM.fixed_params['capability']['immediate-ba'],
                                dM.fixed_params['listen-int'],
                                curid,ssid,sup_rs,ext_rs,vendors))
        self._conn.commit()

    def _insertprobereq(self,fid,client,ap,dM):
        """
         inserts a probe request from sta. NOTE: the ap is usually a broadcast
         address and will not have an id

         :param fid: frame id
         :param client: requesting client id
         :param ap: access point id
         :param dM: mpdu dict
        """
        sql = """
               insert into probereq (fid,client,ap,ssid,sup_rates,ext_rates,vendors)
               values (%s,%s,%s,%s,%s,%s,%s);
              """
        ssid = None
        ssids,sup_rs,ext_rs,vendors = extractie(dM)
        if len(ssids) == 1 and isutf8(ssids[0]): ssid = ssids[0]
        #if len(ssids) == 1:
        #    if isutf8(ssids[0]): ssid = ssids[0]
        #    else:
        #        self._icomms.put((self.cs,ts2iso(time.time()),'!THRESH_WARN!',"non utf-8 found in ssid"))
        else:
            self._icomms.put((self.cs,ts2iso(time.time()),'!THRESH_WARN!','multiple ssids in probereq'))
        self._curs.execute(sql,(fid,client,ap,ssid,sup_rs,ext_rs,vendors))
        self._conn.commit()

    def _insertproberesp(self,fid,ap,client,dM):
        """
         inserts the proberesp from the ap to the client

         :param fid: frame id
         :param client: requesting client id
         :param ap: access point id
         :param dM: mpdu dict
        """
        sql = """
               insert into proberesp (fid,client,ap,beacon_ts,beacon_int,
                                      ess,ibss,cf_pollable,cf_poll_req,privacy,
                                      short_pre,pbcc,ch_agility,spec_mgmt,qos,
                                      short_slot,apsd,rdo_meas,dsss_ofdm,del_ba,
                                      imm_ba,ssid,sup_rates,ext_rates,vendors)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                       %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
              """
        beaconts = hex(dM.fixed_params['timestamp'])[2:] # store the hex (minus '0x')
        ssid = None
        ssids,sup_rs,ext_rs,vendors = extractie(dM)
        if len(ssids) == 1 and isutf8(ssids[0]): ssid = ssids[0]
        #if len(ssids) == 1:
        #    if isutf8(ssids[0]): ssid = ssids[0]
        #    else:
        #        self._icomms.put((self.cs,ts2iso(time.time()),'!THRESH_WARN!',"non utf-8 found in ssid"))
        else:
            self._icomms.put((self.cs,ts2iso(time.time()),'!THRESH_WARN!','multiple ssids in proberesp'))
        self._curs.execute(sql,(fid,client,ap,beaconts,
                                dM.fixed_params['beacon-int'],
                                dM.fixed_params['capability']['ess'],
                                dM.fixed_params['capability']['ibss'],
                                dM.fixed_params['capability']['cfpollable'],
                                dM.fixed_params['capability']['cf-poll-req'],
                                dM.fixed_params['capability']['privacy'],
                                dM.fixed_params['capability']['short-pre'],
                                dM.fixed_params['capability']['pbcc'],
                                dM.fixed_params['capability']['ch-agility'],
                                dM.fixed_params['capability']['spec-mgmt'],
                                dM.fixed_params['capability']['qos'],
                                dM.fixed_params['capability']['time-slot'],
                                dM.fixed_params['capability']['apsd'],
                                dM.fixed_params['capability']['rdo-meas'],
                                dM.fixed_params['capability']['dsss-ofdm'],
                                dM.fixed_params['capability']['delayed-ba'],
                                dM.fixed_params['capability']['immediate-ba'],
                                ssid,sup_rs,ext_rs,vendors))
        self._conn.commit()

    def _insertbeacon(self,fid,ap,dM):
        """
         inserts the beacon from the ap

         :param fid: fame id
         :param ap: access point id
         :param dM: mpdu dict
        """
        sql = """
               insert into beacon (fid,ap,beacon_ts,beacon_int,ess,ibss,
                                   cf_pollable,cf_poll_req,privacy,short_pre,
                                   pbcc,ch_agility,spec_mgmt,qos,short_slot,
                                   apsd,rdo_meas,dsss_ofdm,del_ba,imm_ba,
                                   ssid,sup_rates,ext_rates,vendors)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                       %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
              """
        beaconts = hex(dM.fixed_params['timestamp'])[2:] # store the hex (minus '0x')
        ssid = None
        ssids,sup_rs,ext_rs,vendors = extractie(dM)
        if len(ssids) == 1 and isutf8(ssids[0]): ssid = ssids[0]
        #if len(ssids) == 1:
        #    if isutf8(ssids[0]): ssid = ssids[0]
        #    else:
        #        self._icomms.put((self.cs,ts2iso(time.time()),'!THRESH_WARN!',"non utf-8 found in ssid"))
        else:
            self._icomms.put((self.cs,ts2iso(time.time()),'!THRESH_WARN!','multiple ssids in assocreq'))
        self._curs.execute(sql,(fid,ap,beaconts,
                                dM.fixed_params['beacon-int'],
                                dM.fixed_params['capability']['ess'],
                                dM.fixed_params['capability']['ibss'],
                                dM.fixed_params['capability']['cfpollable'],
                                dM.fixed_params['capability']['cf-poll-req'],
                                dM.fixed_params['capability']['privacy'],
                                dM.fixed_params['capability']['short-pre'],
                                dM.fixed_params['capability']['pbcc'],
                                dM.fixed_params['capability']['ch-agility'],
                                dM.fixed_params['capability']['spec-mgmt'],
                                dM.fixed_params['capability']['qos'],
                                dM.fixed_params['capability']['time-slot'],
                                dM.fixed_params['capability']['apsd'],
                                dM.fixed_params['capability']['rdo-meas'],
                                dM.fixed_params['capability']['dsss-ofdm'],
                                dM.fixed_params['capability']['delayed-ba'],
                                dM.fixed_params['capability']['immediate-ba'],
                                ssid,sup_rs,ext_rs,vendors))
        self._conn.commit()

    def _insertdisassaoc(self,fid,rx,tx,dM):
        """
         inserts the disassociation from tx to tx

         :param fid: frame id
         :param rx: id of receiving sta
         :param tx: id of transmitting sta
         :param dM: mpdu dict
        """
        # have to determine if this is coming from ap or from client and
        # set ap, client appropriately
        if dM.addr3 == dM.addr2:
            fromap = 1
            client = rx
            ap = tx
        else:
            fromap = 0
            client = tx
            ap = rx
        sql = """
               insert into disassoc (fid,client,ap,fromap,reason)
               values (%s,%s,%s,%s,%s);
              """
        self._curs.execute(sql,(fid,client,ap,fromap,dM.fixed_params['reason-code']))
        self._conn.commit()

    def _insertdeauth(self,fid,rx,tx,dM):
        """
         inserts the deauthentication frame from tx to rx

         :param fid: frame id
         :param rx: id of receiving sta
         :param tx: id of transmitting sta
         :param dM: mpdu dict
        """
        # have to determine if this is coming from ap or from client and
        # set ap, client appropriately
        if dM.addr3 == dM.addr2:
            fromap = 1
            client = rx
            ap = tx
        else:
            fromap = 0
            client = tx
            ap = rx
        sql = """
               insert into deauth (fid,client,ap,fromap,reason)
               values (%s,%s,%s,%s,%s);
              """
        self._curs.execute(sql,(fid,client,ap,fromap,dM.fixed_params['reason-code']))
        self._conn.commit()

    def _insertauth(self,fid,rx,tx,dM):
        """
         inserts the deauthentication frame from tx to rx

         :param fid: frame id
         :param rx: id of receiving sta
         :param tx: id of transmitting sta
         :param dM: mpdu dict
        """
        # have to determine if this is coming from ap or from client and
        # set ap, client appropriately
        if dM.addr3 == dM.addr2:
            fromap = 1
            client = rx
            ap = tx
        else:
            fromap = 0
            client = tx
            ap = rx
        sql = """
               insert into auth (fid,client,ap,fromap,auth_alg,auth_trans,status)
               values (%s,%s,%s,%s,%s,%s,%s);
              """
        self._curs.execute(sql,(fid,client,ap,fromap,dM.fixed_params['algorithm-no'],
                                dM.fixed_params['auth-seq'],
                                dM.fixed_params['status-code']))
        self._conn.commit()

    def _insertaction(self,fid,rx,tx,ap,noack,dM):
        """
         inserts the action frame

         :param fid: frame id
         :param rx: id of receiving sta
         :param tx: id of transmitting sta
         :param ap: access point id
         :param noack:
         :param dM: mpdu dict
        """
        # determine if this is from ap, to ap or intra sta
        if tx == ap: fromap = 1
        elif rx == ap: fromap = 0
        else: fromap = 2
        noack = int(noack)
        sql = """
               insert into action (fid,rx,tx,ap,fromap,noack,category,action,has_el)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s);
              """
        self._curs.execute(sql,(fid,rx,tx,ap,fromap,noack,
                                dM.fixed_params['category'],
                                dM.fixed_params['action'],
                                int('action-els' in dM.present)))
        self._conn.commit()