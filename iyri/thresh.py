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
from wraith.radio.oui import manufacturer   # oui functions
from wraith.utils import simplepcap as pcap # write frames to file

class PCAPWriter(mp.Process):
    """ saves frmes to file """
    def __init__(self,comms,q,dbconn,sid,mac,conf):
        """
         comms: internal communication (to Collator)
         q: task queue i.e frames to write
         dbconn: db connection
         sid: current session id
         mac: hwaddr of collecting radio
         conf: configuration details
        """
        mp.Process.__init__(self)
        self._icomms = comms  # communications queue
        self._tasks = q       # write to/from Thresher and/or Collator
        self._conn = dbconn   # db connection
        self._curs = None     # our cursor
        self._sid = sid       # current session id
        self._mac = mac       # hw addr of collecting src
        self._stop = False    # stop flag
        self._path = ''       # file config variables
        self._private = False # data private
        self._sz = 0          # size limit
        self._pkts = []       # bulked packets
        self._npkt = 0        # cur packet number in file
        self._fout = None
        self._setup(conf)

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
                    ts,fid,f,l,r = d
                    if self._private and l < r: f = f[:l] + f[r:]
                    self._pkts.append((ts,fid,f))
                    if len(self._pkts) > NWRITE: self._writepkts()
                else:
                    self._icomms.put((cs,ts1,'!WRITE_WARN!',"invalid token %s" % tkn))
            except Empty: pass
            except (IndexError,ValueError):
                self._icomms.put((cs,ts1,'!WRITE_WARN!',"Invalid arguments"))
            except Exception as e:
                self._icomms.put((cs,ts1,'!WRITE_WARN!',"%s: %s" % (type(e).__name__,e)))

        # are there unwritten packets?
        if len(self._pkts) > 0: self._writepkts()

        # notify Collator we're down
        self._icomms.put((cs,ts2iso(time.time()),'!WRITE!',None))

    def stop(self,signum=None,stack=None): self._stop = True

    def _writepkts(self):
        """ write all packets to file """
        # get a timestamp & cs
        cs = 'writer-d' % self.pid
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

            # write each packet
            for i,pkt in enumerate(self._pkts):
                pcap.pktwrite(self._fout,pkt[0],pkt[2])
                sql = "insert into frame_path (fid,filepath,n) values (%s,%s,%s);"
                self._curs.execute(sql,(pkt[1],self._fout.name,self._npkt))
                self._npkt += 1

            # close file if it exceeds the max
            if self._fout and os.path.getsize(self._fout.name) > self._sz:
                self._icomms.put((cs,ts,'!WRITE_DONE!',"Closing %s. Wrote %d packets" % (self._fout.name,self._npkt)))
                self._fout.close()
                self._fout = None
                self._pkts = []
                self._npkt = 0
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

    def _setup(self,conf):
        """ initialize """
        try:
            # db stuff
            self._curs = self._conn.cursor()
            self._curs.execute("set time zone 'UTC';")
            self._conn.commit()

            # set priavte variables
            self._path = conf['path']
            self._private = conf['private']
            self._sz = conf['sz']
        except psql.Error as e:
            self._conn.rollback()
            raise RuntimeError(e)

class Thresher(mp.Process):
    """ inserts frames (and saves if specified) in db """
    def __init__(self,comms,q,conn,abad,shama,dbconn,ouis):
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
        self._conn = dbconn  # db connection
        self._curs = None    # our cursor
        self._ouis = ouis    # oui dict
        self._stop = False   # stop flag
        self._write = False  # write flag
        self._setup()

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
                    if r == self._cC:
                        tkn,ts,d = self._cC.recv()
                    else: # tasks._reader
                        tkn,ts,d = self._tasks.get(0.5)

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
                        src,ix,l = d[0],d[1],d[2]
                        f = rdos[src]['buffer'][(ix*N):(ix*N)+l].tobytes()

                        # parse the frame
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
                        else:
                            vs = (sid,ts,lF,dR['sz'],dM.offset,
                                  [(dR['sz']+dM.offset),(lF-dM.stripped)],dR['flags'],
                                  int('a-mpdu' in dR['present']),
                                  rtap.flags_get(dR['flags'],'fcs'))

                        # insert the frame. psql exceptions will be cught in outer try
                        sql = """
                               insert into frame (sid,ts,bytes,bRTAP,bMPDU,data,flags,ampdu,fcs)
                               values (%s,%s,%s,%s,%s,%s,%s,%s,%s) returning frame_id;
                              """
                        self._curs.execute(sql,vs)
                        fid = self._curs.fetchone()[0]
                        self._conn.commit()

                        # pass to writer
                        if self._write:
                            l = r = 0
                            if validRTAP: l += dR['sz']
                            if validMPDU:
                                l += dM.offset
                                r = lF-dM.stripped
                            rdos[src]['writer'].put(('!FRAME!',ts,[fid,f,l,r]))
                    else:
                        self._icomms.put((cs,ts1,'!THRESH_WARN!',"invalid token %s" % tkn))
                except psql.OperationalError as e: # unrecoverable
                    self._icomms.put((cs,ts1,'!THRESH_ERR!',"DB. %s: %s" % (e.pgcode,e.pgerror)))
                except (IndexError,ValueError):
                    self._icomms.put((cs,ts1,'!THRESH_WARN!',"invalid arguments for %s" % tkn))
                except KeyError as e:
                    self._icomms.put((cs,ts1,'!THRESH_WARN!',"invalid radio mac: %s" % cs))
                except psql.Error as e:
                    self._conn.rollback()
                    self._icomms.put((cs,ts1,'!THRESH_WARN!',"SQL. %s: %s" % (e.pgcode,e.pgerror)))
                except Exception as e:
                    self._icomms.put((cs,ts1,'!THRESH_WARN!',"%s: %s" % (type(e).__name__,e)))

        # notify collector we're down
        self._icomms.put((cs,ts2iso(time.time()),'!THRESH!',None))

    def stop(self,signum=None,stack=None): self._stop = True

    def _setup(self):
        """ initialize """
        try:
            self._curs = self._conn.cursor()
            self._curs.execute("set time zone 'UTC';")
            self._conn.commit()
        except psql.Error as e:
            self._conn.rollback()
            raise RuntimeError(e)
