#!/usr/bin/env python

""" collator.py: coordinates collection and transfer of wraith sensor & gps data

Processes and forwards 1) frames from the sniffer(s) 2) gps data (if any) collected
by a pf and 3) messages from tuner(s) and sniffer(s0
"""
__name__ = 'collate'
__license__ = 'GPL v3.0'
__version__ = '0.1.2'
__date__ = 'October 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import platform                            # system details
import sys                                 # python intepreter details
import signal                              # signal processing
import time                                # sleep and timestamps
import socket                              # connection to gps device
from Queue import Empty                    # queue empty exception
import multiprocessing as mp               # multiprocessing
import psycopg2 as psql                    # postgresql api
from wraith.utils.timestamps import ts2iso # timestamp conversion
from wraith.wifi.iw import regget          # regulatory domain
from wraith.utils.cmdline import ipaddr    # returns ip address
from wraith.wifi.oui import parseoui       # parse out oui dict
from wraith.iyri.thresh import Thresher    # thresher process
from wraith.iyri.thresh import PCAPWriter  # & the pcap writer process
from wraith.iyri.constants import NTHRESH  # num thresher processes
from wraith.iyri.constants import OUIPATH  # location of oui text file

class Collator(mp.Process):
    """ Collator - handles further processing of raw frames from the sniffer """
    def __init__(self,comms,conn,ab,sb,conf):
        """
         :param comms: internal communication all data sent here
          NOTE: all messages sent on internal comms must be a tuple t where
           t = (sender callsign,timestamp of event,type of message,event message)
         :param conn: connection pipe to/from Iyri
         :param ab: Abad's circular buffer
         :param sb: Shama's circular buffer
         :param conf: configuration dict
        """
        mp.Process.__init__(self)
        self._icomms = comms       # communications queue
        self._cI = conn            # message connection to/from Iyri
        self._conn = None          # conn to backend db
        self._curs = None          # primary db cursors
        self._sid = None           # our session id (from the backend)
        self._gid = None           # the gpsd id (from the backend)
        self._ab = ab              # abad's buffer
        self._sb = sb              # shama's buffer
        self._writea = False       # write abad pcap
        self._writes = False       # write shama pcap
        self._save = None          # save options
        self._dbstr = {}           # db connection string
        self._setup(conf)

    def terminate(self): pass

    def run(self):
        """ run execution loop """
        # ignore signals being used by main program
        signal.signal(signal.SIGINT,signal.SIG_IGN)
        signal.signal(signal.SIGTERM,signal.SIG_IGN)

        # function local variables
        lSta = mp.Lock()                           # sta lock
        qT = mp.Queue()                            # queue for tasks to threshers
        qWA = mp.Queue() if self._writea else None # queue for abad writer
        qWS = mp.Queue() if self._writes else None # queue for shama writer
        ouis = parseoui(OUIPATH)                   # oui dict
        rmap = {}                                  # maps callsigns (vnic) to hwaddr
        roles = {}                                 # maps roles to callsigns (vnics)
        buffers = {}                               # buffer map
        threshers = {}                             # pid->{'obj':Thresher,'conn':connection}
        writers = {}                               # pid->{'obj':Writer,'q':queue,'role':role}

        # send sensor up notification, platform details and gpsid
        try:
            self._submitsensor(ts2iso(time.time()),True)
            self._submitplatform()
        except psql.Error as e:
            # sensor submit failed, no point continuing
            if e.pgcode == '23P01': errmsg = "Last session closed incorrectly"
            else: errmsg = "%s: %s" % (e.pgcode,e.pgerror)
            self._conn.rollback()
            self._cI.send(('err','Collator','DB',errmsg))
            return
        except Exception as e:
            self._conn.rollback()
            self._cI.send(('err','Collator',type(e).__name__,e))

        # create threshers & pass sid
        for _ in xrange(NTHRESH):
            try:
                recv,send = mp.Pipe(False)
                t = Thresher(self._icomms,qT,recv,lSta,(self._ab,qWA),
                             (self._sb,qWS),self._dbstr,ouis)
                t.start()
                threshers[t.pid] = {'obj':t,'conn':send}
                send.send(('!SID!',ts2iso(time.time()),[self._sid]))

                # writing?
                if self._writea: send.send(('!WRITE!',ts2iso(time.time()),[True]))
            except RuntimeError as e:
                self._cI.send(('warn','Collator','Thresher',e))
        if not len(threshers):
            self._cI.send(('err','Collator','Thresher',"No threshers started. Quitting..."))

        # execution loop
        while len(threshers):
            # 1. check for stop token
            if self._cI.poll() and self._cI.recv() == '!STOP!': break

            # get any queued data from internal comms
            cs = ts = ev = msg = None
            try:
                # pull off data
                cs,ts,ev,msg = self._icomms.get(True,0.5)

                # events from thresher(s)
                if ev == '!THRESH!':
                    # thresher process up/down message
                    if msg is not None:
                        if msg in threshers:
                            self._cI.send(('info','Collator','Thresher',"%s initiated" % cs))
                        else:
                            self._cI.send(('warn','Collator','Thresher',"%s not recognized" % cs))
                    else:
                        pid = int(cs.split('-')[1])
                        threshers[pid]['conn'].close()
                        del threshers[pid]
                elif ev == '!THRESH_WARN!': self._cI.send(('warn','Collator','Thresher',msg))
                elif ev == '!THRESH_ERR!':
                    # tell process to stop
                    pid = int(cs.split('-')[1])
                    self._cI.send(('warn','Collator','Thresher',"%s->%s" % (cs,msg)))
                    threshers[pid]['conn'].send(('!STOP!',ts2iso(time.time()),None))
                # events from writer(s)
                elif ev == '!WRITE!':
                    # writer process up/down message
                    if msg is not None:
                        if msg in writers:
                            self._cI.send(('info','Collator','Writer',"%s initiated" % cs))
                        else:
                            self._cI.send(('warn','Collator','Writer',"%s not recognized" % cs))
                    else:
                        pid = int(cs.split('-')[1])
                        del writers[pid]

                        # for now, tell thresher's to stop writing (should add
                        # capability to stop writing for only one radio)
                        for pid in threshers:
                            threshers[pid]['conn'].send(('!WRITE!',ts2iso(time.time()),False))
                elif ev == '!WRITE_WARN!':
                    pid = int(cs.split('-')[1])
                    self._cI.send(('warn','Collator',"%s Writer" % writers[pid]['role'],msg))
                elif ev == '!WRITE_ERR!':
                    # tell process to stop
                    pid = int(cs.split('-')[1])
                    self._cI.send(('warn','Collator',"%s Writer" % writers[pid]['role'],msg))
                    writers[pid]['conn'].send(('!STOP!',ts2iso(time.time()),None))
                elif ev == '!WRITE_OPEN!' or ev == '!WRITE_DONE!':
                    self._cI.send(('info','Collator','Writer',msg))
                # events from gps device
                elif ev == '!GPSD!':
                    # updown message from gpsd (if down delete the gps id)
                    self._submitgpsd(ts,msg)
                    if msg is not None:
                        self._cI.send(('info','Collator','GPSD',"%s initiated" % cs))
                    else:
                        self._gid = None
                        self._cI.send(('info','Collator','GPSD',"%s shutdown" % cs))
                elif ev == '!FLT!': self._submitflt(ts,msg)
                # events from radio(s)
                elif ev == '!RADIO!': #
                    # up/down message from radio(s).
                    if msg is not None:
                        # shouldn't happen but make sure radio doesn't initate twice
                        if msg['role'] in roles:
                            self._cI.send(('warn','Collator','Radio',"%s already initiated" % msg['role']))
                            continue

                        # create a file writer (if saving) & update threshers
                        if msg['role'] == 'abad' and self._writea:
                            try:
                                p = PCAPWriter(self._icomms,qWA,self._sid,msg['mac'],
                                               self._ab,self._dbstr,self._save)
                                p.start()
                                writers[p.pid] = {'obj':p,'q':qWA,'role':'abad'}
                            except RuntimeError as e:
                                self._cI.send(('warn','Collator',"Abad Writer",e))
                        elif msg['role'] == 'shama' and self._writes:
                            try:
                                p = PCAPWriter(self._icomms,qWS,self._sid,msg['mac'],
                                               self._sb,self._dbstr,self._save)
                                p.start()
                                writers[p.pid] = {'obj':p,'q':qWS,'role':'shama'}
                            except RuntimeError as e:
                                self._cI.send(('warn','Collator',"Shama Writer",e))

                        # update threshers
                        for pid in threshers:
                            threshers[pid]['conn'].send(('!RADIO!',ts,[msg['mac'],msg['role']]))

                        # add to radio & role maps, submit radio & submit antenna(s)
                        self._cI.send(('info','Collator','Radio',"%s (%s) initiated" % (cs,msg['role'])))
                        rmap[cs] = msg['mac']
                        roles[msg['role']] = cs
                        self._submitradio(ts,msg['mac'],msg)
                        for i in xrange(msg['nA']):
                            self._submitantenna(ts,{'mac':msg['mac'],'idx':i,
                                                    'type':msg['type'][i],
                                                    'gain':msg['gain'][i],
                                                    'loss':msg['loss'][i],
                                                    'x':msg['x'][i],
                                                    'y':msg['y'][i],
                                                    'z':msg['z'][i]})
                    else:
                        self._cI.send(('info','Collator','Radio',"%s shutdown" % cs))
                        self._submitradio(ts,rmap[cs],None)
                        del rmap[cs]
                        for role in roles:
                            if roles[role] == cs:
                                del roles[role]
                                break
                elif ev == '!FAIL!':
                    # notify Iyri, submit fail & delete cs
                    self._cI.send(('err','Collator','Radio',"Deleting radio %s" % cs,msg))
                    self._submitradioevent(ts,[rmap[cs],'fail',msg])
                    del rmap[cs]
                elif ev == '!SCAN!':
                    # compile the scan list into a string before sending
                    sl = ",".join(["%s:%s" % (c,w) for (c,w) in msg])
                    self._cI.send(('info',cs,ev.replace('!',''),sl))
                    self._submitradioevent(ts,[rmap[cs],'scan',sl])
                elif ev == '!LISTEN!':
                    self._cI.send(('info',cs,ev.replace('!',''),msg))
                    self._submitradioevent(ts,[rmap[cs],'listen',msg])
                elif ev == '!HOLD!':
                    self._cI.send(('info',cs,ev.replace('!',''),msg))
                    self._submitradioevent(ts,[rmap[cs],'hold',msg])
                elif ev == '!PAUSE!':
                    self._cI.send(('info',cs,ev.replace('!',''),msg))
                    self._submitradioevent(ts,[rmap[cs],'pause',' '])
                elif ev == '!SPOOF!':
                    self._cI.send(('info',cs,ev.replace('!',''),msg))
                    self._submitradioevent(ts,[rmap[cs],'spoof',msg])
                elif ev == '!TXPWR!':
                    self._cI.send(('info',cs,ev.replace('!',''),msg))
                    self._submitradioevent(ts,[rmap[cs],'txpwr',msg])
                elif ev == '!FRAME!':
                    ix,l = msg
                    qT.put(('!FRAME!',ts,[rmap[cs],ix,l]))
                else: # unidentified event type, notify iyri
                    self._cI.send(('warn','Collator','Radio',"unknown event %s from %s" % (ev,cs)))
            except Empty: continue
            except psql.OperationalError as e: # unrecoverable
                self._cI.send(('err','Collator','DB',"%s: %s" % (e.pgcode,e.pgerror)))
            except psql.Error as e: # possible incorrect semantics/syntax
                self._conn.rollback()
                self._cI.send(('warn','Collator','SQL',"%s: %s" % (e.pgcode,e.pgerror)))
            except ValueError as e: # a tuple did not unpack
                self._cI.send(('warn','Collator','Unpack',e))
            except IndexError: # something wrong with antenna indexing
                self._cI.send(('err','Collator',"Radio","misconfigured antennas"))
            except KeyError as e: # (most likely) a radio sent a message without initiating
                self._cI.send(('err','Collator',"Key %s" % e,"in event (%s)" % ev))
            except Exception as e: # handle catchall error
                self._cI.send(('warn','Collator',type(e).__name__,e))

        # clean & shut down
        ts = ts2iso(time.time())
        try:
            try:
                # notify Nidus of sensor - check if radio(s), gpsd closed out
                for cs in rmap: self._submitradio(ts,rmap[cs],None)
                if self._gid: self._submitgpsd(ts,None)
                self._submitsensor(ts,False)
            except psql.Error:
                self._conn.rollback()
                self._cI.send(('warn','Collator','shutdown',"Corrupted DB on exit"))

            # stop children and close communications. active_children has side
            # effect of joining
            for pid in threshers:
                try:
                    threshers[pid]['conn'].send(('!STOP!',ts2iso(time.time()),None))
                except EOFError: pass
                finally:
                    threshers[pid]['conn'].close()

            for pid in writers:
                try:
                    writers[pid]['q'].put(('!STOP!',ts2iso(time.time()),None))
                except Exception as e:
                    pass

            # wait for children & join processes
            while mp.active_children(): time.sleep(0.5)

            if self._curs: self._curs.close()
            if self._conn: self._conn.close()
            self._cI.close()
        except EOFError: pass
        except Exception as e:
            if self._cI:
                self._cI.send(('warn','Collator','shutdown',"Failed to clean up: %s" % e))

