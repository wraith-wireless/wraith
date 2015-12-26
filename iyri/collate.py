#!/usr/bin/env python

""" collator.py: coordinates collection and transfer of wraith sensor & gps data

Processes and stores
 1) frames from the radio(s)
 2) gps device data and frontline traces collected by GPSController
 3) messages from tuner(s) and sniffer(s)
"""
__name__ = 'collate'
__license__ = 'GPL v3.0'
__version__ = '0.1.2'
__date__ = 'October 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import platform,sys                        # system & interpreter details
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
        self._local = {}     # thresher & oui path parameters
        self._setup(conf)

    def terminate(self): pass

    def run(self):
        """ run execution loop """
        # ignore signals being used by main program
        signal.signal(signal.SIGINT,signal.SIG_IGN)
        signal.signal(signal.SIGTERM,signal.SIG_IGN)

        # function local variables
        ouis = parseoui(self._local['opath']) # oui dict
        mint = self._local['min']             # min/initial # of threshers
        maxt = self._local['max']             # maximum # of threshers
        wrkt = self._local['wrk']             # threshold
        lSta = mp.Lock()                      # sta lock
        qT = mp.Queue()                       # thresher task queue
        tmap = {}                             # maps src (hwaddr) to frames list
        rmap = {}                             # maps callsigns (vnic) to hwaddr
        imap = {}                             # maps thresher init values to hwaddr
        threshers = {}                        # pid->{'obj':Thresher,'conn':connection}

        # send sensor up notification and platform details
        try:
            self._submitsensor(ts2iso(time.time()),True)
            self._submitplatform()
        except psql.Error as e:
            # sensor submit failed, no point continuing
            if e.pgcode == '23P01': err = "Last session closed incorrectly"
            else: err = "{0}: {1}".format(e.pgcode,e.pgerror)
            self._conn.rollback()
            self._cI.send((IYRI_ERR,'Collator','DB',err))
            return
        except Exception as e:
            self._conn.rollback()
            self._cI.send((IYRI_ERR,'Collator',type(e).__name__,e))

        # create threshers & pass sid
        for _ in xrange(mint):
            try:
                recv,send = mp.Pipe(False)
                t = Thresher(self._icomms,qT,recv,
                             lSta,self._ab,self._sb,
                             self._dbstr,ouis)
                t.start()
                threshers[t.pid] = {'obj':t,'conn':send}
                send.send((COL_SID,ts2iso(time.time()),[self._sid]))
            except RuntimeError as e:
                self._cI.send((IYRI_WARN,'Collator','Thresher',e))

        # notify Collator if no theshers were created
        if not len(threshers):
            self._cI.send((IYRI_ERR,'Collator','Thresher',"No Threshers. Quitting..."))

        # execution loop
        while len(threshers):
            # 1. check for stop token
            if self._cI.poll() and self._cI.recv() == POISON: break

            # get any queued data from internal comms
            try:
                # pull off data
                cs,ts,ev,msg = self._icomms.get(True,0.5)

                # events from thresher(s)
                # NOTE: all events (exluding THRESH_THRESH) will return data
                # as a triple t = (string message,src,buffer index)
                # where any individual item in the triple could be None
                if ev == THRESH_THRESH:
                    # thresher process up/down message
                    if msg is not None:
                        # thresher up - notify iyri
                        rmsg = "{0} up".format(cs)
                        self._cI.send((IYRI_INFO,'Collator','Thresher',rmsg))
                    else:
                        # thresher down - remove from thresher dict
                        pid = int(cs.split('-')[1])
                        threshers[pid]['conn'].close()
                        del threshers[pid]

                        # & notify iyri
                        rmsg = "{0} down".format(cs)
                        self._cI.send((IYRI_INFO,'Collator','Thresher',rmsg))
                elif ev == THRESH_WARN or ev == THRESH_ERR or ev == THRESH_DONE:
                    # update task list & notify iyri
                    wmsg,src,idx = msg
                    try:
                        del tmap[src][idx]
                    except Exception as e:
                        pass

                    # can we delete the task map?
                    if len(tmap[src]) == 0 and src not in imap: del tmap[src]

                    # handle individual events below
                    if ev == THRESH_WARN:
                        self._cI.send((IYRI_WARN,'Collator','Thresher',wmsg))
                    elif ev == THRESH_ERR:
                        pid = int(cs.split('-')[1])
                        rmsg = "{0}->{1}".format(cs,msg[0])
                        self._cI.send((IYRI_WARN,'Collator','Thresher',rmsg))
                        threshers[pid]['conn'].send((POISON,ts,None))
                    else:
                        # can we stop a thresher? - IOT avoid start/stop
                        # situations, half the threshold
                        nt = len(threshers)
                        nf = 0
                        for fs in [tmap[src] for src in tmap]: nf += len(fs)
                        if (nf / nt) < (wrkt / 2) and nt > mint:
                            # notify Iyri & kill first thresher
                            rmsg = "Downgrading to {0} threshers".format(nt-1)
                            self._cI.send((IYRI_INFO,'Collator','Thresher',rmsg))
                            pid = threshers.keys()[0]
                            ts1 = ts2iso(time.time())
                            threshers[pid]['conn'].send((POISON,ts1,None))
                # events from gps device
                elif ev == GPS_GPSD:
                    self._submitgpsd(ts,msg)
                    if msg: self._cI.send((IYRI_INFO,'Collator','GPSD','initiated'))
                    else: self._cI.send((IYRI_INFO,'Collator','GPSD','shutdown'))
                elif ev == GPS_FLT:
                    self._submitflt(ts,msg)
                # events from radio(s)
                elif ev == RDO_RADIO:
                    # up/down message from radio(s).
                    if msg is not None:
                        # pull out mac, role & record
                        mac = msg['mac']
                        role = msg['role']
                        rec = msg['record']

                        # shouldn't happen but make sure radio doesn't initate twice
                        # & that role is valid i.e. abad or shama
                        if cs in rmap:
                            rmsg = "{0} already initiated".format(role)
                            self._cI.send((IYRI_WARN,'Collator','Radio',rmsg))
                            continue
                        elif role not in ['abad','shama']:
                            rmsg = "invalid role: {0}".format(role)
                            self._cI.send((IYRI_WARN,'Collator','Radio',rmsg))
                            continue

                        # notify iyri, add to maps
                        rmsg = "{0}:{1} initiated".format(role,cs)
                        self._cI.send((IYRI_INFO,'Collator','Radio',rmsg))
                        rmap[cs] = mac
                        tmap[mac] = {}
                        imap[mac] = {'role':role,'record':rec}

                        # & update current threshers
                        for pid in threshers:
                            threshers[pid]['conn'].send((COL_RDO,ts,[mac,role]))
                            threshers[pid]['conn'].send((COL_WRITE,ts, [mac,rec]))

                        # submit radio & submit antenna(s)
                        self._submitradio(ts,mac,msg)
                        for i in xrange(msg['nA']):
                            self._submitantenna(ts,{'mac':mac,'idx':i,
                                                    'type':msg['type'][i],
                                                    'gain':msg['gain'][i],
                                                    'loss':msg['loss'][i],
                                                    'x':msg['x'][i],
                                                    'y':msg['y'][i],
                                                    'z':msg['z'][i]})
                    else:
                        # radio is shutting down
                        rmsg = "{0} shutdown".format(cs)
                        self._cI.send((IYRI_INFO,'Collator','Radio',rmsg))
                        self._submitradio(ts,rmap[cs],None)

                        # delete our maps (only delete tasks if its empty)
                        if not tmap[rmap[cs]]: del tmap[rmap[cs]]
                        del imap[rmap[cs]]
                        del rmap[cs]
                elif ev == RDO_FAIL:
                    # notify Iyri & submit fail
                    rmsg = "Deleting radio {0}: {1}".format(cs,msg)
                    self._cI.send((IYRI_ERR,'Collator','Radio',rmsg))
                    self._submitradioevent(ts,[rmap[cs],'fail',msg])

                    # delete our maps (only delete tasks if its empty)
                    if not tmap[rmap[cs]]: del tmap[rmap[cs]]
                    del imap[rmap[cs]]
                    del rmap[cs]
                elif RDO_SCAN <= ev <= RDO_STATE:
                    if ev == RDO_SCAN: # need to format the channel list
                        msg = ','.join(["{0}:{1}".format(c,w) for (c,w) in msg])
                    self._cI.send((IYRI_INFO,cs,RDO_DESC[ev],msg))
                    self._submitradioevent(ts,[rmap[cs],RDO_DESC[ev],msg])
                elif ev == RDO_FRAME:
                    # get the index and length of the frame
                    idx,l = msg

                    # update tmap list, and put frame on thresher queue
                    hwaddr = rmap[cs]
                    if not idx in tmap[hwaddr]: tmap[hwaddr][idx] = None
                    else:
                        rmsg = "src {0} buffer[{1}] overwritten".format(cs,idx)
                        self._cI.send((IYRI_WARN,'Collator','overwrite',rmsg))
                    qT.put((COL_FRAME,ts,[hwaddr,idx,l]))

                    # do we need to add a thresher?
                    nt = len(threshers)
                    nf = 0
                    for fs in [tmap[src] for src in tmap]: nf += len(fs)
                    if nf / nt > wrkt and nt < maxt:
                        # notify Iyri & start a new thresher
                        rmsg = "Upgrading to {0} threshers".format(nt+1)
                        self._cI.send((IYRI_INFO,'Collator','Thresher',rmsg))
                        try:
                            recv,send = mp.Pipe(False)
                            t = Thresher(self._icomms,qT,recv,lSta,self._ab,
                                         self._sb,self._dbstr,ouis)
                            t.start()
                            threshers[t.pid] = {'obj':t,'conn':send}
                        except RuntimeError as e:
                            self._cI.send((IYRI_WARN,'Collator','Thresher',e))
                        else:
                            # update new thesher then send sid
                            p = t.pid
                            for mac in imap:
                                ts1 = ts2iso(time.time())
                                rec = imap[mac]['record']
                                role = imap[mac]['role']
                                threshers[p]['conn'].send((COL_RDO,ts1,[mac,role]))
                                threshers[p]['conn'].send((COL_WRITE,ts1,[mac,rec]))
                            threshers[p]['conn'].send((COL_SID,ts1,[self._sid]))
                else: # unidentified event type, notify iyri
                    rmsg = "unknown event. {0}->{1}".format(ev,cs)
                    self._cI.send((IYRI_WARN,'Collator',cs,rmsg))
            except Empty: continue
            except (EOFError,IOError): break # pipe error
            except psql.OperationalError as e: # unrecoverable
                rmsg = "{0}: {1}".format(e.pgcode,e.pgerror)
                self._cI.send((IYRI_ERR,'Collator','DB',rmsg))
            except psql.Error as e: # possible incorrect semantics/syntax
                self._conn.rollback()
                rmsg = "{0}: {1}".format(e.pgcode,e.pgerror)
                self._cI.send((IYRI_WARN,'Collator','SQL',rmsg))
            except IndexError as e:
                rmsg = "Bad index {0} in event {1}".format(e,ev)
                self._cI.send((IYRI_ERR,'Collator',"Index",rmsg))
            except KeyError as e:
                rmsg = "Bad key {0} in event {1}".format(e,ev)
                self._cI.send((IYRI_ERR,'Collator','Key',rmsg))
            except Exception as e: # handle catchall error
                self._cI.send((IYRI_WARN,'Collator',type(e).__name__,e))

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
                self._cI.send((IYRI_WARN,'Collator','shutdown',"Corrupted DB on exit"))

            # stop children and close communications. active_children has side
            # effect of joining
            for pid in threshers:
                try:
                    threshers[pid]['conn'].send((POISON,ts,None))
                except:
                    pass
                finally:
                    threshers[pid]['conn'].close()

            # wait for children & join processes
            while mp.active_children(): time.sleep(0.5)

            if self._curs: self._curs.close()
            if self._conn: self._conn.close()
            self._cI.close()
        except (EOFError,IOError): pass
        except Exception as e:
            if self._cI:
                rmsg = "Failed to clean up: {0}".format(e)
                self._cI.send((IYRI_WARN,'Collator','shutdown',rmsg))

#### private helper functions

    def _setup(self,conf):
        """
         connect to db w/ params in store & pass sensor up event
         :param conf: configuration details
        """
        try:
            self._dbstr = conf['store']
            self._local = conf['local']['thresher']
            self._local['opath'] = conf['local']['path']
            # connect to db
            self._conn = psql.connect(host=self._dbstr['host'],
                                      port=self._dbstr['port'],
                                      dbname=self._dbstr['db'],
                                      user=self._dbstr['user'],
                                      password=self._dbstr['pwd'])
            self._curs = self._conn.cursor()
            self._curs.execute("set time zone 'UTC';")
            self._conn.commit()
        except psql.OperationalError as e:
            if e.__str__().find('connect') > 0:
                raise RuntimeError('Collator:PostgreSQL:DB not running')
            elif e.__str__().find('authentication') > 0:
                raise RuntimeError('Collator:PostgreSQL:Invalid connection string')
            else:
                raise RuntimeError('Collator:PostgreSQL:DB error: {0}'.format(e))
        except Exception as e:
            raise RuntimeError("Collator:Unknown:{0}".format(e))

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