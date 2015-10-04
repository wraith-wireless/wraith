#!/usr/bin/env python

""" collator.py: coordinates collection and transfer of wraith sensor & gps data

Processes and forwards 1) frames from the sniffer(s) 2) gps data (if any) collected
by a pf and 3) messages from tuner(s) and sniffer(s0
"""
__name__ = 'collate'
__license__ = 'GPL v3.0'
__version__ = '0.1.1'
__date__ = 'September 2015'
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
from wraith.radio.iw import regget         # regulatory domain
from wraith.utils.cmdline import ipaddr    # returns ip address
from wraith.radio.oui import parseoui      # parse out oui dict
from wraith.iyri.thresh import Thresher    # thresher process
from wraith.iyri.constants import NTHRESH  # num thresher processes

class Collator(mp.Process):
    """ Collator - handles further processing of raw frames from the sniffer """
    def __init__(self,comms,conn,ab,sb,conf):
        """
         initializes Collator
         comms - internal communication
          NOTE: all messages sent on internal comms must be a tuple T where
           T = (sender callsign,timestamp of event,type of message,event message)
         conn - connection to/from Iyri
         ab - Abad's circular buffer
         sb - Shama's circular buffer
         conf - necessary config details
        """
        mp.Process.__init__(self)
        self._icomms = comms       # communications queue
        self._cI = conn            # message connection to/from Iyri
        self._gconf = conf['gps']  # configuration for gps/datastore
        self._conn = None          # conn to backend db
        self._curs = None          # primary db cursors
        self._sid = None           # our session id (from the backend)
        self._gid = None           # the gpsd id (from the backend)
        self._ab = ab              # abad's buffer
        self._sb = sb              # shama's buffer
        self._setup(conf['store'])

    def terminate(self): pass

    def run(self):
        """ run execution loop """
        # ignore signals being used by main program
        signal.signal(signal.SIGINT,signal.SIG_IGN)
        signal.signal(signal.SIGTERM,signal.SIG_IGN)

        # basic variables
        q = mp.Queue()    # internal queue for tasks to threshers
        ouis = parseoui() # oui dict
        rmap = {}         # radio map: maps callsigns to mac addr
        buffers = {}      # buffer map
        threshers = {}    # thresher map

        # send sensor up notification, platform details and gpsid
        try:
            self._submitsensor(ts2iso(time.time()),True)
            self._submitplatform()
        except psql.Error as e:
            # sensor submit failed, no point continuing
            if e.pgcode == '23P01':
                errmsg = "Sensor failed to close correctly last session"
            else:
                errmsg = "%s: %s" % (e.pgcode,e.pgerror)
            self._conn.rollback()
            self._cI.send(('err','Collator','DB',errmsg))
            return
        except Exception as e:
            self._conn.rollback()
            self._cI.send(('err','Collator','Unknown',e))

        # create threshers
        a = (self._ab,None)
        for _ in xrange(NTHRESH):
            try:
                t = Thresher(self._icomms,q,self._conn,ouis,
                             (self._ab,None),(self._sb,None),None)
                t.start()
                threshers[t.pid] = t
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
                        if msg not in threshers:
                            self._cI.send(('warn','Collator','Thresher',"%s not recognized" % cs))
                        else:
                            self._cI.send(('info','Collator','Thresher',"%s initiated" % cs))
                    else:
                        pid = cs.split('-')[1]
                        del threshers[pid]
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
                        # assign buffers
                        if msg['role'] == 'abad': buffers['cs'] = self._ab
                        elif msg['role'] == 'shama': buffers['cs'] = self._sb
                        else:
                            raise RuntimeError("Invalid role %s" % msg['role'])

                        # update threshers
                        for _ in threshers: q.put(('!RADIO!',ts,[msg['role'],cs]))

                        # add to radio map, submit radio & submit antenna(s)
                        self._cI.send(('info','Collator','Radio',"%s (%s) initiated" % (cs,msg['role'])))
                        rmap[cs] = msg['mac']
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
                    q.put(('!FRAME!',ts,[rmap[cs],ix,l]))
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
                self._cI.send(('err','Collator','Unknown',e))

        # clean & shut down
        ts = ts2iso(time.time())
        try:
            try:
                # notify Nidus of sensor - check if radio(s), gpsd closed out
                for cs in rmap: self._submitradio(ts,rmap[cs],None)
                if self._gid: self._submitgpsd(ts,None)
                self._submitsensor(ts,False)
            except psql.Error as e:
                self._conn.rollback()
                if self._cI:
                    self._cI.send(('warn','Collator','shutdown',"Failed to close cleanly - corrupted DB %s: %s" % (e.pgcode,e.pgerror)))

            # stop children and close communications. active_children has side
            # effect of joining
            for _ in threshers:
                try:
                    q.put(('!STOP!',None,None))
                except EOFError: pass
            while mp.active_children(): time.sleep(0.5)

            if self._curs: self._curs.close()
            if self._conn: self._conn.close()
            self._cI.close()
        except EOFError: pass
        except Exception as e:
            if self._cI:
                self._cI.send(('warn','Collator','shutdown',"Failed to clean up: %s" % e))

#### private helper functions

    def _setup(self,store):
        """ connect to db w/ params in store & pass sensor up event """
        try:
            self._conn = psql.connect(host=store['host'],
                                      port=store['port'],
                                      dbname=store['db'],
                                      user=store['user'],
                                      password=store['pwd'])
            self._curs = self._conn.cursor()
            self._curs.execute("set time zone 'UTC';")
            self._conn.commit()
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
        """ submit sensor at ts having state """
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
        assert self._sid

        # get platform details
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
        """ submit gps device having state w/ details """
        assert self._sid
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
            assert self._gid
            sql = """
                   update using_gpsd set period = tstzrange(lower(period),%s)
                   where sid = %s and gid = %s;
                  """
            self._curs.execute(sql,(ts,self._sid,self._gid))
        self._conn.commit()

    def _submitflt(self,ts,flt):
        """ submit the flt at ts """
        assert self._sid
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
        """ submit gps device having state w/ details """
        assert self._sid
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
        """ submit antenna at ts """
        assert self._sid
        sql = """
               insert into antenna (mac,ind,gain,loss,x,y,z,type,ts)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s);
              """
        self._curs.execute(sql,(a['mac'],a['idx'],a['gain'],a['loss'],
                                a['x'],a['y'],a['z'],a['type'],ts))
        self._conn.commit()

    def _submitradioevent(self,ts,m):
        """ submit radioevent at ts """
        assert self._sid
        sql = """
               insert into radio_event (mac,state,params,ts)
               values (%s,%s,%s,%s);
              """
        self._curs.execute(sql,(m[0],m[1],m[2],ts))
        self._conn.commit()