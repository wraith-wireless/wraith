#!/usr/bin/env python

""" nidusdb.py: interface to underlying nidus storage system

Provides a common interface and access methods from Nidus request handlers to the
underlying storage system, serving a two-fold service:
 1) remove necessity for request handler to 'understand' underlying storage system
    protocols (of course, will have to code a new nidusdb to handle different db)
 2) remove necessity for data provider i.e. a sensor to 'understand' underlying
    storage system
"""
__name__ = 'nidusdb'
__license__ = 'GPL v3.0'
__version__ = '0.1.3'
__date__ = 'January 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import time                                          # timestamps
import psycopg2 as psql                              # postgresql api
import ConfigParser                                  # config file
import threading                                     # sync items
import Queue                                         # thread-safe queue
import zlib                                          # decompress bulk frames
import wraith.radio.radiotap as rtap                 # 802.11 layer 1 parsing
from wraith.radio import mpdu                        # 802.11 layer 2 parsing
from wraith.radio.oui import parseoui   # oui functions
from wraith.nidus import nmp                         # message protocol
from wraith.nidus import sse                         # worker threads
from wraith.utils.timestamps import ts2iso           # timestamp convesion

class NidusDBException(Exception): pass                          # generic exception
class NidusDBServerException(NidusDBException): pass             # no server/failed to connect
class NidusDBAuthException(NidusDBException): pass               # authentication failure
class NidusDBSubmitException(NidusDBException): pass             # submit failed
class NidusDBSubmitParseException(NidusDBSubmitException): pass  # submit failed due to parsing
class NidusDBSubmitParamException(NidusDBSubmitException): pass  # one or more params are invalid
class NidusDBInvalidFrameException(NidusDBSubmitException): pass # frame does not follow standard

