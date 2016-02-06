#!/usr/bin/env python

""" thresh.py: frame and metadata extraction and file writes

Processings of frames, stores frame data/metadata to DB.
"""
__name__ = 'thresh'
__license__ = 'GPL v3.0'
__version__ = '0.0.5'
__date__ = 'January 2016'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import signal                                      # handle signals
import select                                      # for select
import multiprocessing as mp                       # multiprocessing
import psycopg2 as psql                            # postgresql api
from dateutil import parser as dtparser            # parse out timestamps
from wraith.utils.timestamps import isots          # converted timestamp
import wraith.wifi.standards.radiotap as rtap      # 802.11 layer 1 parsing
from wraith.wifi.standards import mpdu             # 802.11 layer 2 parsing
from wraith.wifi.standards import mcs              # mcs functions
from wraith.wifi.standards import channels         # 802.11 channels/RFs
from wraith.wifi.interface.oui import manufacturer # oui functions
from wraith.utils.valrep import tb                 # for traceback
from wraith.iyri.constants import *                # constants

class Thresher(mp.Process):
    """ Thresher process frames and inserts frame data in database """
    def __init__(self,comms,q,conn,lSta,buff,dbstr,ouis):
        """
         :param comms: internal communication (to Collator)
         :param q: task queue from Collator
         :param conn: token connection from Collator
         :param lSta: lock for sta and sta activity inserts/updates
         :param buff: buffer
         :param dbstr: db connection string
         :param ouis: oui dict
        """
        mp.Process.__init__(self)
        self._icomms = comms  # communications queue
        self._tasks = q       # connection from Collator
        self._cC = conn       # token connection from Collator
        self._buff = buff     # frame buffer
        self._conn = None     # db connection
        self._l = lSta        # sta lock
        self._curs = None     # our cursor
        self._ouis = ouis     # oui dict
        self._next = None     # next operation to execute
        self._setup(dbstr)

    def terminate(self): pass

    @property
    def cs(self): return 'thresher-{0}'.format(self.pid)

    def run(self):
        """ execute frame process loop """
        # ignore signals used by main program & add signal for stop
        signal.signal(signal.SIGINT,signal.SIG_IGN)   # CTRL-C and kill -INT stop
        signal.signal(signal.SIGTERM,signal.SIG_IGN)  # kill -TERM stop

        # local variables
        sid = None   # current session id
        rdos = {}    # radio map hwaddr->write = oneof {True|False}
        stop = False # stop flag

        # notify collator we're up
        self._icomms.put((self.cs,isots(),THRESH_THRESH,self.pid))

        while not stop:
            try:
                # do not check task queue until sid has been set
                ins = [self._cC,self._tasks._reader] if sid else [self._cC]
                (rs,_,_ )= select.select(ins,[],[])
            except select.error as e: # hide (4,'Interupted system call') errors
                if e[0] == 4: continue
                rs = []

            # get each message
            for r in rs:
                try:
                    # get & process data
                    if r == self._cC: (tkn,ts,d) = self._cC.recv()
                    else: (tkn,ts,d) = self._tasks.get(0.5)
                    if tkn == POISON: stop = True
                    elif tkn == COL_SID: sid = d[0]
                    elif tkn == COL_RDO: rdos[d[0]] = False
                    elif tkn == COL_WRITE: rdos[d[0]] = d[1]
                    elif tkn == COL_FRAME: self._processframe(sid,rdos,ts,d)
                except Exception as e:
                    # blanket exception, catch all and notify collator
                    msg = "{0} {1}\n{2}".format(type(e).__name__,e,tb())
                    self._icomms.put((self.cs,isots(),THRESH_WARN,(msg,None)))

        # notify collector we're down
        if self._curs: self._curs.close()
        if self._conn: self._conn.close()
        self._icomms.put((self.cs,isots(),THRESH_THRESH,None))

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

    def _processframe(self,sid,rdos,ts,d):
        """
         inserts frame into db
         :param sid: session id
         :param rdos: radio dict
         :param ts: timestamp of frame
         :param d:  data
        """
        # (1) pull frame off the buffer & notify Collator
        src = idx = b = None
        try:
            src,idx,b = d # hwaddr,index,nBytes
            f = self._buff[(idx*DIM_N):(idx*DIM_N)+b].tobytes()
            self._icomms.put((self.cs,isots(),THRESH_DQ,(None,idx)))
        except ValueError:
            self._icomms.put((self.cs,isots(),THRESH_ERR,'Bad Data'))
            return
        except Exception as e:
            tr = tb()
            te = type(e).__name__
            if not src:
                msg = "Failed extracting data: {0}->{1}\n{2}".format(te,e,tr)
                self._icomms.put((self.cs,isots(),THRESH_ERR,(msg,None)))
            else:
                msg = "Failed extracting frame: {0}->{1}\n{2}".format(te,e,tr)
                self._icomms.put((self.cs,isots(),THRESH_ERR,(msg,idx)))
            return

        # (2) parse the frame
        fid = None       # set an invalid frame id
        dR = {}          # make an empty rtap dict
        dM = mpdu.MPDU() # & an empty mpdu dict
        try:
            lF = len(f)
            dR = rtap.parse(f)
            dM = mpdu.parse(f[dR['sz']:],rtap.flags_get(dR['flags'],'fcs'))
            vs = (sid,ts,lF,dR['sz'],dM.offset,[(dR['sz']+dM.offset),(lF-dM.stripped)],
                  dR['flags'],int('a-mpdu' in dR['present']),
                  rtap.flags_get(dR['flags'],'fcs'))
        except rtap.RadiotapException as e:
            # parsing failed @ radiotap, set empty vals & alert Collator
            msg = "Parsing failed at radiotap: {0} in buffer[{1}]".format(e,idx)
            self._icomms.put((self.cs,isots(),THRESH_WARN,(msg,None)))
            vs = (sid,ts,lF,0,0,[0,lF],0,0,0)
            dR['err'] = e
        except mpdu.MPDUException as e:
            # mpdu failed - initialize empty mpdu vals & alert Collator
            msg = "Parsing failed at mpdu: {0} in buffer[{1}]".format(e,idx)
            self._icomms.put((self.cs,isots(),THRESH_WARN,(msg,None)))
            vs = (sid,ts,lF,dR['sz'],0,[dR['sz'],lF],dR['flags'],
                  int('a-mpdu' in dR['present']),rtap.flags_get(dR['flags'],'fcs'))
        except Exception as e: # blanket error
            msg = "Parsing Error. {0} {1}\n{2}".format(type(e).__name__,e,tb())
            self._icomms.put((self.cs,isots(),THRESH_WARN,(msg,idx)))
            return

        # (3) store the frame
        # NOTE: individual helper functions will commit database inserts/updates
        # but allow exceptions to fall through as db errors will be caught in this
        # try & rollbacks will be executed here
        try:
            # insert the frame and get frame's id
            self._next = 'frame'
            sql = """
                   insert into frame (sid,ts,bytes,bRTAP,bMPDU,data,flags,ampdu,fcs)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s) returning frame_id;
                  """
            self._curs.execute(sql,vs)
            fid = self._curs.fetchone()[0]
            self._conn.commit()

            # write raw bytes if specified
            if rdos[src]:
                self._next = 'frame_raw'
                sql = "insert into frame_raw (fid,raw) values (%s,%s);"
                self._curs.execute(sql,(fid,psql.Binary(f)))
                self._conn.commit()

            # insert radiotap and/or malformed if we had any issues
            self._next = 'radiotap'
            if not 'err' in dR: self._insertrtap(fid,src,dR)
            else:
                sql = """
                       insert into malformed (fid,location,reason)
                       values (%s,%s,%s);
                      """
                self._curs.execute(sql,(fid,'radiotap',dR['err']))
                self._conn.commit()

            # insert mpdu and malfored (if it exists)
            for err in dM.error:
                sql = """
                       insert into malformed (fid,location,reason)
                       values (%s,%s,%s);
                      """
                self._curs.execute(sql,(fid,err[0],err[1]))
                self._conn.commit()

                # notify collator, but we want to continue attempting to store
                # as much as possible so set src and index to None
                msg = "Frame {0}. Bad MPDU {1}".format(fid,err)
                self._icomms.put((self.cs,isots(),THRESH_WARN,(msg,None)))

            # (a) store frame details in db

            if not dM.isempty:
                self._next = 'mpdu'
                self._insertmpdu(fid,dM)

                # (b) extract
                self._next = 'extract'

                # pull unique addresses of stas from mpdu into the addr dict
                # having the form: <hwaddr>->{'loc:[<i..n>], where i=1..4
                #                             'id':<sta_id>}
                # NOTE: insertsta modifies the addrs dict in place assigning ids
                # to each nonbroadcast address
                # sta addresses
                # Fct        To From    Addr1    Addr2  Addr3  Addr4
                # IBSS/Intra  0    0    RA=DA    TA=SA  BSSID    N/A
                # From AP     0    1    RA=DA TA=BSSID     SA    N/A
                # To AP       1    0 RA=BSSID    TA=SA     DA    N/A
                # Wireless DS 1    1 RA=BSSID TA=BSSID DA=WDS SA=WDS
                addrs = {}
                for i,a in enumerate(['addr1','addr2','addr3','addr4']):
                    if not a in dM: break
                    if dM[a] in addrs: addrs[dM[a]]['loc'].append(i+1)
                    else: addrs[dM[a]] = {'loc':[i+1],'id':None}

                # insert the sta, sta_activity
                self._insertsta(fid,sid,ts,addrs)
                self._insertsta_activity(sid,ts,addrs)

                # further process mgmt frames?
                if dM.type == mpdu.FT_MGMT:
                    self._next = 'mgmt'
                    self._processmgmt(fid,sid,ts,addrs,dM)

            # notify collator, we're done
            self._icomms.put((self.cs,isots(),THRESH_DONE,(None,idx)))
        except psql.OperationalError as e: # unrecoverable
            # NOTE: for now we do not exit on unrecoverable error but allow
            # collator to send the poison pill
            self._conn.rollback()
            args = (fid,self._next,e.pgcode,e.pgerror)
            msg = "<PSQL> Frame {0} failed at {1}. {2}->{3}.".format(*args)
            self._icomms.put((self.cs,isots(),THRESH_ERR,(msg,idx)))
        except psql.Error as e:
            # rollback to avoid db errors
            self._conn.rollback()
            args = (fid,self._next,e.pgcode,e.pgerror)
            msg = "<PSQL> Frame {0} failed at {1}. {2}->{3}.".format(*args)
            self._icomms.put((self.cs,isots(),THRESH_WARN,(msg,idx)))
        except Exception as e:
            self._conn.commit() # commit anything that may be pending
            args = (fid,self._next,type(e).__name__,e,tb())
            msg = "<UNK> Frame {0} failed at {1}. {2}->{3}\n{4}.".format(*args)
            self._icomms.put((self.cs,isots(),THRESH_WARN,(msg,idx)))

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
        if not dM.crypt: return
        if dM.crypt['type'] == 'wep':
            self._next = 'wepcrypt'
            sql = "insert into wepcrypt (fid,iv,key_id,icv) values (%s,%s,%s,%s);"
            self._curs.execute(sql,(fid,psql.Binary(dM.crypt['iv']),
                                        dM.crypt['key-id'],
                                        psql.Binary(dM.crypt['icv'])))
        elif dM.crypt['type'] == 'tkip':
            self._next = 'tkipcrypt'
            sql = """
                   insert into tkipcrypt (fid,tsc1,wepseed,tsc0,key_id,
                                          tsc2,tsc3,tsc4,tsc5,mic,icv)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
                  """
            self._curs.execute(sql,(fid,psql.Binary(dM.crypt['iv']['tsc1']),
                                        psql.Binary(dM.crypt['iv']['wep-seed']),
                                        psql.Binary(dM.crypt['iv']['tsc0']),
                                        dM.crypt['iv']['key-id']['key-id'],
                                        psql.Binary(dM.crypt['ext-iv']['tsc2']),
                                        psql.Binary(dM.crypt['ext-iv']['tsc3']),
                                        psql.Binary(dM.crypt['ext-iv']['tsc4']),
                                        psql.Binary(dM.crypt['ext-iv']['tsc5']),
                                        psql.Binary(dM.crypt['mic']),
                                        psql.Binary(dM.crypt['icv'])))
        elif dM.crypt['type'] == 'ccmp':
            self._next = 'ccmpcrypt'
            sql = """
                   insert into ccmpcrypt (fid,pn0,pn1,key_id,pn2,pn3,pn4,pn5,mic)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s);
                  """
            self._curs.execute(sql,(fid,psql.Binary(dM.crypt['pn0']),
                                            psql.Binary(dM.crypt['pn1']),
                                            dM.crypt['key-id']['key-id'],
                                            psql.Binary(dM.crypt['pn2']),
                                            psql.Binary(dM.crypt['pn3']),
                                            psql.Binary(dM.crypt['pn4']),
                                            psql.Binary(dM.crypt['pn5']),
                                            psql.Binary(dM.crypt['mic'])))
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

    def _insertsta_activity(self,sid,ts,addrs):
        """
         inserts activity of all stas in db
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
                    # we have to convert the frame ts to a datatime obj w/ tz
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
                                     apsd,sw_meas,dsss_ofdm,del_ba,imm_ba,
                                     listen_int,sup_rates,ext_rates,vendors)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                       %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
              """
        ssids,ss,xs,vs = dM.getie([mpdu.EID_SSID,mpdu.EID_SUPPORTED_RATES,
                                   mpdu.EID_EXTENDED_RATES,mpdu.EID_VEND_SPEC])
        os = [] # add unique vendor oui
        for v in vs:
            if v[0] not in os: os.append(v[0])
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
                                ss,xs,os))
        self._conn.commit()

        # now the ssids
        sql = "insert into ssid (fid,valid,invalid,isvalid) values (%s,%s,%s,%s);"
        for ssid in ssids:
            try:
                if mpdu.validssid(ssid):
                    valid = ssid
                    invalid = None
                    isvalid = 1
                else:
                    valid = None
                    invalid = psql.Binary(ssid)
                    isvalid = 0
                self._curs.execute(sql,(fid,valid,invalid,isvalid))
            except:
                raise
            else:
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
                                      status,aid,sup_rates,ext_rates,vendors)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                       %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
              """
        ssids,ss,xs,vs = dM.getie([mpdu.EID_SSID,mpdu.EID_SUPPORTED_RATES,
                                   mpdu.EID_EXTENDED_RATES,mpdu.EID_VEND_SPEC])
        os = [] # add unique vendor oui
        for v in vs:
            if v[0] not in os: os.append(v[0])
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
                                dM.fixed_params['status-code'],
                                aid,ss,xs,os))
        self._conn.commit()

        # now the ssids
        sql = "insert into ssid (fid,valid,invalid,isvalid) values (%s,%s,%s,%s);"
        for ssid in ssids:
            try:
                if mpdu.validssid(ssid):
                    valid = ssid
                    invalid = None
                    isvalid = 1
                else:
                    valid = None
                    invalid = psql.Binary(ssid)
                    isvalid = 0
                self._curs.execute(sql,(fid,valid,invalid,isvalid))
            except:
                raise
            else:
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
                                       listen_int,cur_ap,sup_rates,ext_rates,
                                       vendors)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                       %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
              """
        ssids,ss,xs,vs = dM.getie([mpdu.EID_SSID,mpdu.EID_SUPPORTED_RATES,
                                   mpdu.EID_EXTENDED_RATES,mpdu.EID_VEND_SPEC])
        os = [] # add unique vendor oui
        for v in vs:
            if v[0] not in os: os.append(v[0])
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
                                curid,ss,xs,vs))
        self._conn.commit()

        # now the ssids
        sql = "insert into ssid (fid,valid,invalid,isvalid) values (%s,%s,%s,%s);"
        for ssid in ssids:
            try:
                if mpdu.validssid(ssid):
                    valid = ssid
                    invalid = None
                    isvalid = 1
                else:
                    valid = None
                    invalid = psql.Binary(ssid)
                    isvalid = 0
                self._curs.execute(sql,(fid,valid,invalid,isvalid))
            except:
                raise
            else:
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
               insert into probereq (fid,client,ap,sup_rates,ext_rates,vendors)
               values (%s,%s,%s,%s,%s,%s);
              """
        ssids,ss,xs,vs = dM.getie([mpdu.EID_SSID,mpdu.EID_SUPPORTED_RATES,
                                   mpdu.EID_EXTENDED_RATES,mpdu.EID_VEND_SPEC])
        os = [] # add unique vendor oui
        for v in vs:
            if v[0] not in os: os.append(v[0])
        self._curs.execute(sql,(fid,client,ap,ss,xs,os))
        self._conn.commit()

        # now the ssids
        sql = "insert into ssid (fid,valid,invalid,isvalid) values (%s,%s,%s,%s);"
        for ssid in ssids:
            try:
                if mpdu.validssid(ssid):
                    valid = ssid
                    invalid = None
                    isvalid = 1
                else:
                    valid = None
                    invalid = psql.Binary(ssid)
                    isvalid = 0
                self._curs.execute(sql,(fid,valid,invalid,isvalid))
            except:
                raise
            else:
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
                                      imm_ba,sup_rates,ext_rates,vendors)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                       %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
              """
        ssids,ss,xs,vs = dM.getie([mpdu.EID_SSID,mpdu.EID_SUPPORTED_RATES,
                                   mpdu.EID_EXTENDED_RATES,mpdu.EID_VEND_SPEC])
        os = [] # add unique vendor oui
        for v in vs:
            if v[0] not in os: os.append(v[0])
        self._curs.execute(sql,(fid,client,ap,dM.fixed_params['timestamp'],
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
                                ss,xs,os))
        self._conn.commit()

        # now the ssids
        sql = "insert into ssid (fid,valid,invalid,isvalid) values (%s,%s,%s,%s);"
        for ssid in ssids:
            try:
                if mpdu.validssid(ssid):
                    valid = ssid
                    invalid = None
                    isvalid = 1
                else:
                    valid = None
                    invalid = psql.Binary(ssid)
                    isvalid = 0
                self._curs.execute(sql,(fid,valid,invalid,isvalid))
            except:
                raise
            else:
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
                                   sup_rates,ext_rates,vendors)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                       %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
              """
        ssids,ss,xs,vs = dM.getie([mpdu.EID_SSID,mpdu.EID_SUPPORTED_RATES,
                                   mpdu.EID_EXTENDED_RATES,mpdu.EID_VEND_SPEC])
        os = [] # add unique vendor oui
        for v in vs:
            if v[0] not in os: os.append(v[0])
        self._curs.execute(sql,(fid,ap,dM.fixed_params['timestamp'],
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
                                ss,xs,os))
        self._conn.commit()

        # now the ssids
        self._next = 'ssids'
        sql = "insert into ssid (fid,valid,invalid,isvalid) values (%s,%s,%s,%s);"
        for ssid in ssids:
            try:
                if mpdu.validssid(ssid):
                    valid = ssid
                    invalid = None
                    isvalid = 1
                else:
                    valid = None
                    invalid = psql.Binary(ssid)
                    isvalid = 0
                self._curs.execute(sql,(fid,valid,invalid,isvalid))
            except:
                raise
            else:
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
               insert into act (fid,rx,tx,ap,fromap,noack,category,act_code,has_el)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s);
              """
        self._curs.execute(sql,(fid,rx,tx,ap,fromap,noack,
                                dM.fixed_params['category'],
                                dM.fixed_params['action'],
                                int('action-els' in dM.present)))
        self._conn.commit()