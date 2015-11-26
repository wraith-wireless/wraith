#!/usr/bin/env python

""" thresh.py: frame and metadata extraction and file writes

Provides Thresher and PCAPWriter:
 Thresher: processes of frames, stores frame data/metadata to DB.
 PCAPWriter: saves frames to file (if desired)

Each Process is configured to all for future commands (via tokens) to be used
to assist in any as of yet unidentified issues or future upgrades that may be
desired. Additionally, while each process will stop if given a token !STOP!,
the calling process i.e. the Collator can also send a SIGUSR1 signal to stop
the process out of order, that is preemptively
"""
__name__ = 'thresh'
__license__ = 'GPL v3.0'
__version__ = '0.0.4'
__date__ = 'October 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import os                                   # path/file functions
import signal                               # handle signals
import select                               # for select
import time                                 # timestamps
from struct import error as UnpackError     # struct unpack error
import multiprocessing as mp                # multiprocessing
import psycopg2 as psql                     # postgresql api
from Queue import Empty                     # queue empty exception
from wraith.utils.timestamps import ts2iso  # timestamp conversion
from dateutil import parser as dtparser     # parse out timestamps
from wraith.iyri.constants import NWRITE    # max packets to store before writing
from wraith.iyri.constants import N         # row size in buffer
from wraith.iyri.constants import MPDUPATH  # path to store bad frames
import wraith.wifi.radiotap as rtap         # 802.11 layer 1 parsing
from wraith.wifi import mpdu                # 802.11 layer 2 parsing
from wraith.wifi import mcs                 # mcs functions
from wraith.wifi import channels            # 802.11 channels/RFs
from wraith.wifi.oui import manufacturer    # oui functions
from wraith.utils import simplepcap as pcap # write frames to file

