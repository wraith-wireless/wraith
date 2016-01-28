#!/usr/bin/env python

""" collator.py: coordinates collection and transfer of wraith sensor & gps data

Processes and stores
 1) frames from the radio(s)
 2) frontline traces collected by GPSController
 3) messages from tuner(s) and sniffer(s)
 4) device details to include 802.11 radios, gps device and system

Additionally, an internal dict with the form fmap[ix] = state where ix is the
index of the frame in the buffer and state is oneof {0|1} such that 0 denotes
that the frame at ix has been "pulled" of the buffer but is still being processed
and 1 denotes that frame at ix is still on the buffer (and no entry denotes that
no frame is at ix. Use the number of frames (regardless of state) to determine if
we need to increase/decrease the size of the local buffer.

NOTE: this assumes that the Collator can pull frames off the radio(s) buffer prior
to their being overwritten by the RadioCollator
"""
__name__ = 'collate'
__license__ = 'GPL v3.0'
__version__ = '0.1.4'
__date__ = 'January 2016'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import platform,sys                        # system & interpreter details
import signal,select                       # signal & select processing
from time import time                      # sleep and timestamps
import socket                              # connection to gps device
from Queue import Empty                    # queue empty exception
import multiprocessing as mp               # multiprocessing
import psycopg2 as psql                    # postgresql api
from wraith.utils.timestamps import isots  # converted timestamp
from wraith.wifi.iw import regget          # regulatory domain
from wraith.utils.cmdline import ipaddr    # returns ip address
from wraith.wifi.oui import parseoui       # parse out oui dict
from wraith.iyri.thresh import Thresher    # thresher process
from wraith.iyri.constants import *        # constants