class NidusDB(object):
    """ NidusDB - interface to nidus database """
    def __init__(self,cpath=None):
        """ initialize NidusDB """
        self._conn = None           # connection to datastore
        self._curs = None           # cursor to datastore
        self._sid  = None           # session id for this sensor
        self._gid  = None           # gpsd id
        self._storage = {}          # psql connect parameters
        self._raw = {'store':False} # raw frame storage config
        self._oui = {}              # oui dict (oui->manufacturer)

        # SSE variables
        self._lSta = None           # lock on the stas
        self._qSave = {}            # one (or two) queues for each radio(s) saving
        self._tSave = {}            # one (or two) threads for each radio(s) saving
        self._qStore = None         # queue for storage
        self._nStore = 1            # num threads for storing default is 1
        self._tStore = []           # thread(s) for storing
        self._qExtract = None       # queue for extraction
        self._nExtract = 1          # num threads for extracting default is 1
        self._tExtract = []         # thread(s) for extracting

        # parse the config file
        if cpath:
            cp = ConfigParser.RawConfigParser()
            if not cp.read(cpath): raise NidusDBException('%s is invalid' % cpath)

            # save section of SSE
            try:
                # storage section
                self._storage = {'host':cp.get('Storage','host'),
                                 'port':cp.getint('Storage','port'),
                                 'db':cp.get('Storage','db'),
                                 'user':cp.get('Storage','user'),
                                 'pwd':cp.get('Storage','pwd')}

                # sse section
                self._raw['save'] = cp.getboolean('SSE','save')
                if self._raw['save']:
                    self._raw['private'] = cp.get('SSE','save_private')
                    self._raw['path'] = cp.get('SSE','save_path')
                    self._raw['sz'] = cp.getint('SSE','save_maxsize') * 1048576
                    self._raw['nfiles'] = cp.getint('SSE','save_maxfiles')

                # number of storing and extracting threads
                self._nStore = cp.getint('SSE','store_threads')
                self._nExtract = cp.getint('SSE','extract_threads')
            except ValueError as e:
                raise NidusDBException("%s" % e)
            except (ConfigParser.NoSectionError,ConfigParser.NoOptionError) as e:
                raise NidusDBException("%s" % e)

            # oui file
            if cp.has_option('OUI','path'):
                self._oui = parseoui(cp.get('OUI','path'))
        else:
            # need to set defaults?
            pass

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
            self._conn = psql.connect(host=self._storage['host'],
                                      port=self._storage['port'],
                                      dbname=self._storage['db'],
                                      user=self._storage['user'],
                                      password=self._storage['pwd'])
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
        try:
            # stop & wait on the sse threads
            for _ in self._tStore: self._qStore.put('!STOP!')
            for thread in self._tStore:
                if thread.is_alive(): thread.join()

            for _ in self._tExtract: self._qExtract.put('!STOP!')
            for thread in self._tExtract:
                if thread.is_alive(): thread.join()

            for thread in self._tSave:
                self._qSave[thread].put('!STOP!')
                if self._tSave[thread].is_alive(): self._tSave[thread].join()
        except:
            # blanket exception
            pass
        finally:
            # close out database
            if self._curs: self._curs.close()
            if self._conn: self._conn.close()

    def submitdevice(self,f,ip=None):
        """ submitdevice - submit the string fields to the database """
        try:
            # tokenize the string f, convert to dict
            ds = nmp.data2dict(nmp.tokenize(f),'DEVICE')

            # what type of device -> note: radio and gpsd are set 'up
            # in submitradio and submitgpsd
            if not ds['type'] in ['sensor','radio','gpsd']:
                raise NidusDBSubmitParamException("Invalid Device type")
            if ds['type'] == 'sensor':
                try:
                    self._setsensor(ds['ts'],ds['id'],ds['state'],ip)
                except sse.SSEDBException as e:
                    # a thread failed to connect - reraise as dbsubmitexception
                    self._conn.rollback()
                    raise NidusDBSubmitException("submit device %s" % e.__repr__())
                except psql.Error as e:
                    # most likely a sensor attempting to log in when it is
                    # data from it's most recent connect is still being processed
                    # NOTE: a runtimeerror will result in the nidus responehandler
                    #  attempting to submitdropped(). Since no sid was attained
                    #  this->submitdropped() will return without effect
                    self._conn.rollback()
                    raise RuntimeError("submit device %s: %s" % (e.pgcode,e.pgerror))
            elif ds['type'] == 'radio': self._setradio(ds['ts'],ds['id'],ds['state'])
            elif ds['type'] == 'gpsd': self._setgpsd(ds['ts'],ds['state'])
        except nmp.NMPException as e:
            raise NidusDBSubmitParseException(e)
        except psql.Error as e:
            # rollback so postgresql is not left in error state
            self._conn.rollback()
            raise NidusDBSubmitException("submit device %s: %s" % (e.pgcode,e.pgerror))
        except Exception as e:
            # blanket except
            self._conn.rollback()
            raise NidusDBSubmitException("submit device type(%s) %s" % (type(e),e.__repr__()))
        else:
            self._conn.commit()

    def submitplatform(self,f):
        """ submit platform details """
        try:
            # tokenize
            ds = nmp.data2dict(nmp.tokenize(f),'PLATFORM')

            sql = """
                   insert into platform (sid,os,dist,version,name,kernel,machine,
                                         pyvers,pycompiler,pylibcvers,pybits,
                                         pylinkage,region)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
                  """
            self._curs.execute(sql,(self._sid,ds['os'],ds['dist'],ds['osv'],
                                    ds['name'],ds['kernel'],ds['machine'],ds['pyv'],
                                    ds['compiler'],ds['libcv'],ds['bits'],ds['link'],
                                    ds['regdom']))
        except nmp.NMPException as e:
            raise NidusDBSubmitParseException("submit platform %s" % e)
        except psql.Error as e:
            # roll back
            self._conn.rollback()
            raise NidusDBSubmitException("submit platform %s: %s" % (e.pgcode,e.pgerror))
        except Exception as e:
            # blanket exception
            self._conn.rollback()
            raise NidusDBSubmitException("submit platform type(%s) %s" % (type(e),e.__repr__()))
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
        except:
            # don't raise an exception here, nidus is already exiting
            self._conn.rollback()
        else:
            self._conn.commit()

    def submitgpsd(self,f):
        """ submitgpsd - submit the string fields to the database """
        try:
            # tokenize the string f and convert to dict
            ds = nmp.data2dict(nmp.tokenize(f),'GPSD')

            # submit to db
            # insert into the gpsd table (if it does not already exist)
            self._curs.execute("select gpsd_id from gpsd where devid=%s;",(ds['id'],))
            row = self._curs.fetchone()
            if not row:
                sql = """
                       insert into gpsd (devid,version,flags,driver,bps,tty)
                       values (%s,%s,%s,%s,%s,%s) returning gpsd_id;
                      """
                self._curs.execute(sql,(ds['id'],ds['vers'],ds['flags'],
                                        ds['driver'],ds['bps'],ds['path']))
                self._gid = self._curs.fetchone()[0]
            else:
                self._gid = row[0]

            # insert into the using table
            sql = """
                  insert into using_gpsd (sid,gid,period)
                  values (%s,%s,tstzrange(%s,NULL,'[]'));
                """
            self._curs.execute(sql,(self._sid,self._gid,ds['ts']))
        except nmp.NMPException as e:
            raise NidusDBSubmitParseException("submit gspd %s" % e)
        except psql.Error as e:
            # rollback so postgresql is not left in error state
            self._conn.rollback()
            raise NidusDBSubmitException("submit gpsde %s: %s" % (e.pgcode,e.pgerror))
        else:
            self._conn.commit()

    def submitradio(self,f):
        """ submitradio - submit the string fields to the database """
        try:
            # tokenize the string f and convert to dict
            ds = nmp.data2dict(nmp.tokenize(f),'RADIO')

            # submit to db
            # insert radio into radio table if it does not exist
            self._curs.execute("select * from radio where mac=%s;",(ds['mac'],))
            if not self._curs.fetchone():
                # truncate the strings to max length 20
                sql = """
                       insert into radio (mac,driver,chipset,channels,standards,description)
                       values (%s,%s,%s,%s,%s,%s);
                      """
                self._curs.execute(sql,(ds['mac'],ds['driver'][0:20],
                                        ds['chipset'][0:20],ds['channels'],
                                        ds['standards'][0:20],ds['desc'][0:100]))

            # insert using_radio
            sql = """
                   insert into using_radio (sid,mac,phy,nic,vnic,role,period)
                   values (%s,%s,%s,%s,%s,%s,tstzrange(%s,NULL,'[]'));
                  """
            self._curs.execute(sql,(self._sid,ds['mac'],ds['phy'],ds['nic'],
                                    ds['vnic'],ds['role'],ds['ts']))

            sql = "insert into radio_event (mac,state,params,ts) values (%s,%s,%s,%s);"
            # insert initial events (spoof if any, and txpwr
            print 'spoofed: ', ds['spoofed']
            print 'txpwr: ', ds['txpwr']
            if ds['spoofed']:# and ds['spoofed'] != 'None':
                self._curs.execute(sql,(ds['mac'],'spoof',ds['spoofed'],ds['ts']))
            self._curs.execute(sql,(ds['mac'],'txpwr',ds['txpwr'],ds['ts']))

            # start save thread if save is enabled
            if self._raw['save']:
                self._qSave[ds['mac']] = Queue.Queue()
                self._tSave[ds['mac']] = sse.SaveThread(self._qSave[ds['mac']],
                                                        self._raw['path'],
                                                        self._raw['private'],
                                                        self._raw['sz'],
                                                        (self._storage['host'],
                                                         self._storage['port'],
                                                         self._storage['db'],
                                                         self._storage['user'],
                                                         self._storage['pwd']))
                self._tSave[ds['mac']].start()

        except nmp.NMPException as e:
            raise NidusDBSubmitParseException("submit radio %s" % e)
        except psql.Error as e:
            # rollback so postgresql is not left in error state
            self._conn.rollback()
            raise NidusDBSubmitException("submit radio %s: %s" % (e.pgcode,e.pgerror))
        except NidusDBException:
            # our save thread failed to connect to database - reraise
            self._conn.rollback()
            raise NidusDBSubmitException("submit radio connect error")
        except Exception as e:
            # blanket exception
             self._conn.rollback()
             raise NidusDBException("submit radio type(%s) %s" % (type(e),e.__repr__()))
        else:
            self._conn.commit()

    def submitantenna(self,f):
        """ submitantenna - submit the string fields to the database """
        try:
            # tokenize f and convert to dict and insert into db
            ds = nmp.data2dict(nmp.tokenize(f),'ANTENNA')
            sql = """
                   insert into antenna (mac,ind,gain,loss,x,y,z,type,ts)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s);
                  """
            self._curs.execute(sql,(ds['mac'],ds['index'],ds['gain'],ds['loss'],
                                    ds['x'],ds['y'],ds['z'],ds['type'],ds['ts']))
        except nmp.NMPException as e:
            raise NidusDBSubmitParseException("submit antenna %s" % e)
        except psql.Error as e:
            self._conn.rollback()
            raise NidusDBSubmitException("submit antenna %s: %s" % (e.pgcode,e.pgerror))
        except Exception as e:
            # blannket
            self._conn.rollback()
            raise NidusDBSubmitException("submit antenna type(%s) %s" % (type(e),e.__repr__()))
        else:
            self._conn.commit()

    def submitradioevent(self,f):
        """ submitradioevent - submit the string fields to the database """
        try:
            # tokenize the string f and convert to dict and insert into db
            ds = nmp.data2dict(nmp.tokenize(f),'RADIO_EVENT')
            sql = """
                   insert into radio_event (mac,state,params,ts)
                   values (%s,%s,%s,%s);
                  """
            self._curs.execute(sql,(ds['mac'],ds['event'],ds['params'],ds['ts']))
        except nmp.NMPException as e:
            raise NidusDBSubmitParseException("submit radio event" % e)
        except psql.Error as e:
            self._conn.rollback()
            raise NidusDBSubmitException("submit radio event %s: %s" % (e.pgcode,e.pgerror))
        except Exception as e:
            # blannket
            self._conn.rollback()
            raise NidusDBSubmitException("submit radio event type(%s) %s" % (type(e),e.__repr__()))
        else:
            self._conn.commit()

    def submitbulk(self,f):
        """ submitbulk - submit string fields (multiple frames) to the database """
        # tokenize the data & decompress the frames
        try:
            ds = nmp.data2dict(nmp.tokenize(f),'BULK')
            frames = zlib.decompress(ds['frames'])
            mac = ds['mac']
            fs = frames.split('\x1FFE\x1E') # split by end delimiter
            for f in fs:
                if not f: continue
                f = f.split('\x1EFB\x1F')
                self._submitframe(mac,f[0].strip(),f[1])
        except nmp.NMPException as e:
            raise NidusDBSubmitParseException("submit bulk %s" % e)
        except zlib.error as e:
            raise NidusDBSubmitParseException("submit bulk zip error %s" % e)
        except Exception as e:
            # blanket
            self._conn.rollback()
            raise NidusDBSubmitException("submit bulk type(%s) %s" % (type(e),e.__repr__()))

    # depecrated
    def submitsingle(self,f):
        """ submitsingle - submit the string fields (single frame) to the database """
        # tokenize the data
        try:
            ds = nmp.data2dict(nmp.tokenize(f),'FRAME')
        except nmp.NMPException as e:
            raise NidusDBSubmitParseException(e)
        self._submitframe(ds['mac'],ds['ts'],ds['frame'])

    def submitgeo(self,f):
        """ submitgeo - submit the string fields to the database """
        try:
            # tokenize the string f and convert to dict, convert lat/lon to mgrs
            ds = nmp.data2dict(nmp.tokenize(f),'GPS')

            # submit to db
            sql = """
                   insert into geo (sid,ts,coord,alt,spd,dir,
                                    fix,xdop,ydop,pdop,epx,epy)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
                  """
            self._curs.execute(sql,(self._sid,ds['ts'],ds['coord'],ds['alt'],
                                    ds['spd'],ds['dir'],ds['fix'],ds['xdop'],
                                    ds['ydop'],ds['pdop'],ds['epx'],ds['epy']))
        except nmp.NMPException as e:
            raise NidusDBSubmitParseException("submit geo %s" % e)
        except psql.Error as e:
            self._conn.rollback()
            raise NidusDBSubmitException("submit geo %s: %s" % (e.pgcode,e.pgerror))
        except Exception as e:
            # blanket
            self._conn.rollback()
            raise NidusDBSubmitException("submit geo type(%s) %s" % (type(e),e.__repr__()))
        else:
            self._conn.commit()

    ### NOTE: for all _set* functions commit or rollback is executed from caller

    def _setsensor(self,ts,did,state,ip):
        """ set the state of the sensor """
        # up or down
        if state:
            # open the sensor record
            sql="""
                 insert into sensor (hostname,ip,period)
                 values (%s,%s,tstzrange(%s,NULL,'[]')) RETURNING session_id;
                """
            self._curs.execute(sql,(did,ip,ts))
            self._sid = self._curs.fetchone()[0]

            # start extract and store threads here - save threads will be
            # started in the submitradio function
            # store threads
            self._qStore = Queue.Queue()
            for i in xrange(self._nStore):
                thread = sse.StoreThread(self._qStore,self._sid,(self._storage['host'],
                                                                 self._storage['port'],
                                                                 self._storage['db'],
                                                                 self._storage['user'],
                                                                 self._storage['pwd']))
                thread.start()
                self._tStore.append(thread)

            # extract threads
            self._lSta = threading.Lock()
            self._qExtract = Queue.Queue()
            for i in xrange(self._nExtract):
                thread = sse.ExtractThread(self._qExtract,self._lSta,self._sid,
                                           self._oui,(self._storage['host'],
                                                      self._storage['port'],
                                                      self._storage['db'],
                                                      self._storage['user'],
                                                      self._storage['pwd']))
                thread.start()
                self._tExtract.append(thread)
        else:
            # close out the sensor record
            sql = """
                   update sensor set period = tstzrange(lower(period),%s)
                   where session_id = %s;
                  """
            self._curs.execute(sql,(ts,self._sid))

    def _setradio(self,ts,did,state):
        """ set the state of a radio """
        if not state:
            # close out  using_radio record
            sql = """
                   update using_radio set period = tstzrange(lower(period),%s)
                   where sid = %s and mac = %s;
                  """
            self._curs.execute(sql,(ts,self._sid,did))

    def _setgpsd(self,ts,state):
        """ set the state of the gpsd """
        if not state:
            sql = """
                   update using_gpsd set period = tstzrange(lower(period),%s)
                   where sid = %s and gid = %s;
                  """
            self._curs.execute(sql,(ts,self._sid,self._gid))

    def _submitframe(self,mac,ts,f):
        """ submit frame collected by mac at time t """
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
            vs = (self._sid,ts,lF,0,0,[0,lF],0,'none',0)
        except mpdu.MPDUException:
            # the radiotap was valid but mpdu failed - initialize empty mpdu
            validMPDU = False
            vs = (self._sid,ts,lF,dR['sz'],0,[dR['sz'],lF],dR['flags'],
                  int('a-mpdu' in dR['present']),rtap.flags_get(dR['flags'],'fcs'))
        except Exception as e:
            # catch all
            raise NidusDBSubmitException("submit frame type<%s> %s" % (type(e),e.__repr__()))
        else:
            vs = (self._sid,ts,lF,dR['sz'],dM.offset,
                  [(dR['sz']+dM.offset),(lF-dM.stripped)],dR['flags'],
                  int('a-mpdu' in dR['present']),rtap.flags_get(dR['flags'],'fcs'))

        # insert the frame
        sql = """
               insert into frame (sid,ts,bytes,bRTAP,bMPDU,data,flags,ampdu,fcs)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s) returning frame_id;
              """
        try:
            self._curs.execute(sql,vs)
            fid = self._curs.fetchone()[0]
        except psql.Error as e:
            self._conn.rollback()
            raise NidusDBSubmitException("submit frame %s: %s" % (e.pgcode,e.pgerror))
        else:
            self._conn.commit()

        # put task(s) on SSE queues
        # S: frame will always be saved (if specified in config file
        # S: frame will be 'stored' if radiotap is valid
        # E: frame will be 'extracted' if mpdu is valid
        if self._raw['save']:
            # setup our left/right boundaries for privacy feature
            l = r = 0
            if validRTAP: l += dR['sz']
            if validMPDU:
                l += dM.offset
                r = lF-dM.stripped
            self._qSave[mac].put(sse.SaveTask(ts,fid,self._sid,mac,f,(l,r)))
        if validRTAP: self._qStore.put(sse.StoreTask(fid,mac,dR,dM))
        if validMPDU: self._qExtract.put(sse.ExtractTask(ts,fid,dM))