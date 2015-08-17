#!/usr/bin/env python

""" rto.py: collates and relays wraith sensor data

Processes and forwards 1) frames from the sniffer(s) 2) gps data (if any) collected
by a pf and 3) messages from tuner(s) and sniffer(s0
"""
__name__ = 'rto'
__license__ = 'GPL v3.0'
__version__ = '0.1.0'
__date__ = 'August 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import platform                            # system details
import sys                                 # python intepreter details
import signal                              # signal processing
import time                                # sleep and timestamps
import socket                              # connection to gps device
import threading                           # threads
import mgrs                                # lat/lon to mgrs conversion
import gps                                 # gps device access
from Queue import Queue, Empty             # thread-safe queue
import multiprocessing as mp               # multiprocessing
import psycopg2 as psql                    # postgresql api
from wraith.utils.timestamps import ts2iso # timestamp conversion
from wraith.radio.iw import regget         # regulatory domain
from wraith.utils.cmdline import ipaddr    # returns ip address

class GPSPoller(threading.Thread):
    """ periodically checks gps for current location """
    def __init__(self,eq,conf):
        """
         eq - event queue between rto and this Thread
         conf - config file for gps
        """
        threading.Thread.__init__(self)
        self._done = threading.Event() # stop event
        self._eQ = eq                  # msg queue from radio controller
        self._conf = conf              # gps configuration
        self._gpsd = None              # connection to the gps device
        self._setup()

    def _setup(self):
        """ attempt to connect to device if fixed is off """
        if self._conf['fixed']: return # static, do nothing
        try:
            self._gpsd = gps.gps('127.0.0.1',self._conf['port'])
            self._gpsd.stream(gps.WATCH_ENABLE)
        except socket.error as e:
            raise RuntimeError(e)

    def shutdown(self): self._done.set()

    def run(self):
        """ query for current location """
        # two execution loops - 1) get device details 2) get location

        # initialize device details dict
        if self._conf['fixed']:
            # configure a 'fake' device
            poll = 0.5 # please poll charm
            qpx = qpy = float('inf') # quiet PyCharm alerts
            dd = {'id':'xxxx:xxxx',
                  'version':'0.0',
                  'flags':0,
                  'driver':'static',
                  'bps':0,
                  'path':'None'}
        else:
            poll = self._conf['poll'] # extract polltime from config
            qpx = self._conf['epx']   # extract quality ellipse x from config
            qpy = self._conf['epy']   # extract quality ellipse x from config
            dd = {'id':self._conf['id'],
                  'version':None,
                  'driver':None,
                  'bps':None,
                  'path':None,
                  'flags':None}

        # Device Details Loop - get complete details or quit on done
        while dd['flags'] is None:
            if self._done.is_set(): break
            else:
                # loop while data is on serial, polling first
                while self._gpsd.waiting():
                    dev = self._gpsd.next()
                    try:
                        if dev['class'] == 'VERSION': dd['version'] = dev['release']
                        elif dev['class'] == 'DEVICE':
                            # flags will not be present until gpsd has seen identifiable
                            # packets from the device
                            dd['flags'] = dev['flags']
                            dd['driver'] = dev['driver']
                            dd['bps'] = dev['bps']
                            dd['path'] = dev['path']
                    except KeyError:
                        pass

        # send device details. If fixed gps, exit immediately
        if not self._done.is_set():
            self._eQ.put(('!DEV!',time.time(),dd))
            if self._conf['fixed']: # send static front line trace
                self._eQ.put(('!FLT!',time.time(),{'id':dd['id'],
                                                  'fix':-1,
                                                  'lat':(self._conf['lat'],0.0),
                                                  'lon':(self._conf['lon'],0.0),
                                                  'alt':self._conf['alt'],
                                                  'dir':self._conf['dir'],
                                                  'spd':0.0,
                                                  'dop':{'xdop':1,'ydop':1,'pdop':1}}))
                return

        # Location - loop until told to quit
        while not self._done.is_set():
            # while there's data, get it (NOTE: this loop may exit without data)
            while self._gpsd.waiting():
                if self._done.is_set(): break
                rpt = self._gpsd.next()
                if rpt['class'] != 'TPV': continue
                try:
                    if rpt['epx'] > qpx or rpt['epy'] > qpy: continue
                    else:
                        # get all values
                        flt = {}
                        flt['id'] = dd['id']
                        flt['fix'] = rpt['mode']
                        flt['lat'] = (rpt['lat'],rpt['epy'])
                        flt['lon'] = (rpt['lon'],rpt['epx'])
                        flt['alt'] = rpt['alt'] if 'alt' in rpt else float("nan")
                        flt['dir'] = rpt['track'] if 'track' in rpt else float("nan")
                        flt['spd'] = rpt['spd'] if 'spd' in rpt else float("nan")
                        flt['dop'] = {'xdop':self._gpsd.xdop,
                                       'ydop':self._gpsd.ydop,
                                       'pdop':self._gpsd.pdop}
                        self._eQ.put(('!GEO',time.time(),flt))
                        break
                except (KeyError,AttributeError):
                    # a KeyError means not all values are present, an
                    # AttributeError means not all dop values are present
                    pass
            time.sleep(poll)

        # close out connection
        self._gpsd.close()

