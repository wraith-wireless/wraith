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
import wraith.radio.radiotap as rtap        # 802.11 layer 1 parsing
from wraith.radio import mpdu               # 802.11 layer 2 parsing
from wraith.radio import mcs                # mcs functions
from wraith.radio import channels           # 802.11 channels/RFs
#from wraith.radio.oui import manufacturer   # oui functions
from wraith.utils import simplepcap as pcap # write frames to file

class PCAPWriter(mp.Process):
    """ saves frames to file """
    def __init__(self,comms,q,sid,mac,buff,dbstr,conf):
        """
         :param comms: internal communication (to Collator)
         q: task queue i.e frames to write
         sid: current session id
         mac: hwaddr of collecting radio
         buffer: the buffer of frames to write
         dbstr: db connection string
         conf: configuration details
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
        """ initialize """
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
    """ inserts frames (and saves if specified) in db """
    def __init__(self,comms,q,conn,abad,shama,dbstr,ouis):
        """
         comms - internal info-message communication (to Collator)
         q - task queue from Collator
         conn - token connection from Collator
         abad: tuple t = (AbadBuffer,AbadWriterQueue)
         shama: tuple t = (ShamaBuffer,ShamaWriterQueue)
         dbconn - db connection
         ouis - oui dict
        """
        mp.Process.__init__(self)
        self._icomms = comms # communications queue
        self._tasks = q      # connection from Collator
        self._cC = conn      # token connection from Collator
        self._abad = abad    # abad tuple
        self._shama = shama  # shama tuple
        self._conn = None    # db connection
        self._curs = None    # our cursor
        self._ouis = ouis    # oui dict
        self._stop = False   # stop flag
        self._write = False  # write flag
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

        # notify collator we're up
        self._icomms.put((cs,ts2iso(time.time()),'!THRESH!',self.pid))

        while not self._stop:
            # check for tasks or messages
            tkn = ts = d = None
            rs,_,_ = select.select([self._cC,self._tasks._reader],[],[])
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
                            self._icomms.put((cs,ts1,'!THRESH_WARN!','bad frame at %d: %s' % (ix,f)))
                            continue
                        else:
                            vs = (sid,ts,lF,dR['sz'],dM.offset,
                                  [(dR['sz']+dM.offset),(lF-dM.stripped)],dR['flags'],
                                  int('a-mpdu' in dR['present']),
                                  rtap.flags_get(dR['flags'],'fcs'))

                        # insert the frame
                        sql = """
                               insert into frame (sid,ts,bytes,bRTAP,bMPDU,data,flags,ampdu,fcs)
                               values (%s,%s,%s,%s,%s,%s,%s,%s,%s) returning frame_id;
                              """
                        try:
                            self._curs.execute(sql,vs)
                            fid = self._curs.fetchone()[0]
                        except psql.OperationalError as e: # unrecoverable
                            self._icomms.put((cs,ts1,'!THRESH_ERR!',"DB. %s: %s" % (e.pgcode,e.pgerror)))
                            continue
                        except psql.Error as e:
                            self._conn.rollback()
                            self._icomms.put((cs,ts1,'!THRESH_WARN!',"SQL. %s: %s" % (e.pgcode,e.pgerror)))
                            continue
                        except Exception as e:
                            self._conn.rollback()
                            self._icomms.put((cs,ts1,'!THRESH_WARN!',"%s: %s" % (type(e),e)))
                        else:
                            self._conn.commit()

                        # pass fid, index, nBytes, left, right indices to writer
                        if fid:
                            if self._write:
                                l = r = 0
                                if validRTAP: l += dR['sz']
                                if validMPDU:
                                    l += dM.offset
                                    r = lF-dM.stripped
                                rdos[src]['writer'].put(('!FRAME!',ts,[fid,ix,b,l,r]))

                        # NOTE: the next two "parts" storing and extracting are
                        # mutually exlusive and do not need to happen in any order
                        # and could be handled by threads or other processes

                        # store frame details in db
                        try:
                            # start with radiotap data
                            self._insertrtap(fid,src,dR)

                            # then mpdu data
                            #if dM.offset > 0: self._insertmpdu(fid,dR)
                            #if dM.offset > 0:
                            #    self._inserttraffic(fid,dM)
                            #    if dM.qosctrl: self._insertqos(fid,dM)
                            #    if dM.crypt: self._insertcrypt(fid,dM)
                        except psql.OperationalError as e: # unrecoverable
                            self._icomms.put((cs,ts1,'!THRESH_ERR!',"DB. %s: %s" % (e.pgcode,e.pgerror)))
                            continue
                        except psql.Error as e:
                            self._conn.rollback()
                            self._icomms.put((cs,ts1,'!THRESH_WARN!',"SQL. %s: %s" % (e.pgcode,e.pgerror)))
                            continue
                        except Exception as e:
                            self._conn.rollback()
                            self._icomms.put((cs,ts1,'!THRESH_WARN!',"%s: %s" % (type(e).__name__,e)))
                        else:
                            self._conn.commit()
                    else:
                        self._icomms.put((cs,ts1,'!THRESH_WARN!',"invalid token %s" % tkn))
                except (IndexError,ValueError):
                    self._icomms.put((cs,ts1,'!THRESH_WARN!',"invalid arguments (%s) for %s" % (','.join([str(x) for x in d]),tkn)))
                except KeyError as e:
                    self._icomms.put((cs,ts1,'!THRESH_WARN!',"invalid radio hwaddr: %s" % cs))
                except Exception as e:
                    self._icomms.put((cs,ts1,'!THRESH_WARN!',"%s: %s" % (type(e).__name__,e)))

        # notify collector we're down
        if self._curs: self._curs.close()
        if self._conn: self._conn.close()
        self._icomms.put((cs,ts2iso(time.time()),'!THRESH!',None))

    def stop(self,signum=None,stack=None): self._stop = True

    def _setup(self,dbstr):
        """ initialize db connection """
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

    def _insertrtap(self,fid,src,dR):
        """ insert radiotap data into db """
        #if 'a-mpdu' in dR['present']: self._insertampdu(fid,dR)
                            #self._insertsource(fid,dR)
                            #self._insertsiganl(fid,dR)
        # NOTE: all exceptions are caught in caller
        # ampdu info
        if 'a-mpdu' in dR['present']:
            sql = "insert into ampdu fid,refnum,flags) values (%s,%s,%s);"
            self._curs.execute(sql,(fid,dR['a-mpdu'][0],dR['a-mpdu'][1]))

        # source info
        ant = dR['antenna'] if 'antenna' in dR else 0
        pwr = dR['antsignal'] if 'antsignal' in dR else 0
        sql = "insert into source (fid,src,antenna,rfpwr) values (%s,%s,%s,%s);"
        self._curs.execute(sql,(fid,src,ant,pwr))

        # signal info - determine what standard, data rate and any mcs fields
        # assuming channel info is always in radiotap
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