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
__version__ = '0.1.0'
__date__ = 'October 2014'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@hushmail.com'
__status__ = 'Development'

import os                                              # file paths
import time                                            # timestamps
import psycopg2 as psql                                # postgresql api
import ConfigParser                                    # config file
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

#### THREADS



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
        self._fout = None           # current file

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
        if self._conn and not self._conn.closed: self.disconnect()

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

        # close out current file (open)
        if self._fout: self._fout.close()

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
        except psql.Error as e:
            # rollback so postgresql is not left in error state
            self._conn.rollback()
            raise NidusDBSubmitException("%s: %s" % (e.pgcode,e.pgerror))
        except nmp.NMPException as e:
            raise NidusDBSubmitParseException(e)
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
        except psql.Error as e:
            # rollback so postgresql is not left in error state
            self._conn.rollback() 
            raise NidusDBSubmitException("%s: %s" % (e.pgcode,e.pgerror))
        except nmp.NMPException as e:
            raise NidusDBSubmitParseException(e)
        else:
            self._conn.commit()
        
    def submitradio(self,f):
        """ submitradio - submit the string fields to the database """
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
        except psql.Error as e:
            self._conn.rollback()
            raise NidusDBSubmitException("%s: %s" % (e.pgcode,e.pgerror))
        except nmp.NMPException as e:
            raise NidusDBSubmitParseException(e)
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

        # parse radiotap and mpdu (init everything to empty)
        try:
            frame = ds['frame']
            dR = rtap.parse(frame)
            dM = mpdu.parse(frame[dR['sz']:], rtap.flags_get(dR['flags'],'fcs'))
        except (rtap.RadiotapException,mpdu.MPDUException):
            # TODO: log reason for failure
            dR = {}
            dM = {}

        # execute SSE
        if self._raw['store']:
            # save frame if specfied
            try:
                self._save(ds['ts'],ds['mac'],ds['frame'])
            except IOError:
                pass
        self._store(ds['ts'],ds['mac'],len(ds['frame']),dR,dM)
        if dM: self._extract(ds['ts'],dM)
        
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

    def _save(self,ts,rdo,frame):
        """ saves frame fr to file """
        fname = None
        if os.path.getsize(self._fout.name) > self._raw['sz'] or not self._fout:
            self._fout.close()
            fname = os.path.join(self._raw['path'],
                                 "%d_%s_%s.pcap" % (self._sid,ts,rdo))
        if not self._fout or self._fout.closed: self._fout = pcapopen(fname)
        pktwrite(self._fout,ts,frame)

    def _store(self,ts,rdo,lF,dR,dM):
        """
         stores the frame to db where lF is the total length of the frame and
         dR and dM are the parsed radiotap and mpdu respectively
        """
        try:
            # insert the frame - if invalid stop after insertion and commit it
            sql = """
                   insert into frame (ts,bytes,bytesHdr,ampdu,fcs)
                   values (%s,%s,%s,%s,%s) RETURNING id;
                  """
            if not dR['sz']:
                self._curs.execute(ts,(lF,0,0,0))
                self._conn.commit()
                return

            # valid header, continue
            ampdu = int('a-mpdu' in dR['present'])
            self._curs.execute(sql,(ts,lF,dR['sz'],ampdu,rtap.flags_get(dR['flags'],
                                                                        'fcs')))
            fid = self._curs.fetchone()[0]

            # insert ampdu?
            if ampdu:
                sql = "insert into ampdu (fid,refnum,flags) values (%s,%s,%s);"
                self._curs.execute(sql,(fid,dR['a-mpdu'][0],dR['a-mpdu'][1]))

            # insert the source record
            ant = dR['antenna'] if 'antenna' in dR else 0
            pwr = dR['antsignal'] if 'antsignal' in dR else 0
            sql = "insert into source (fid,src,antenna,rfpwr) values (%s,%s,%s,%s);"
            self._curs.execute(sql,(fid,rdo,ant,pwr))

            # insert signal record
            # determine the standard, rate and mcs fields
            # TODO: is b,g differentiation enough, notify if vht found
            try:
                std = 'n'
                mcsflags = rtap.mcsflags_params(dR['mcs'][0],dR['mcs'][1])
                if mcsflags['bw'] == rtap.MCS_BW_20: bw = '20'
                elif mcsflags['bw'] == rtap.MCS_BW_40: bw = '40'
                elif mcsflags['bw'] == rtap.MCS_BW_20L: bw = '20L'
                else: bw = '20U'
                width = 40 if bw == '40' else 20
                gi = 1 if 'gi' in mcsflags and mcsflags['gi'] > 0 else 0
                ht = 1 if 'ht' in mcsflags and mcsflags['ht'] > 0 else 0
                index = dR['mcs'][2]
                rate = mcs.mcs_rate(dR['mcs'][2],width,gi)
                hasMCS = 1
            except:
                if dR['channel'][0] in channels.ISM_24_F2C:
                    if rtap.chflags_get(dR['channel'][1],'cck'):
                        std = 'b'
                    else:
                        std = 'g'
                else:
                    std = 'a'
                rate = dR['rate'] * 0.5
                bw = None
                gi = None
                ht = None
                index = None
                hasMCS = 0

            # NOTE: we assume that channels will always be present in radiotap
            sql = """
                   insert into signal (fid,std,rate,channel,chflags,rf,ht,
                                       mcs_bw,mcs_gi,mcs_ht,mcs_index)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
                  """
            self._curs.execute(sql,(fid,std,rate,channels.f2c(dR['channel'][0]),
                                    dR['channel'][1],dR['channel'][0],hasMCS,
                                    bw,gi,ht,index))

            # insert traffic
            if dM:
                sql = """
                       insert into traffic (fid,fc_type,fc_subtype,fc_flags,
                                            duration,addr1,addr2,addr3,
                                            sc_fragnum,sc_seqnum,addr4)
                       values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
                      """
                self._curs.execute(sql,(fid,
                                        mpdu.FT_TYPES[dM['framectrl']['type']],
                                        mpdu.subtypes(dM['framectrl']['type'],
                                                      dM['framectrl']['subtype']),
                                        dM['framectrl']['flags'],
                                        dM['duration'],
                                        dM['addr1'],
                                        dM['addr2'] if 'addr2' in dM else None,
                                        dM['addr3'] if 'addr3' in dM else None,
                                        dM['seqctrl']['fragno'] if 'seqctrl' in dM else None,
                                        dM['seqctrl']['seqno'] if 'seqctrl' in dM else None,
                                        dM['addr4'] if 'addr4' in dM else None))
        except psql.Error as e:
            self._conn.rollback()
            raise NidusDBSubmitException("%s: %s" % (e.pgcode,e.pgerror))
        else:
            self._conn.commit()

    def _extract(self,ts,m):
        """  extract extract and store details of networks/stas etc from mpdu dict m """
        # get all mac addresses
        # Function To DS From DS Address 1 Address 2 Address 3 Address 4
        # IBSS/Intra   0    0        RA=DA     TA=SA     BSSID       N/A
        # From AP      0    1        RA=DA  TA=BSSID        SA       N/A
        # To AP        1    0     RA=BSSID     TA=SA        DA       N/A
        # Wireless DS  1    1     RA=BSSID  TA=BSSID     DA=WDS    SA=WDS

        # determine if each station exists already addr1 will always be present
        sql = "select sid,id,mac from sta where mac=%s"
        addrs = {m['addr1'].lower():{'loc':[1],'id':None}}

        # for addr2 thru addr4, if its present and not already being checked,
        # add to sql query
        if 'addr2' in m:
            a = m['addr2'].lower()
            if a in addrs:
                addrs[a]['loc'].append(2)
            else:
                addrs[a] = {'loc':[2],'id':None}
                sql += " or mac=%s"
            if 'addr3' in m:
                a = m['addr3'].lower()
                if a in addrs:
                    addrs[a]['loc'].append(3)
                else:
                    addrs[a] = {'loc':[3],'id':None}
                    sql += " or mac=%s"
                if 'addr4' in m:
                    a = m['addr4'].lower()
                    if a in addrs:
                        addrs[a]['loc'].append(4)
                    else:
                        addrs[a] = {'loc':[4],'id':None}
                        sql += " or mac=%s"

        # add non-broadcast addr(s) if not already present
        try:
            # get rows for any sta with given mac addr
            self._curs.execute(sql,tuple(addrs.keys()))
            rows = self._curs.fetchall()
            for addr in addrs:
                # if not broadcast, add sta id if found
                if addr == mpdu.BROADCAST: continue
                for row in rows:
                    if addr == row[2]:
                        addrs[addr]['id'] = row[1]
                        break

                # check current addr for an id, if not present add it
                if not addrs[addr]['id']:
                    sql = """
                           insert into sta (sid,spotted,mac,manuf,note)
                           values (%s,%s,%s,%s,%s)
                           RETURNING id;
                          """
                    self._curs.execute(sql,(self._sid,ts,addr,self._manuf(addr),""))
                    addrs[addr]['id'] = self._curs.fetchone()[0]

                # add/update sta activity for this session
                mode = 'rx'
                if 2 in addrs[addr]['loc']: mode = 'tx'

                if addr in self._stas:
                    # update timestamps
                    if mode == 'tx':
                        self._stas[addr]['fh'] = ts
                        self._stas[addr]['lh'] = ts
                    else:
                        self._stas[addr]['fs'] = ts
                        self._stas[addr]['ls'] = ts

                    # insert the record
                    sql = """
                           update sta_activity
                           set firstSeen=%s,lastSeen=%s,firstHeard=%s,lastHeard=%s
                           where sid = %s and staid = %s;
                          """
                    self._curs.execute(sql,(self._stas[addr]['fs'],
                                            self._stas[addr]['ls'],
                                            self._stas[addr]['fh'],
                                            self._stas[addr]['lh'],
                                            self._sid,self._stas[addr]['id']))
                else:
                    # create a new entry for this sta
                    self._stas[addr] = {'id':addrs[addr]['id'],
                                        'fs':None,'ls':None,
                                        'fh':None,'lh':None}
                    if mode == 'tx':
                        self._stas[addr]['fh'] = ts
                        self._stas[addr]['lh'] = ts
                    else:
                        self._stas[addr]['fs'] = ts
                        self._stas[addr]['ls'] = ts

                    # and insert it
                    sql = """
                           insert into sta_activity (sid,staid,firstSeen,lastSeen,
                                                     firstHeard,lastHeard)
                           values (%s,%s,%s,%s,%s,%s);
                          """
                    self._curs.execute(sql,(self._sid,self._stas[addr]['id'],
                                            self._stas[addr]['fs'],
                                            self._stas[addr]['ls'],
                                            self._stas[addr]['fh'],
                                            self._stas[addr]['lh']))
        except psql.Error as e:
            self._conn.rollback()
            raise NidusDBSubmitException("%s: %s" % (e.pgcode,e.pgerror))
        else:
            self._conn.commit()

        #flags = mpdu.fcfields_all(m['framectrl']['flags'])
        #if flags['td'] and flags['fd']:
        #    # bridge: betw/ DS
        #    pass
        #elif flags['td'] and not flags['fd']:
        #    # STA -> AP
        #    pass
        #elif not flags['td'] and not flags['fd']:
        #    # AP -> STA
        #    pass
        #else:
        #    # IBSS/intra
        #    pass

    def _manuf(self,mac):
        """ returns the manufacturer of the mac address if exists, otherwise 'unknown' """
        try:
            return self._oui[mac[:8]]
        except KeyError:
            return "unknown"