class Collator(mp.Process):
    """ Collator - handles processing/storage of raw frames from the sniffer """
    def __init__(self,comms,conn,ab,sb,conf):
        """
         :param comms: internal communication all data sent here
          NOTE: all messages sent on internal comms must be a tuple t where
           t = (sender callsign,message timestamp,type of message,event message)
         :param conn: connection pipe to/from Iyri
         :param ab: Abad's circular buffer
         :param sb: Shama's circular buffer
         :param conf: configuration dict
        """
        mp.Process.__init__(self)
        self._icomms = comms # communications queue
        self._cI = conn      # message connection to/from Iyri
        self._conn = None    # conn to backend db
        self._curs = None    # primary db cursor
        self._sid = None     # our session id (from the db)
        self._gid = None     # the gpsd id (from gps controller)
        self._ab = ab        # abad's buffer
        self._sb = sb        # shama's buffer
        self._save = None    # save options
        self._dbstr = {}     # db connection string
        self._ps = {}        # thresher & oui path parameters
        self._setup(conf)

    def terminate(self): pass

    @property
    def cs(self): return 'collatorr-{0}'.format(self.pid)

    def run(self):
        """ run execution loop """
        # ignore signals being used by main program
        signal.signal(signal.SIGINT,signal.SIG_IGN)
        signal.signal(signal.SIGTERM,signal.SIG_IGN)

        # function local variables
        ouis = parseoui(self._ps['opath']) # oui dict
        mint = mp.cpu_count()              # min/initial # of threshers
        maxt = self._ps['max']             # maximum # of threshers
        lSta = mp.Lock()                   # sta lock
        qT = mp.Queue()                    # thresher task queue
        rmap = {}                          # maps callsigns (vnic) to hwaddr
        fmap = {}                          # maps src (hwaddr) to frames
        smap = {}                          # maps src (hwaddr) to sensor params
        threshers = {}                     # pid->connection
        stop = False                       # poison pill has been received
        poisoned = False                   # poison pill has been sent (to threshers)
        df = rf = 0                        # number dropped frames & read frames

        # create our frame buffer
        m = DIM_M * 5  # set max # of frames
        n = DIM_N      # and keep n as is
        _ix = 0        # current 'pointer'
        cb = memoryview(mp.Array('B',m*n,lock=False))

        # send sensor up notification, platform details & create threshers
        try:
            self._submitsensor(isots(),True)
            for _ in xrange(mint):
                try:
                    (pid,send) = self._newthresher(qT,lSta,cb,ouis,smap)
                    threshers[pid] = send
                except RuntimeError as e:
                    self._cI.send((IYRI_WARN,'collator','Thresher',e))
            self._submitplatform()
        except psql.Error as e:
            if e.pgcode == '23P01': err = "Last session closed incorrectly"
            else: err = "{0}->{1}".format(e.pgcode,e.pgerror)
            self._conn.rollback()
            self._cI.send((IYRI_ERR,'collator','Thresher',err))

        # notify iyri of startup parameters
        msg = "{0} threshers (min={1},max={2}) & a {3} x {4} internal buffer"
        msg = msg.format(format(len(threshers)),mint,maxt,m,n)
        self._cI.send((IYRI_INFO,'collator','Startup',msg))

        # execution loop - NOTE: if submitsensor failed, there will be no
        # threshers and we will immediately fall through the exection loop
        tmUpdate = 0
        tmUpdate1 = 0
        ins = [self._cI,self._icomms._reader]
        while mp.active_children():
            if stop: # is it time to quit?
                # while frames are still queued, update iyri of status
                if len(fmap) > 0 and not poisoned:
                    tmUpdate1 = time()
                    if tmUpdate1 - tmUpdate > 5.0:
                        msg = "{0} outstanding frames".format(len(fmap))
                        self._cI.send((IYRI_INFO,'collator','Frames',msg))
                        tmUpdate = time()

                # send out the poison pills once all frames have been
                # processed (or at least pulled of the buffer)
                if not [i for i in fmap if fmap[i]] and not poisoned:
                    for pid in threshers:
                        try:
                            threshers[pid].send((POISON,None,None))
                        except Exception as e:
                            msg = "Error stopping Thresher-{0}: {1}".format(pid,e)
                            self._cI.send((IYRI_WARN,'collator','Thresher',e))
                    poisoned = True

            # continue with processing
            try:
                # block longer if we havent gotten poison pill
                (rs,_,_) = select.select(ins,[],[],0.5 if stop else 5)

                # convert tkns from iyri to icomms format
                # NOTE: all Thresh events (exluding THRESH_THRESH) will return
                # data as a tuple t = (string message,buffer index) where any
                # individual item in the tuple could be None
                for r in rs:
                    if r == self._cI: (cs,ts,ev,d) = ('','',self._cI.recv(),'')
                    else: (cs,ts,ev,d) = self._icomms.get_nowait()

                    if ev == POISON: stop = True
                    elif ev == THRESH_THRESH: # thresher process up/down message
                        if d is not None: # thresher up
                            msg = "{0} up".format(cs)
                            self._cI.send((IYRI_INFO,'collator','Thresher',msg))
                        else: # thresher down
                            pid = int(cs.split('-')[1])
                            threshers[pid].close()
                            del threshers[pid]
                            msg = "{0} down".format(cs)
                            self._cI.send((IYRI_INFO,'collator','Thresher',msg))
                    elif ev == THRESH_DQ: # frame has been pulled off buffer
                        (_,idx) = d
                        fmap[idx] = 0
                    elif ev == THRESH_WARN or ev == THRESH_ERR or ev == THRESH_DONE:
                        # frame processing finished
                        msg,idx = d
                        try:
                            del fmap[idx]
                        except:
                            pass

                        # handle individual events below
                        if ev == THRESH_WARN:
                            self._cI.send((IYRI_WARN,'collator','Thresher',msg))
                        elif ev == THRESH_ERR:
                            pid = int(cs.split('-')[1])
                            msg = "{0}->{1}".format(cs,msg[0])
                            self._cI.send((IYRI_WARN,'collator','Thresher',msg))
                            threshers[pid].send((POISON,None,None))

                            # make a new thresher (to replace this one)
                            try:
                                (pid,send) = self._newthresher(qT,lSta,cb,ouis,smap)
                                threshers[pid] = send
                            except RuntimeError as e:
                                self._cI.send((IYRI_WARN,'Collator',Thresher,e))

                        # determine workload percentage
                        if stop: continue
                        if len(fmap) / (m*1.0) <= 0.1 and len(threshers) > mint:
                            msg = "Workload falling below 10%, removing a threseher"
                            self._cI.send((IYRI_INFO,'collator','load',msg))
                            pid = threshers.keys()[0]
                            threshers[pid].send((POISON,None,None))
                    elif ev == GPS_GPSD: # gpsd up/down
                        self._submitgpsd(ts,d)
                        if d: self._cI.send((IYRI_INFO,'collator','GPSD','initiated'))
                    elif ev == GPS_FLT: self._submitflt(ts,d)
                    elif ev == RDO_RADIO: # up/down message from radio(s).
                        if d is not None: # radio up
                            (mac,role,rec) = d['mac'],d['role'],d['record']

                            # shouldn't happen but make sure:
                            assert(cs not in rmap)           # reinitialization
                            assert(role in ['abad','shama']) # role is valid

                            # notify iyri radio is up & add to maps
                            msg = "{0}:{1} initiated".format(role,cs)
                            self._cI.send((IYRI_INFO,'collator','Radio',msg))
                            rmap[cs] = mac
                            smap[mac] = {'record':rec,'cb':None}
                            if role == 'abad': smap[mac]['cb'] = self._ab
                            else: smap[mac]['cb'] = self._sb

                            # update threshers
                            for pid in threshers:
                                threshers[pid].send((COL_RDO,ts,[mac]))
                                threshers[pid].send((COL_WRITE,ts,[mac,rec]))

                            # submit radio & antenna(s)
                            self._submitradio(ts,mac,d)
                            for i in xrange(d['nA']):
                                self._submitantenna(ts,{'mac':mac,'idx':i,
                                                        'type':d['type'][i],
                                                        'gain':d['gain'][i],
                                                        'loss':d['loss'][i],
                                                        'x':d['x'][i],
                                                        'y':d['y'][i],
                                                        'z':d['z'][i]})
                        else:  # radio down
                            msg = "{0} shutdown".format(cs)
                            self._cI.send((IYRI_INFO,'collator','Radio',msg))
                            self._submitradio(ts,rmap[cs],None)

                            # delete our maps (only delete tasks if its empty)
                            del smap[rmap[cs]]
                            del rmap[cs]
                    elif ev == RDO_FAIL:
                        msg = "Deleting radio {0}: {1}".format(cs,d)
                        self._cI.send((IYRI_ERR,'collator','Radio',msg))
                        self._submitradioevent(ts,[rmap[cs],'fail',d])

                        # delete our maps
                        del smap[rmap[cs]]
                        del rmap[cs]
                    elif RDO_SCAN <= ev <= RDO_STATE:
                        if ev == RDO_SCAN: # need to format the channel list
                            d = ','.join(["{0}:{1}".format(c,w) for (c,w) in d])
                        self._cI.send((IYRI_INFO,cs,RDO_DESC[ev],d))
                        self._submitradioevent(ts,[rmap[cs],RDO_DESC[ev],d])
                    elif ev == RDO_FRAME:
                        # get the index,length of the frame & src hwaddr
                        (i,l) = d
                        hw = rmap[cs]

                        # about to overwrite a frame?
                        if _ix in fmap and fmap[_ix] == 1:
                            df += 1
                            print 'dropping'
                            continue

                        # move to our buffer, put on threshers queue & update index
                        cb[(_ix*n):(_ix*n)+l] = smap[hw]['cb'][(i*n):(i*n)+l]
                        fmap[_ix] = 1
                        qT.put((COL_FRAME,ts,(hw,_ix,l)))
                        _ix = (_ix+1) % m
                        rf += 1

                        # if the buffer reaches 25% capacity, add a thresher
                        # NOTE: consider all outstanding frames even those that
                        # have been pulled of the buffer but are still being
                        # processed)
                        if len(fmap) / (m*1.0) > 0.25 and len(threshers) < maxt:
                            # create at most mint new threshers w/out adding
                            # more than allowed
                            x = min(mint,maxt-len(threshers))
                            msg = "Buffer at 25%, adding {0} threshers".format(x)
                            self._cI.send((IYRI_INFO,'collator','load',msg))
                            for _ in xrange(x):
                                try:
                                    (pid,send) = self._newthresher(qT,lSta,cb,
                                                                   ouis,smap)
                                    threshers[pid] = send
                                except RuntimeError as e:
                                    self._cI.send((IYRI_WARN,'Collator',Thresher,e))
                    else: # unidentified event type, notify iyri
                        msg = "unknown event. {0}->{1}".format(ev,cs)
                        self._cI.send((IYRI_WARN,'collator','icomms',msg))
            except Empty: continue
            except (EOFError,IOError):
                pass
            except psql.OperationalError as e: # unrecoverable
                rmsg = "{0}: {1}".format(e.pgcode,e.pgerror)
                self._cI.send((IYRI_ERR,'collator','DB',rmsg))
            except psql.Error as e: # possible incorrect semantics/syntax
                self._conn.rollback()
                rmsg = "{0}: {1}".format(e.pgcode,e.pgerror)
                self._cI.send((IYRI_WARN,'collator','SQL',rmsg))
            except IndexError as e:
                rmsg = "Bad index {0} in event {1}".format(e,ev)
                self._cI.send((IYRI_ERR,'collator',"Index",rmsg))
            except KeyError as e:
                rmsg = "Bad key {0} in event {1}".format(e,ev)
                self._cI.send((IYRI_ERR,'collator','Key',rmsg))
            except select.error as e: # hide (4,'Interupted system call') errors
                if e[0] != 4: self._cI.send((IYRI_WARN,'collator','select',e))
            except Exception as e: # handle catchall error
                self._cI.send((IYRI_WARN,'collator',type(e).__name__,e))

        # clean up & shut down
        try:
            try:
                # notify Nidus of sensor - check if radio(s), gpsd closed out
                for cs in rmap: self._submitradio(isots(),rmap[cs],None)
                if self._gid: self._submitgpsd(isots(),None)
                if self._sid: self._submitsensor(isots(),False)
            except psql.Error:
                self._conn.rollback()
                self._cI.send((IYRI_WARN,'collator','shutdown',"DB is corrupted"))

            if self._curs: self._curs.close()
            if self._conn: self._conn.close()
            if rf or df:
                msg = "{0} read frames, {1} dropped frames".format(rf,df)
                self._cI.send((IYRI_DONE,'collator','Complete',msg))
            self._cI.close()
        except (EOFError,IOError): pass
        except Exception as e:
            if self._cI and not self._cI.closed:
                msg = "Failed to clean up: {0}".format(e)
                self._cI.send((IYRI_WARN,'collator','shutdown',msg))

