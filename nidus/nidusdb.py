#!/usr/bin/env python

""" nidusdb.py: interface to underlying nidus storage system 

Provides a common interface and access methods from Nidus request handlers to the 
underlying storage system, serving a two-fold service:
 1) remove necessity for request handler to 'understand' underlying storage system
    protocols
 2) allow for easier changes to storage system - NOTE: this file will have to be
    modified to fit the storage system
"""
__name__ = 'nidusdb'
__license__ = 'GPL'
__version__ = '0.1.1'
__date__ = 'January 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@hushmail.com'
__status__ = 'Development'

import os                                              # file paths
import time                                            # timestamps
import psycopg2 as psql                                # postgresql api
import ConfigParser                                    # config file
import threading                                       # sse threads
import Queue                                           # thread-safe queue
import wraith.radio.radiotap as rtap                   # 802.11 layer 1 parsing
from wraith.radio import mpdu                          # 802.11 layer 2 parsing
from wraith.radio import mcs                           # 802.11 mcs fcts
from wraith.radio import channels                      # 802.11 channels
from wraith.radio.oui import parseoui                  # out dict
from wraith.nidus import nmp                           # message protocol
from wraith.nidus.simplepcap import pcapopen, pktwrite # pcap writing
from wraith import ts2iso                              # timestamp convesion

class NidusDBException(Exception): pass                          # generic exception
class NidusDBServerException(NidusDBException): pass             # no server/failed to connect
class NidusDBAuthException(NidusDBException): pass               # authentication failure
class NidusDBSubmitException(NidusDBException): pass             # submit failed
class NidusDBSubmitParseException(NidusDBSubmitException): pass  # submit failed due to parsing
class NidusDBSubmitParamException(NidusDBSubmitException): pass  # one or more params are invalid
class NidusDBInvalidFrameException(NidusDBSubmitException): pass # frame does not follow standard

#### SSE functionality

# for now define the number of threads here (there will only be 1 saving thread
# for radio
NUM_STORE_THREADS   = 1
NUM_EXTRACT_THREADS = 1

# Task Definitions

class SaveTask(tuple):
    # noinspection PyInitNewSignature
    def __new__(cls,sid,ts,mac,frame):
        return super(SaveTask,cls).__new__(cls,tuple([sid,ts,mac,frame]))
    @property
    def sid(self): return self[0]
    @property
    def ts(self): return self[1]
    @property
    def mac(self): return self[2]
    @property
    def frame(self): return self[3]


class StoreTask(tuple):
    # noinspection PyInitNewSignature
    def __new__(cls,ts,mac,lFrame,l1,l2):
        return super(StoreTask,cls).__new__(cls,tuple([ts,mac,lFrame,l1,l2]))
    @property
    def ts(self): return self[0]
    @property
    def mac(self): return self[1]
    @property
    def length(self): return self[2]
    @property
    def l1(self): return self[3]
    @property
    def l2(self): return self[4]

class ExtractTask(tuple):
    # noinspection PyInitNewSignature
    def __new__(cls,sid,ts,l2):
        return super(ExtractTask,cls).__new__(cls,tuple([sid,ts,l2]))
    @property
    def sid(self): return self[0]
    @property
    def ts(self): return self[1]
    @property
    def l2(self): return self[2]

# Worker definitions