#### private helper functions

    def _setup(self,conf):
        """
         connect to db w/ params in store & pass sensor up event

         :param conf: configuration details
        """
        try:
            self._dbstr = conf['store']
            # connect to db
            self._conn = psql.connect(host=self._dbstr['host'],
                                      port=self._dbstr['port'],
                                      dbname=self._dbstr['db'],
                                      user=self._dbstr['user'],
                                      password=self._dbstr['pwd'])
            self._curs = self._conn.cursor()
            self._curs.execute("set time zone 'UTC';")
            self._conn.commit()

            # set save values
            if conf['save']['on']:
                self._writea = True
                if conf['shama'] is not None: self._writes = True
                self._save = conf['save']
        except psql.OperationalError as e:
            if e.__str__().find('connect') > 0:
                raise RuntimeError('Collator:PostgreSQL:DB not running')
            elif e.__str__().find('authentication') > 0:
                raise RuntimeError('Collator:PostgreSQL:Invalid connection string')
            else:
                raise RuntimeError('Collator:PostgreSQL:DB error: %s' % e)
        except Exception as e:
            raise RuntimeError("Collator:Unknown:%s" % e)

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
        pyvers = "%d.%d.%d" % (sys.version_info.major,
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
                       insert into radio (mac,driver,chipset,channels,standards,description)
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