class RTO(mp.Process):
    """ RTO - handles further processing of raw frames from the sniffer """
    def __init__(self,comms,conn,rb,cb,conf):
        """
         initializes RTO
         comms - internal communication
          NOTE: all messages sent on internal comms must be a tuple T where
           T = (sender callsign,timestamp of event,type of message,event message)
         conn - connection to/from DySKT
         rb - recon circular buffer
         cb - collection circular buffer
         conf - necessary config details
        """
        mp.Process.__init__(self)
        self._icomms = comms       # communications queue
        self._cD = conn            # message connection to/from DySKT
        self._gconf = conf['gps']  # configuration for gps/datastore
        self._rb = rb              # recon buffer
        self._cb = cb              # collection buffer
        self._gps = None           # polling thread for front line traces
        self._qG = None            # internal queue for gps poller
        self._conn = None          # conn to backend db
        self._curs = None          # primary db cursors
        self._sid = None           # our session id
        self._gid = None           # the gpsd id from the backend
        self._mgrs = None          # lat/lon to mgrs conversion
        self._setup(conf['store'])

    def terminate(self): pass
    
    def run(self):
        """ run execution loop """
        # ignore signals being used by main program
        signal.signal(signal.SIGINT,signal.SIG_IGN)
        signal.signal(signal.SIGTERM,signal.SIG_IGN)

        # basic variables
        rmap = {}    # radio map: maps callsigns to mac addr
        gpsid = None # id of gps device

        # send sensor up notification, platform details and gpsid
        try:
            self._submitsensor(ts2iso(time.time()),True)
            self._submitplatform(ts2iso(time.time()))
            if self._gconf:
                self._qG = Queue()
                try:
                    self._gps = GPSPoller(self._qG,self._gconf)
                    self._gps.start()
                except RuntimeError as e:
                    self._cD.send(('warn','RTO','GPSD',"Failed to connnect: %s" %e))
                    self._gps = None
        except psql.Error as e:
            # sensor submit failed, no point continuing
            if e.pgcode == '23P01':
                errmsg = "Sensor failed to close correctly last session"
            else:
                errmsg = "%s: %s" % (e.pgcode,e.pgerror)
            self._conn.rollback()
            self._cD.send(('err','RTO','DB',errmsg))
            return
        except Exception as e:
            self._conn.rollback()
            self._cD.send(('err','RTO','Unknown',e))

        # execution loop
        while True:
            # TODO: convert all to select
            # 1. anything from DySKT
            if self._cD.poll() and self._cD.recv() == '!STOP!': break

            # 2. gps device/frontline trace?
            try:
                t,ts,msg = self._qG.get_nowait()
            except (Empty,AttributeError): pass
            else:
                if t == '!FLT!': self._submitflt(ts2iso(ts),msg)
                elif t == '!DEV!':
                    try:
                        gpsid = msg['id']
                        self._cD.send(('info','RTO','GPSD',"%s initiated" % gpsid))
                        self._submitgpsd(ts2iso(ts),True,msg)
                    except psql.OperationalError as e: # unrecoverable
                        self._cD.send(('err','RTO','DB',"%s: %s" % (e.pgcode,e.pgerror)))
                    except psql.Error as e: # possible incorrect semantics/syntax
                        self._conn.rollback()
                        self._cD.send(('warn','RTO','SQL',"%s: %s" % (e.pgcode,e.pgerror)))

            # 3. queued data from internal comms
            ev = msg = None
            try:
                cs,ts,ev,msg = self._icomms.get(True,0.5)
                ts = ts2iso(ts)

                if ev == '!UP!':
                    # should be the 1st message we get from radio(s). Notify
                    # DySKT, submit the new radio and it's antennas
                    rmap[cs] = msg['mac']
                    self._cD.send(('info','RTO','Radio',"%s initiated" % cs))
                    self._submitradio(ts,True,msg)
                    for i in xrange(msg['nA']):
                        self._submitantenna(ts,{'mac':msg['mac'],'idx':i,
                                                'type':msg['type'][i],
                                                'gain':msg['gain'][i],
                                                'loss':msg['loss'][i],
                                                'x':msg['x'][i],
                                                'y':msg['y'][i],
                                                'z':msg['z'][i]})
                elif ev == '!FAIL!':
                    # notify DySKT, submit faile & delete cs
                    self._submitradioevent(ts,[rmap[cs],'fail',msg])
                    del rmap[cs]
                    del self._bulk[cs]
                elif ev == '!SCAN!':
                    # compile the scan list into a string before sending
                    sl = ",".join(["%s:%s" % (c,w) for (c,w) in msg])
                    self._cD.send(('info',cs,ev.replace('!',''),sl))
                    self._submitradioevent(ts,[rmap[cs],'scan',sl])
                elif ev == '!LISTEN!':
                    self._cD.send(('info',cs,ev.replace('!',''),msg))
                    self._submitradioevent(ts,[rmap[cs],'listen',msg])
                elif ev == '!HOLD!':
                    self._cD.send(('info',cs,ev.replace('!',''),msg))
                    self._submitradioevent(ts,[rmap[cs],'hold',msg])
                elif ev == '!PAUSE!':
                    self._cD.send(('info',cs,ev.replace('!',''),msg))
                    self._submitradioevent(ts,[rmap[cs],'pause',' '])
                elif ev == '!SPOOF!':
                    self._cD.send(('info',cs,ev.replace('!',''),msg))
                    self._submitradioevent(ts,[rmap[cs],'spoof',msg])
                elif ev == '!TXPWR!':
                    self._cD.send(('info',cs,ev.replace('!',''),msg))
                    self._submitradioevent(ts,[rmap[cs],'txpwr',msg])
                #elif ev == '!DWELL!':
                #    if msg: self._cD.send(('info',cs,ev.replace('!',''),msg))
                elif ev == '!FRAME!':
                    pass
                else: # unidentified event type, notify dyskt
                    self._cD.send(('warn','RTO','Radio',"unknown event %s" % ev))
            except Empty: continue
            except psql.OperationalError as e: # unrecoverable
                self._cD.send(('err','RTO','DB',"%s: %s" % (e.pgcode,e.pgerror)))
            except psql.Error as e: # possible incorrect semantics/syntax
                self._conn.rollback()
                self._cD.send(('warn','RTO','SQL',"%s: %s" % (e.pgcode,e.pgerror)))
            #except IndexError: # something wrong with antenna indexing
            #    self._cD.send(('err','RTO',"Radio","misconfigured antennas"))
            except KeyError as e: # a radio sent a message without initiating
                self._cD.send(('err','RTO','Radio %s' % e,"data out of order (%s)" % ev))
            #except Exception as e: # handle catchall error
            #    self._cD.send(('err','RTO','Unknown',e))

        # any bulked frames not yet sent?
        #for cs in rmap:
        #    ret = self._flushbulk(time.time(),rmap[cs],cs)
        #    if ret:
        #        if ret: self._cD.send(('err','RTO','Nidus',ret))
        #        break

        # notify Nidus of closing (radios,sensor,gpsd). hopefully no errors on send
        ts = ts2iso(time.time())
        for cs in rmap: self._submitradio(ts,False,{'mac':rmap[cs]})
        if self._gps: self._submitgpsd(ts,False)
        self._submitsensor(ts,False)

        # shut down
        if not self._shutdown():
            try:
                self._cD.send(('warn','RTO','Shutdown',"Incomplete shutdown"))
            except IOError:
                # most likely DySKT closed its side of the pipe
                pass