class SSEThread(threading.Thread):
    """ Super Class for a SaveStoreExtract worker thread """
    def __init__(self,tasks,db):
        """
         sid - current session id
         halt - stop event
         task - queue of tasks to pull from
         db - {True|False} db access is needed
        """
        threading.Thread.__init__(self)
        self._qT = tasks
        self._wDB = db

    def run(self):
        # connect to db
        conn = None
        if self._wDB:
            try:
                conn = self._dbconnect()
            except psql.OperationalError as e:
                if e.__str__().find('connect') > 0:
                    raise NidusDBServerException("Postgresql not running")
                elif e.__str__().find('authentication') > 0:
                    raise NidusDBAuthException("Invalid connection string")
                else:
                    raise NidusDBException("Database failure: %s" % e)

        # processing loop
        while True:
            item = self._qT.get()
            if item == '!STOP!': break
            self._consume(item,conn)

        # close db
        if conn and not conn.closed: conn.close()

    def _dbconnect(self):
        """ cnnnects to db returning a connection object"""
        # connect to db
        conn = psql.connect(host="localhost",dbname="nidus",
                                  user="nidus",password="nidus")
        curs = conn.cursor()
        curs.execute("set time zone 'UTC';")
        curs.close()
        conn.commit()
        return conn

    def _consume(self,item,conn):
        """ process the next item, using db connection conn if necessary """
        raise NotImplementedError

class SaveThread(SSEThread):
    def __init__(self,tasks,path,sz):
        """
         path - directory to store pcaps in
         sz - max size of pcap file
        """
        SSEThread.__init__(self,tasks,False)
        self._path = path
        self._sz = sz
        self._fout = None
    def _consume(self,item,conn=None):
        """ write the packet in item to file """
        fname = None
        if not self._fout or os.path.getsize(self._fout.name) > self._sz:
            if self._fout:
                self._fout.close()
                self._fout = None
            fname = os.path.join(self._path,"%d_%s_%s.pcap" % (item.sid,
                                                               item.ts,
                                                               item.mac))
        if not self._fout: self._fout = pcapopen(fname)
        pktwrite(self._fout,item.ts,item.frame)

class StoreThread(SSEThread):
    def __init__(self,tasks):
        SSEThread.__init__(self,tasks,True)
    def _consume(self,item,conn): pass

class ExtractThread(SSEThread):
    def __init__(self,db,tasks):
        SSEThread.__init__(self,tasks,True)
    def _consume(self,item,conn): pass