#### private helper functions

    def _setup(self,conf):
        """
         connect to db w/ params in store & pass sensor up event
         :param conf: configuration details
        """
        try:
            self._dbstr = conf['store']
            self._ps = conf['local']['thresher']
            self._ps['opath'] = conf['local']['opath']
            self._conn = psql.connect(host=self._dbstr['host'],
                                      port=self._dbstr['port'],
                                      dbname=self._dbstr['db'],
                                      user=self._dbstr['user'],
                                      password=self._dbstr['pwd'])
            self._curs = self._conn.cursor()
            self._curs.execute("set time zone 'UTC';")
            self._conn.commit()

            # determine max connections from database
            # = max_connections - superusr_reserved_connections - CURRENT_CONNECTIONS
            # maximum threshers will be set to the minimum of max_connections &
            # user specified value
            maxc = rsrvc = currc = None
            self._curs.execute("show max_connections;")
            maxc = int(self._curs.fetchone()[0])
            self._curs.execute("show superuser_reserved_connections;")
            rsrvc = int(self._curs.fetchone()[0])
            self._curs.execute("select count(*) from pg_stat_activity;")
            currc = self._curs.fetchone()[0]
            maxc = maxc - rsrvc - currc
            self._ps['max'] = min(maxc,self._ps['max'])
        except psql.OperationalError as e:
            self._conn.rollback()
            if e.__str__().find('connect') > 0:
                raise RuntimeError('Collator:PostgreSQL:DB not running')
            elif e.__str__().find('authentication') > 0:
                raise RuntimeError('Collator:PostgreSQL:Invalid connection string')
            else:
                raise RuntimeError('Collator:PostgreSQL:DB error: {0}'.format(e))
        except Exception as e:
            self._conn.rollback()
            raise RuntimeError("Collator:Unknown:{0}->{1}".format(type(e).__name__,e))

    def _newthresher(self,q,l,b,os,m):
        """
        creates a new thresher
        :param q: task queue for threshers
        :param l: STA lock
        :param b: buffer
        :param os: oui dict
        :param m: smap dict
        :returns tuple t = (thresher process id,send connection):
        """
        # NOTE: send the sid last so the thresher will not attempt to process
        # any frames until it has all radio(s) data
        r,s = mp.Pipe(False)
        t = Thresher(self._icomms,q,r,l,b,self._dbstr,os)
        t.start()
        for mac in m:
            ts = isots()
            rec = m[mac]['record']
            s.send((COL_RDO,ts,[mac]))
            s.send((COL_WRITE,ts,[mac,rec]))
        if self._sid: s.send((COL_SID,isots(),[self._sid]))
        return t.pid,s

    #### DB functionality ####
    def _submitsensor(self,ts,state):
        """
         submit sensor at ts having state
         :param ts: timestamp of event
         :param state: state of event
        """
        if state:
            sql = """
                   insert into sensor (hostname,ip,period)
                   values (%s,%s,tstzrange(%s,NULL,'[]')) RETURNING session_id;
                  """
            self._curs.execute(sql,(socket.gethostname(),ipaddr(),ts))
            self._sid = self._curs.fetchone()[0]
        else:
            sql = """
                   update sensor set period = tstzrange(lower(period),%s)
                   where session_id = %s;
                  """
            self._curs.execute(sql,(ts,self._sid))
        self._conn.commit()

    def _submitplatform(self):
        """ submit platform details """
        os = platform.system()
        try:
            dist,osvers,name = platform.linux_distribution()
        except:
            dist = osvers = name = None
        try:
            rd = regget()
        except:
            rd = None
        kernel = platform.release()
        arch = platform.machine()
        pyvers = "{0}.{1}.{2}".format(sys.version_info.major,
                                      sys.version_info.minor,
                                      sys.version_info.micro)
        bits,link = platform.architecture()
        compiler = platform.python_compiler()
        libcvers = " ".join(platform.libc_ver())

        # submit the details
        sql = """
               insert into platform (sid,os,dist,version,name,kernel,machine,
                                     pyvers,pycompiler,pylibcvers,pybits,
                                     pylinkage,region)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
              """
        self._curs.execute(sql,(self._sid,os,dist,osvers,name,kernel,arch,
                                pyvers,compiler,libcvers,bits,link,rd))
        self._conn.commit()

    def _submitgpsd(self,ts,g):
        """
         submit gps device at gs
         :param ts: timestamp of event
         :param g: gps device details
        """
        if g is not None:
            # insert if gpsd does not already exist
            self._curs.execute("select gpsd_id from gpsd where devid=%s;",(g['id'],))
            row = self._curs.fetchone()
            if row: self._gid = row[0]
            else:
                sql = """
                       insert into gpsd (devid,version,flags,driver,bps,tty)
                       values (%s,%s,%s,%s,%s,%s) returning gpsd_id;
                      """
                self._curs.execute(sql,(g['id'],g['version'],g['flags'],
                                        g['driver'],g['bps'],g['path']))
                self._gid = self._curs.fetchone()[0]

            # update using table
            sql = """
                   insert into using_gpsd (sid,gid,period)
                   values (%s,%s,tstzrange(%s,NULL,'[]'));
                  """
            self._curs.execute(sql,(self._sid,self._gid,ts))
        else:
            sql = """
                   update using_gpsd set period = tstzrange(lower(period),%s)
                   where sid = %s and gid = %s;
                  """
            self._curs.execute(sql,(ts,self._sid,self._gid))
            self._gid = None
        self._conn.commit()

    def _submitflt(self,ts,flt):
        """
         submit the flt at ts
         :param ts: timestamp of frontline trace
         :param flt: frontline trace dict
        """
        sql = """
               insert into flt (sid,ts,coord,alt,spd,dir,fix,xdop,ydop,pdop,epx,epy)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
              """
        self._curs.execute(sql,(self._sid,ts,flt['coord'],flt['alt'],flt['spd'],
                                flt['dir'],flt['fix'],flt['dop']['xdop'],
                                flt['dop']['ydop'],flt['dop']['pdop'],flt['epy'],
                                flt['epx']))
        self._conn.commit()

    def _submitradio(self,ts,mac,r):
        """
         submit radio
         :param ts: timestamp of radio event
         :param mac: mac hw address
         :param r: radio details
        """
        if r is not None:
            # add radio if it does not exist
            self._curs.execute("select * from radio where mac=%s;",(mac,))
            if not self._curs.fetchone():
                sql = """
                       insert into radio (mac,driver,chipset,channels,
                                          standards,description)
                       values (%s,%s,%s,%s,%s,%s);
                      """
                self._curs.execute(sql,(mac,r['driver'][0:20],r['chipset'][0:20],
                                        [int(c) for c in r['channels']],
                                        r['standards'][0:20],r['desc'][0:200]))

            # add a using_radio record
            sql = """
                   insert into using_radio (sid,mac,phy,nic,vnic,hop,ival,role,period)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,tstzrange(%s,NULL,'[]'));
                  """
            self._curs.execute(sql,(self._sid,mac,r['phy'],r['nic'],r['vnic'],
                                    r['hop'],r['ival'],r['role'],ts))

            # add a txpwr event
            sql = "insert into radio_event (mac,state,params,ts) values (%s,%s,%s,%s);"
            self._curs.execute(sql,(mac,'txpwr',r['txpwr'],ts))

             # add a spoof event (if necessary)
            if r['spoofed']: self._curs.execute(sql,(mac,'spoof',r['spoofed'],ts))
        else:
            sql = """
                   update using_radio set period = tstzrange(lower(period),%s)
                   where sid = %s and mac =%s;
                  """
            self._curs.execute(sql,(ts,self._sid,mac))
        self._conn.commit()

    def _submitantenna(self,ts,a):
        """
         submit antenna
         :param ts: timestamp of antenna submit
         :param a: antenna details
        """
        sql = """
               insert into antenna (mac,ind,gain,loss,x,y,z,type,ts)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s);
              """
        self._curs.execute(sql,(a['mac'],a['idx'],a['gain'],a['loss'],
                                a['x'],a['y'],a['z'],a['type'],ts))
        self._conn.commit()

    def _submitradioevent(self,ts,m):
        """
         submit radioevent at ts
         :param ts: timestamp of radio event
         :param m: event details
        """
        sql = """
               insert into radio_event (mac,state,params,ts)
               values (%s,%s,%s,%s);
              """
        self._curs.execute(sql,(m[0],m[1],m[2],ts))
        self._conn.commit()