#### private helper functions

    def _setup(self,store):
        """ connect to db w/ params in store & pass sensor up event """
        try:
            self._mgrs = mgrs.MGRS() # get mgrs converter
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
                raise RuntimeError('RTO:PostgreSQL:DB not running')
            elif e.__str__().find('authentication') > 0:
                raise RuntimeError('RTO:PostgreSQL:Invalid connection string')
            else:
                raise RuntimeError('RTO:PostgreSQL:DB error: %s' % e)
        except Exception as e:
            raise RuntimeError("RTO:Unknown:%s" % e)

    def _shutdown(self):
        """ clean up. returns whether a full reset or not occurred """
        # try shutting down & resetting radio (if it failed we may not be able to)
        clean = True
        try:
            # close backend connection and connection to DySKT
            if self._curs: self._curs.close()
            if self._conn: self._conn.close()
            self._cD.close()

            # stop GPSPoller
            if self._gps and self._gps.is_alive(): self._gps.stop()
        except:
            clean = False
        return clean

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

    def _submitplatform(self,ts):
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

    def _submitgpsd(self,ts,state,g=None):
        """ submit gps device having state w/ details """
        assert self._sid
        if state:
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
        self._curs.execute(sql,(self._sid,ts,
                                self._mgrs.toMGRS(flt['lat'][0],flt['lon'][0]),
                                flt['alt'],flt['spd'],flt['dir'],flt['fix'],
                                flt['dop']['xdop'],flt['dop']['ydop'],
                                flt['dop']['pdop'],flt['lat'][1],flt['lon'][1]))
        self._conn.commit()

    def _submitradio(self,ts,state,r):
        """ submit gps device having state w/ details """
        assert self._sid
        if state:
            # add radio if it does not exist
            self._curs.execute("select * from radio where mac=%s;",(r['mac'],))
            if not self._curs.fetchone():
                sql = """
                       insert into radio (mac,driver,chipset,channels,standards,description)
                       values (%s,%s,%s,%s,%s,%s);
                      """
                self._curs.execute(sql,(r['mac'],r['driver'][0:20],r['chipset'][0:20],
                                        [int(c) for c in r['channels']],r['standards'][0:20],
                                        r['desc'][0:200]))

            # add a using_radio record
            sql = """
                   insert into using_radio (sid,mac,phy,nic,vnic,role,period)
                   values (%s,%s,%s,%s,%s,%s,tstzrange(%s,NULL,'[]'));
                  """
            self._curs.execute(sql,(self._sid,r['mac'],r['phy'],r['nic'],
                                    r['vnic'],r['role'],ts))

            # add a txpwr event
            sql = "insert into radio_event (mac,state,params,ts) values (%s,%s,%s,%s);"
            self._curs.execute(sql,(r['mac'],'txpwr',r['txpwr'],ts))

             # add a spoof event (if necessary)
            if r['spoofed']: self._curs.execute(sql,(r['mac'],'spoof',r['spoofed'],ts))
        else:
            sql = """
                   update using_radio set period = tstzrange(lower(period),%s)
                   where sid = %s and mac =%s;
                  """
            self._curs.execute(sql,(ts,self._sid,r['mac']))
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

    #### send helper functions

    def _send(self,t,ts,d):
        """
         send - sends message msg m of type t with timestamp ts to Nidus
          t - message type
          ts - message timestamp
          d - data
         returns None on success otherwise returns reason for failure
        """
        # convert the timestamp to utc isoformat before crafting
        ts = ts2iso(ts)
        
        # craft the message
        try:
            send = "\x01*%s:\x02" % t
            if t == 'DEVICE': send += self._craftdevice(ts,d)
            elif t == 'PLATFORM': send += self._craftplatform(d)
            elif t == 'RADIO': send += self._craftradio(ts,d)
            elif t == 'ANTENNA': send += self._craftantenna(ts,d)
            elif t == 'GPSD': send += self._craftgpsd(ts,d)
            elif t == 'FRAME': send += self._craftframe(ts,d)
            elif t == 'BULK': send += self._craftbulk(ts,d)
            elif t == 'FLT': send += self._craftflt(ts,d,self._mgrs)
            elif t == 'RADIO_EVENT': send += self._craftradioevent(ts,d)
            send += "\x03\x12\x15\04"
            #if not self._nidus.send(send): return "Nidus socket closed unexpectantly"
            return None
        except socket.error, ret:
            return ret
        except Exception, ret:
            return ret

    @staticmethod
    def _craftbulk(ts,d):
        """ create body of bulk message """
        return "%s %s %s \x1EFB\x1F%s\x1FFE\x1E" % (ts,d[0],d[1],d[2])

    @staticmethod
    def _craftframe(ts,d):
        """ creates body of the frame message """
        return "%s \x1EFB\x1F%s\x1FFE\x1E \x1EFB\x1F%s\x1FFE\x1E" % (ts,d[0],d[1])