class PCAPWriter(mp.Process):
    """
     A PCAP writer is responsible for saving frames from one radio. This can be
     a bottleneck as multiple Threshers will be sending data and the frames
     will be out of order.
    """
    def __init__(self,comms,q,sid,mac,buff,dbstr,conf):
        """
         :param comms: internal communication (to Collator)
         :param q: task queue i.e frames to write
         :param sid: current session id
         :param mac: hwaddr of collecting radio
         :param buff: the buffer of frames to write
         :param dbstr: db connection string
         :param conf: configuration details
        """
        mp.Process.__init__(self)
        self._icomms = comms  # communications queue
        self._tasks = q       # write to/from Thresher and/or Collator
        self._conn = None     # db connection
        self._curs = None     # our cursor
        self._sid = sid       # current session id
        self._mac = mac       # hw addr of collecting radio
        self._buffer = buff   # the collecting radio's buffer
        self._stop = False    # stop flag
        self._path = ''       # file config variables
        self._private = False # data private
        self._sz = 0          # size limit
        self._pkts = []       # bulked packets
        self._npkt = 1        # cur packet number in file
        self._fout = None     # our file object
        self._setup(dbstr,conf)

    def terminate(self): pass

    @property
    def cs(self): return 'writer-%d' % self.pid

    def run(self):
        """ execution loop """
        # ignore signals used by main program
        signal.signal(signal.SIGINT,signal.SIG_IGN)   # CTRL-C and kill -INT stop
        signal.signal(signal.SIGTERM,signal.SIG_IGN)  # kill -TERM stop
        signal.signal(signal.SIGUSR1,self.stop)       # kill signal from Collator

        # notify collator we're up
        self._icomms.put((self.cs,ts2iso(time.time()),'!WRITE!',self.pid))

        # loop until told to quit
        while not self._stop:
            try:
                ts1 = ts2iso(time.time()) # our timestamp
                tkn,ts,d = self._tasks.get(1.0)
                if tkn == '!STOP!': self._stop = True
                elif tkn == '!FRAME!':
                    fid,ix,b,l,r = d # frame id,index,bytes,left, right
                    f = self._buffer[(ix*N):(ix*N)+b].tobytes()
                    if self._private and l < r: f = f[:l] + f[r:]
                    self._pkts.append((ts,fid,f))
                    if len(self._pkts) > NWRITE: self._writepkts()
                else:
                    msg = "invalid token %s" % tkn
                    self._icomms.put((self.cs,ts1,'!WRITE_ERR!',msg))
            except Empty: pass
            except (IndexError,ValueError):
                self._icomms.put((self.cs,ts1,'!WRITE_ERR!',"Invalid arguments"))
            except Exception as e:
                msg = "%s: %s" % (type(e).__name__,e)
                self._icomms.put((self.cs,ts1,'!WRITE_ERR!',msg))

        # are there unwritten packets?
        if len(self._pkts) > 0: self._writepkts()

        # notify Collator we're down
        if self._curs: self._curs.close()
        if self._conn: self._conn.close()
        self._icomms.put((self.cs,ts2iso(time.time()),'!WRITE!',None))

    def stop(self,signum=None,stack=None): self._stop = True

    def _writepkts(self):
        """ write all packets to file """
        # get a timestamp & cs
        cs = 'writer-%d' % self.pid
        ts = ts2iso(time.time())

        # wrap everything in a try block & reset all when done
        try:
            # open a new file sid_timestamp_hwaddr.pcap
            if not self._fout:
                fname = os.path.join(self._path,"%d_%s_%s.pcap" % (self._sid,
                                                                   self._pkts[0][0],
                                                                   self._mac))
                self._fout = pcap.pcapopen(fname)
                self._icomms.put((cs,ts,'!WRITE_OPEN!',"%s opened for writing" % fname))

            # write each packet, then reset the packet list
            for i,pkt in enumerate(self._pkts):
                pcap.pktwrite(self._fout,pkt[0],pkt[2])
                sql = "insert into frame_path (fid,filepath,n) values (%s,%s,%s);"
                self._curs.execute(sql,(pkt[1],self._fout.name,self._npkt))
                self._npkt += 1
            self._pkts = []

            # close file if it exceeds the max
            if self._fout and os.path.getsize(self._fout.name) > self._sz:
                self._icomms.put((cs,ts,'!WRITE_DONE!',"Closing %s. Wrote %d packets" % (self._fout.name,self._npkt)))
                self._fout.close()
                self._fout = None
                self._npkt = 1
        except psql.OperationalError as e: # unrecoverable
            self._icomms.put((cs,ts,'!THRESH_ERR!',"DB: %s->%s" % (e.pgcode,e.pgerror)))
        except pcap.PCAPException as e:
            self._icomms.put((cs,ts,'!THRESH_ERR!',"File Error: %s" % e))
        except psql.Error as e: # possible incorrect semantics/syntax
            self._conn.rollback()
            self._icomms.put((cs,ts,'!THRESH_WARN!',"SQL: %s->%s" % (e.pgcode,e.pgerror)))
        except Exception as e:
            self._icomms.put((cs,ts,'!THRESH_WARN!',"%s: %s" % (type(e).__name__,e)))
        else:
            self._conn.commit()

    def _setup(self,dbstr,conf):
        """
         connect to database & initialize variables

         :param dbstr: database connection string
         :param conf: configuration database
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

            # set save parameters
            self._path = conf['path']
            self._private = conf['private']
            self._sz = conf['sz']
        except Exception as e:
            if self._curs:
                self._conn.rollback()
                self._curs.close()
            if self._conn: self._conn.close()
            raise RuntimeError(e)

def extractie(dM):
    """
     extracts info-elements for ssid, supported rates, extended rates & vendors

     :param dM: mpdu dict
     :returns: ssid,supported_rates,extended_rates,vendors
    """
    ssid = None
    ss = []
    es = []
    vs = []
    for ie in dM.info_els:
        if ie[0] == mpdu.EID_SSID: ssid = ie[1]
        if ie[0] == mpdu.EID_SUPPORTED_RATES: ss = ie[1]
        if ie[0] == mpdu.EID_EXTENDED_RATES: es = ie[1]
        if ie[0] == mpdu.EID_VEND_SPEC: vs.append(ie[1][0])
    return ssid,ss,es,vs

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
         :param abad: tuple t = (AbadBuffer,AbadWriterQueue)
         :param shama: tuple t = (ShamaBuffer,ShamaWriterQueue)
         :param dbstr: db connection string
         :param ouis: oui dict
        """
        mp.Process.__init__(self)
        self._icomms = comms # communications queue
        self._tasks = q      # connection from Collator
        self._cC = conn      # token connection from Collator
        self._abad = abad    # abad tuple
        self._shama = shama  # shama tuple
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
    def cs(self): return 'thresher-%d' % self.pid

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
                        rdos[d[0]] = {'role':d[1],'buffer':None,'writer':None}
                        if d[1] == 'abad':
                            rdos[d[0]]['buffer'] = self._abad[0]
                            rdos[d[0]]['writer'] = self._abad[1]
                        elif d[1] == 'shama':
                            rdos[d[0]]['buffer'] = self._shama[0]
                            rdos[d[0]]['writer'] = self._shama[1]
                        else:
                            self._icomms.put((self.cs,ts1,'!THRESH_WARN!',"Role %s" %d[1]))
                    elif tkn == '!WRITE!':
                        if d[0]: self._write = True
                        elif not d[0]: self._write = False
                    elif tkn == '!FRAME!':
                        self._processframe(sid,rdos,ts,ts1,d)
                    else:
                        msg = "invalid token %s" % tkn
                        self._icomms.put((self.cs,ts1,'!THRESH_WARN!',msg))
                except (IndexError,ValueError):
                    msg = "invalid arguments (%s) for %s" % (','.join([str(x) for x in d]),tkn)
                    self._icomms.put((self.cs,ts1,'!THRESH_WARN!',msg))
                except KeyError as e:
                    msg = "invalid radio hwaddr: %s" % e
                    self._icomms.put((self.cs,ts1,'!THRESH_WARN!',msg))
                except Exception as e:
                    msg = "%s: %s" % (type(e).__name__,e)
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
        except mpdu.MPDUException: # mpdu failed - initialize empty mpdu
            validMPDU = False
            vs = (sid,ts,lF,dR['sz'],0,[dR['sz'],lF],dR['flags'],
                  int('a-mpdu' in dR['present']),rtap.flags_get(dR['flags'],'fcs'))
        except UnpackError as e: # uncaught parsing error (most likely mpdu)
            if not dR: msg = 'Unpack error in radiotap at %d: %s' % (ix,f)
            else: msg = 'Unpack error in mpdu at %d: %s' % (ix,f)
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

            # pass fid, index, nBytes, left, right indices to writer
            if self._write:
                l = r = 0
                if validRTAP: l += dR['sz']
                if validMPDU:
                    l += dM.offset
                    r = lF-dM.stripped
                rdos[src]['writer'].put(('!FRAME!',ts,[fid,ix,b,l,r]))

            # NOTE: the next two "parts" storing and extracting are mutually
            # exlusive & are required to occur sequentially, thus could be
            # handled by threads/processes

            # (1) store frame details in db
            self._next = 'store'
            self._insertrtap(fid,src,dR)
            if not dM.isempty: self._insertmpdu(fid,dM)

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

            # further process management frames
            if dM.isempty:
                msg = ''
                try:
                    fname = os.path.join(MPDUPATH,"bad%d.pcap" % fid)
                    fout = pcap.pcapopen(fname)
                    pcap.pktwrite(fout,ts,f)
                    fout.close()
                    msg = "Bad MPDU in %d. Wrote to %s" % (fid,fname)
                except:
                    msg = "Bad MPDU in %d. %s" % (fid,f)
                self._icomms.put((self.cs,ts1,'!THRESH_WARN!',msg))
                return

            # further process mgmt frames
            self._next = 'mgmt'
            if dM.type == mpdu.FT_MGMT: self._processmgmt(fid,sid,ts,addrs,dM)
        except psql.OperationalError as e: # unrecoverable
            if not fid:
                msg = "Failed to insert frame: %s: %s. %s" % (e.pgcode,e.pgerror,f)
            else:
                msg = "Frame %d insert failed at %s:. %s: %s. %s" % (fid,self._next,e.pgcode,e.pgerror,f)
            self._icomms.put((self.cs,ts1,'!THRESH_ERR!',msg))
        except psql.Error as e:
            self._conn.rollback()
            if not fid:
                msg = "Failed to insert frame: %s: %s. %s" % (e.pgcode,e.pgerror,f)
            else:
                msg = "Frame %d failed at %s. %s: %s. %s" % (fid,self._next,e.pgcode,e.pgerror,f)
            self._icomms.put((self.cs,ts1,'!THRESH_WARN!',msg))
        except Exception as e:
            self._conn.rollback()
            if not fid:
                msg = "Failed to insert frame: %s: %s. %s" % (type(e).__name__,e,f)
            else:
                msg = "Frame %d failed at %s. %s: %s. %s" % (fid,self._next,type(e).__name__,e,f)
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
        ssid,sup_rs,ext_rs,vendors = extractie(dM)
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
        aid = dM.fixed_params['status-code'] if 'status-code' in dM.fixed_params else None
        ssid,sup_rs,ext_rs,vendors = extractie(dM)
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
        ssid,sup_rs,ext_rs,vendors = extractie(dM)
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
        ssid,sup_rs,ext_rs,vendors = extractie(dM)
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
        ssid,sup_rs,ext_rs,vendors = extractie(dM)
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
        ssid,sup_rs,ext_rs,vendors = extractie(dM)
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