class NidusDB(object):
    """ NidusDB - interface to nidus database """
    def __init__(self,cpath=None):
        """ initialize NidusDB """
        self._conn = None           # connection to datastore
        self._curs = None           # cursor to datastore
        self._sid  = None           # session id for this sensor
        self._raw = {'store':False} # raw frame storage config
        self._oui = {}              # oui dict (oui->manufacturer)
        self._stas = {}             # stas seen this session

        # SSE variables
        self._qSave = {}               # one (or two) queues for each radio(s) saving
        self._tSave = {}               # one (or two) threads for each radio(s) saving
        self._qStore = None            # queue for storage
        self._tStores = []             # thread(s) for storing
        self._qExtract = None          # queue for extraction
        self._tExtracts = []           # thread(s) for extracting

        # parse the config file (if none set to defaults)
        if cpath:
            conf = ConfigParser.RawConfigParser()
            if not conf.read(cpath): raise NidusDBException('%s is invalid' % cpath)

            try:
                # raw frame storage
                if conf.has_section('STORE'):
                    self._raw['store'] = conf.getboolean('STORE','store')
                    if self._raw['store']:
                        self._raw['path'] = conf.get('STORE','path')
                        self._raw['sz'] = conf.getint('STORE','maxsize') * 1048576
                        self._raw['nfiles'] = conf.getint('STORE','maxfiles')

                # oui file
                if conf.has_option('OUI','path'):
                    self._oui = parseoui(conf.get('OUI','path'))
            except ConfigParser.NoOptionError as e:
                raise NidusDBException("%s" % e)

    def __del__(self):
        """ called during garbage collection forces shuts down connection """
        self.shutdown()

    def shutdown(self):
        """ closes open connections, cleans up """
        self.disconnect()

    def connect(self):
        """ client connects to NidusDB """
        try:
            # make connection, cursor and set session timezone to utc
            self._conn = psql.connect(host="localhost",
                                      dbname="nidus",
                                      user="nidus",
                                      password="nidus")
            self._curs = self._conn.cursor()
            self._curs.execute("set time zone 'UTC';")
            self._conn.commit()
        except psql.OperationalError as e:
            if e.__str__().find('connect') > 0:
                raise NidusDBServerException("Postgresql not running")
            elif e.__str__().find('authentication') > 0:
                raise NidusDBAuthException("Invalid connection string")
            else:
                raise NidusDBException("Database failure: %s" % e)
        except Exception as e:
            raise NidusDBException("Unknown failure: %s" % e)

    def disconnect(self):
        """ client disconnects from NidusDB """
        # close out database
        if self._conn and not self._conn.closed:
            self._curs.close()
            self._conn.close()

        # stop & wait on the sse threads
        for thread in self._tSave: # save threads
            self._qSave[thread].put('!STOP!')
            while self._tSave[thread].is_alive():
                self._tSave[thread].join(0.5)

    def submitdevice(self,f,ip=None):
        """ submitdevice - submit the string fields to the database """
        try:
            # tokenize the string f, convert to dict
            ds = nmp.data2dict(nmp.tokenize(f),"DEVICE")
            
            # what type of device
            if not ds['type'] in ['sensor','radio','gpsd']:
                raise NidusDBSubmitParamException("Invalid Device type %s" % ds['type'])                
            if ds['type'] == "sensor":
                self._setsensor(ds['ts'],ds['id'],ds['state'],ip)
            elif ds['type'] == "radio":
                self._setradio(ds['ts'],ds['id'],ds['state'])
            elif ds['type'] == 'gpsd':
                self._setgpsd(ds['ts'],ds['id'],ds['state'])
        except nmp.NMPException as e:
            raise NidusDBSubmitParseException(e)
        except psql.Error as e:
            # rollback so postgresql is not left in error state
            self._conn.rollback()
            raise NidusDBSubmitException("%s: %s" % (e.pgcode,e.pgerror))
        else:
            self._conn.commit()

    def submitdropped(self):
        """ sensor exited unexpectantly, close out open ended records """
        if not self._sid: return
        try:
            # get current time
            ts = ts2iso(time.time())
            
            # close out the sensor
            sql = """
                   update sensor set period = tstzrange(lower(period),%s) 
                   where session_id = %s;
                  """
            self._curs.execute(sql,(ts,self._sid))
            
            # close out radios
            # get radios currently used by sensor
            sql = " select mac from using_radio where sid=%s;"
            self._curs.execute(sql,(self._sid,))
            for row in self._curs.fetchall():
                mac = row[0]
                
                # close out radio_epoch
                sql = """
                       update radio_epoch set period = tstzrange(lower(period),%s)
                       where mac = %s and upper(period) is NULL;
                      """
                self._curs.execute(sql,(ts,mac))
                
                # close out radio_period
                sql = """
                       update radio_period set period = tstzrange(lower(period),%s)
                       where mac = %s and upper(period) is NULL;
                      """
                self._curs.execute(sql,(ts,mac))
                
                # close out using_radio
                sql = """
                       update using_radio set period = tstzrange(lower(period),%s)
                       where sid=%s and mac=%s;
                      """
                self._curs.execute(sql,(ts,self._sid,mac))
           
            # close out gpsd
            sql = """
                   update using_gpsd set period = tstzrange(lower(period),%s)
                   where sid=%s;
                  """
            self._curs.execute(sql,(ts,self._sid))
        except psql.Error:
            # don't raise an exception here, nidus is already exiting
            self._conn.rollback()
        else:
            self._conn.commit()    
 
    def submitgpsd(self,f):
        """ submitgpsd - submit the string fields to the database """
        try:
            # tokenize the string f and convert to dict
            ds = nmp.data2dict(nmp.tokenize(f),"GPSD")
            
            # submit to db
            # insert into the gpsd table (if it does not already exist)
            self._curs.execute("select * from gpsd where id=%s;",(ds['id'],))
            if not self._curs.fetchone():
                sql = "insert into gpsd values (%s,%s,%s,%s,%s,%s);"
                self._curs.execute(sql,(ds['id'],ds['vers'],ds['flags'],
                                        ds['driver'],ds['bps'],ds['path']))
            
            # insert into the using table
            sql = """
                  insert into using_gpsd (sid,gid,period)
                  values (%s,%s,tstzrange(%s,NULL,'[]'));
                """
            self._curs.execute(sql,(self._sid,ds['id'],ds['ts']))
        except nmp.NMPException as e:
            raise NidusDBSubmitParseException(e)
        except psql.Error as e:
            # rollback so postgresql is not left in error state
            self._conn.rollback() 
            raise NidusDBSubmitException("%s: %s" % (e.pgcode,e.pgerror))
        else:
            self._conn.commit()
        
    def submitradio(self,f):
        """ submitradio - submit the string fields to the database """
        # TODO: ensure we only get a radio submit once per radio
        try:
            # tokenize the string f and convert to dict
            ds = nmp.data2dict(nmp.tokenize(f),"RADIO")
            
            # submit to db
            # insert radio into radio table if it does not exist
            self._curs.execute("select * from radio where mac=%s;",(ds['mac'],))
            if not self._curs.fetchone():
                # truncate the strings to max length 20
                sql = """
                       insert into radio (mac,driver,chipset,channels,standards)
                       values (%s,%s,%s,%s,%s);
                      """
                self._curs.execute(sql,(ds['mac'],ds['driver'][0:20],
                                        ds['chipset'][0:20],ds['channels'],
                                        ds['standards'][0:20]))
            
            # insert epochal
            sql = """
                   insert into radio_epoch
                    (mac,role,ant_offset,ant_gain,ant_loss,ant_type,description,period)
                   values (%s,%s,%s,%s,%s,%s,%s,tstzrange(%s,NULL,'[]'));
                  """
            self._curs.execute(sql,(ds['mac'],ds['role'],ds['ant_offset'],ds['ant_gain'],
                                    ds['ant_loss'],ds['ant_type'],ds['desc'],ds['ts']))
            
            # insert periodic
            sql = """
                   insert into radio_period (mac,spoofed,txpwr,period)
                   values (%s,%s,%s,tstzrange(%s,NULL,'[]'));
                  """
            self._curs.execute(sql,(ds['mac'],ds['spoofed'],ds['txpwr'],ds['ts']))
            
            # insert using_radio
            sql = """
                   insert into using_radio (sid,mac,phy,nic,vnic,period)
                   values (%s,%s,%s,%s,%s,tstzrange(%s,NULL,'[]'));
                  """
            self._curs.execute(sql,(self._sid,ds['mac'],ds['phy'],ds['nic'],
                                    ds['vnic'],ds['ts']))

            # start save thread if save is enabled
            if self._raw['store']:
                self._qSave[ds['mac']] = Queue.Queue()
                self._tSave[ds['mac']] = SaveThread(self._qSave[ds['mac']],
                                                    self._raw['path'],
                                                    self._raw['sz'])
                self._tSave[ds['mac']].start()

        except nmp.NMPException as e:
            raise NidusDBSubmitParseException(e)
        except psql.Error as e:
            # rollback so postgresql is not left in error state
            self._conn.rollback() 
            raise NidusDBSubmitException("%s: %s" % (e.pgcode,e.pgerror))
        else:
            self._conn.commit()

    def submitradioevent(self,f):
        """ submitradioevent - submit the string fields to the database """
        try:
            # tokenize the string f and convert to dict
            ds = nmp.data2dict(nmp.tokenize(f),"RADIO_EVENT")
            
            sql = "insert into radio_event values (%s,%s,%s,%s);"
            self._curs.execute(sql,(ds['mac'],ds['event'],ds['params'],ds['ts']))
        except nmp.NMPException as e:
            raise NidusDBSubmitParseException(e)
        except psql.Error as e:
            self._conn.rollback()
            raise NidusDBSubmitException("%s: %s" % (e.pgcode,e.pgerror))
        else:
            self._conn.commit()

    def submitframe(self,f):
        """
         submitframe - submit the string fields to the database
          s - save frame to file
          s - store frame in data store
          e - extract details on nets/stas
        """
        # tokenize the data
        try:
            ds = nmp.data2dict(nmp.tokenize(f),"FRAME")
        except nmp.NMPException as e:
            raise NidusDBSubmitParseException(e)

        # parse radiotap and mpdu
        try:
            frame = ds['frame']
            dR = rtap.parse(frame)
            dM = mpdu.parse(frame[dR['sz']:], rtap.flags_get(dR['flags'],'fcs'))
        except (rtap.RadiotapException,mpdu.MPDUException):
            dR = {}
            dM = {}

        # send to queues
        if self._raw['store']:
            self._qSave[ds['mac']].put(SaveTask(self._sid,ds['ts'],
                                                ds['mac'],ds['frame']))
        #self._qStore.put((ds['ts'],ds['mac'],len(ds['frame']),dR,dM))
        #if dM: self._qExtract((ds['ts'],dM))
        
    def submitgeo(self,f):
        """ submitgeo - submit the string fields to the database """
        try:
            # tokenize the string f and convert to dict, convert lat/lon to mgrs
            ds = nmp.data2dict(nmp.tokenize(f),"GPS")

            # submit to db
            sql = "insert into geo values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);"
            self._curs.execute(sql,(ds['id'],ds['ts'],ds['coord'],ds['alt'],
                                    ds['spd'],ds['dir'],ds['fix'],ds['xdop'],
                                    ds['ydop'],ds['pdop'],ds['epx'],ds['epy']))
        except nmp.NMPException as e:
            print f
            raise NidusDBSubmitParseException(e)
        except psql.Error as e:
            self._conn.rollback()
            raise NidusDBSubmitException("%s: %s" % (e.pgcode,e.pgerror))
        else:
            self._conn.commit()

    #### NOTE: for all _set* functions commit or rollback is exec'd from caller

    def _setsensor(self,ts,did,state,ip):
        """ set the state of the sensor """
        # up or down
        if state:
            # open the sensor record
            # TODO: don't make a new session if one already exists
            sql="""
                 insert into sensor (hostname,ip,period)
                 values (%s,%s,tstzrange(%s,NULL,'[]')) RETURNING session_id;
                """
            self._curs.execute(sql,(did,ip,ts))
            self._sid = self._curs.fetchone()[0]
        else:
            sql = """
                   update sensor set period = tstzrange(lower(period),%s) 
                   where session_id = %s;
                  """
            self._curs.execute(sql,(ts,self._sid))

    def _setradio(self,ts,did,state):
        """ set the state of a radio """
        if not state:
            # close out radio_epochal,
            sql = """
                   update radio_epoch set period = tstzrange(lower(period),%s)
                   where mac = %s and upper(period) is NULL;
                  """
            self._curs.execute(sql,(ts,did))
            
            # radio_periodic
            sql = """
                   update radio_period set period = tstzrange(lower(period),%s)
                   where mac = %s and upper(period) is NULL;
                  """
            self._curs.execute(sql,(ts,did))
            
            # and using_radio record
            sql = """
                   update using_radio set period = tstzrange(lower(period),%s)
                   where sid = %s and mac = %s;
                  """
            self._curs.execute(sql,(ts,self._sid,did))

    def _setgpsd(self,ts,did,state):
        """ set the state of the gpsd """
        if not state:
            sql = """
                   update using_gpsd set period = tstzrange(lower(period),%s)
                   where sid = %s and gid = %s;
                  """
            self._curs.execute(sql,(ts,self._sid,did))

    def _manuf(self,mac):
        """ returns the manufacturer of the mac address if exists, otherwise 'unknown' """
        try:
            return self._oui[mac[:8]]
        except KeyError:
            return "unknown"