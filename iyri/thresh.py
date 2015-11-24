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
from wraith.iyri.constants import NWRITE    # max packets to store before writing
from wraith.iyri.constants import N         # row size in buffer
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

    def run(self):
        """ execution loop """
        # ignore signals used by main program
        signal.signal(signal.SIGINT,signal.SIG_IGN)   # CTRL-C and kill -INT stop
        signal.signal(signal.SIGTERM,signal.SIG_IGN)  # kill -TERM stop
        signal.signal(signal.SIGUSR1,self.stop)       # kill signal from Collator

        # local variables
        cs = 'writer-%d' % self.pid # our callsign

        # notify collator we're up
        self._icomms.put((cs,ts2iso(time.time()),'!WRITE!',self.pid))

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
                    self._icomms.put((cs,ts1,'!WRITE_ERR!',"invalid token %s" % tkn))
            except Empty: pass
            except (IndexError,ValueError):
                self._icomms.put((cs,ts1,'!WRITE_ERR!',"Invalid arguments"))
            except Exception as e:
                self._icomms.put((cs,ts1,'!WRITE_ERR!',"%s: %s" % (type(e).__name__,e)))

        # are there unwritten packets?
        if len(self._pkts) > 0: self._writepkts()

        # notify Collator we're down
        if self._curs: self._curs.close()
        if self._conn: self._conn.close()
        self._icomms.put((cs,ts2iso(time.time()),'!WRITE!',None))

    def stop(self,signum=None,stack=None): self._stop = True

    def _writepkts(self):
        """ write all packets to file """
        # get a timestamp & cs
        cs = 'writer-%d' % self.pid
        ts = ts2iso(time.time())

        # wrap everything in a try block& reset all when done
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

    def run(self):
        """ execute frame process loop """
        # ignore signals used by main program
        signal.signal(signal.SIGINT,signal.SIG_IGN)   # CTRL-C and kill -INT stop
        signal.signal(signal.SIGTERM,signal.SIG_IGN)  # kill -TERM stop
        signal.signal(signal.SIGUSR1,self.stop)       # kill signal from Collator

        # local variables
        cs = 'thresher-%d' % self.pid # our callsign
        sid = None                    # current session id
        rdos = {}                     # radio map hwaddr{'role','buffer','writer'}
        ouis = {}                     # oui dict

        # notify collator we're up
        self._icomms.put((cs,ts2iso(time.time()),'!THRESH!',self.pid))

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
                            self._icomms.put((cs,ts1,'!THRESH_WARN!',"Invalid role %s" %d[1]))
                    elif tkn == '!WRITE!':
                        if d[0]: self._write = True
                        elif not d[0]: self._write = False
                    elif tkn == '!FRAME!':
                        # extract frame details & get frame from buffer
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
                        except rtap.RadiotapException:
                            # the parsing failed at radiotap, set insert values to empty
                            validRTAP = validMPDU = False
                            vs = (sid,ts,lF,0,0,[0,lF],0,'none',0)
                        except mpdu.MPDUException:
                            # the radiotap was valid but mpdu failed - initialize empty mpdu
                            validMPDU = False
                            vs = (sid,ts,lF,dR['sz'],0,[dR['sz'],lF],dR['flags'],
                                  int('a-mpdu' in dR['present']),
                                  rtap.flags_get(dR['flags'],'fcs'))
                        except UnpackError as e:
                            # parsing uncaught error (most likely mpdu)
                            msg = 'bad frame at %d: %s' % (ix,f)
                            self._icomms.put((cs,ts1,'!THRESH_WARN!',msg))
                            continue
                        else:
                            vs = (sid,ts,lF,dR['sz'],dM.offset,
                                  [(dR['sz']+dM.offset),(lF-dM.stripped)],dR['flags'],
                                  int('a-mpdu' in dR['present']),
                                  rtap.flags_get(dR['flags'],'fcs'))

                        # insert the frame
                        fid = None

                        # In the below, individual helper functions will commit
                        # database inserts/updates. All db errors will be caught
                        # in this try block and rollbacks will be executed here
                        try:
                            # setup next and fake fid
                            self._next = 'frame'

                            # insert the frame and get frame's id
                            sql = """
                                   insert into frame (sid,ts,bytes,bRTAP,bMPDU,
                                                      data,flags,ampdu,fcs)
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

                            # NOTE: the next two "parts" storing and extracting
                            # are mutually exlusive and do not need to happen in
                            # any order & could be handled by threads/processes

                            # store frame details in db
                            self._next = 'store'
                            self._insertrtap(fid,src,dR)           # radiotap related
                            if dM.offset: self._insertmpdu(fid,dM) # mpdu related

                            # store extracted 'metadata'
                            self._next = 'extract'
                            # sta addresses
                            # Fct        To From    Addr1    Addr2  Addr3  Addr4
                            # IBSS/Intra  0    0    RA=DA    TA=SA  BSSID    N/A
                            # From AP     0    1    RA=DA TA=BSSID     SA    N/A
                            # To AP       1    0 RA=BSSID    TA=SA     DA    N/A
                            # Wireless DS 1    1 RA=BSSID TA=BSSID DA=WDS SA=WDS

                            # extract unique addresses of stas in the mpdu into the
                            # addr dict having the form:
                            # <hwaddr>->{'loc:[<i..n>], where i=1..4
                            #            'id':<sta_id>}
                            addrs = {}
                            for i,a in enumerate(['addr1','addr2','addr3','addr4']):
                                if not a in dM: break
                                if dM[a] in addrs: addrs[dM[a]]['loc'].append(i+1)
                                else: addrs[dM[a]] = {'loc':[i+1],'id':None}

                            # insert the sta and sta_activity
                            self._insertsta(fid,sid,ts,addrs)
                            # self._insertsta_activity
                            # self._conn.commit()
                        except psql.OperationalError as e: # unrecoverable
                            msg = "frame %d insert failed at %s:. %s: %s" % (fid,self._next,e.pgcode,e.pgerror)
                            self._icomms.put((cs,ts1,'!THRESH_ERR!',msg))
                        except psql.Error as e:
                            self._conn.rollback()
                            msg = "frame %d failed at %s. %s: %s" % (fid,self._next,e.pgcode,e.pgerror)
                            self._icomms.put((cs,ts1,'!THRESH_WARN!',msg))
                        except Exception as e:
                            self._conn.rollback()
                            msg = "frame %d failed at %s. %s: %s" % (fid,self._next,type(e).__name__,e)
                            self._icomms.put((cs,ts1,'!THRESH_WARN!',msg))
                    else:
                        msg = "invalid token %s" % tkn
                        self._icomms.put((cs,ts1,'!THRESH_WARN!',msg))
                except (IndexError,ValueError):
                    msg = "invalid arguments (%s) for %s" % (','.join([str(x) for x in d]),tkn)
                    self._icomms.put((cs,ts1,'!THRESH_WARN!',msg))
                except KeyError as e:
                    msg = "invalid radio hwaddr: %s" % cs
                    self._icomms.put((cs,ts1,'!THRESH_WARN!',msg))
                except Exception as e:
                    msg = "%s: %s" % (type(e).__name__,e)
                    self._icomms.put((cs,ts1,'!THRESH_WARN!',msg))

        # notify collector we're down
        if self._curs: self._curs.close()
        if self._conn: self._conn.close()
        self._icomms.put((cs,ts2iso(time.time()),'!THRESH!',None))

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
        sql = """
               insert into signal (fid,std,rate,channel,chflags,rf,ht,mcs_bw,
                                   mcs_gi,mcs_ht,mcs_index,mcs_stbc)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
              """
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
        self._next = 'qos'
        sql = """
               insert into qosctrl (fid,tid,eosp,ackpol,amsdu,txop)
               values (%s,%s,%s,%s,%s,%s);
              """
        self._curs.execute(sql,(fid,dM.qosctrl['tid'],dM.qosctrl['eosp'],
                                dM.qosctrl['ack-policy'],dM.qosctrl['a-msdu'],
                                dM.qosctrl['txop']))
        self._conn.commit()

        # encryption
        self._next = 'crypt'
        if dM.crypt['type'] == 'wep':
            sql = "insert into wepcrypt (fid,iv,key_id,icv) values (%s,%s,%s,%s);"
            self._curs.execute(sql,(fid,dM.crypt['iv'],dM.crypt['key-id'],dM.crypt['icv']))
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
         :param ts: timestamp frame collected
         :param addrs: address dict
        """
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
            for a in nonbroadcast:
                # if this one doesnt have an id (not seen before) add it
                if not addrs[a]['id']:
                    # insert the new sta
                    sql = """
                           insert into sta (sid,fid,spotted,mac,manuf)
                           values (%s,%s,%s,%s,%s) RETURNING sta_id;
                          """
                    self._curs.execute(sql,(sid,fid,ts,a,manufacturer(self._ouis,a)))
                    addrs[a]['id'] = self._curs.fetchone()[0]
                    self._conn.commit()