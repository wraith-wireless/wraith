#!/usr/bin/env python

""" geo.py: GPS device and front-line trace

Processes and forwards GPS device and locational data
"""
__name__ = 'gpsctl'
__license__ = 'GPL v3.0'
__version__ = '0.0.1'
__date__ = 'September 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import time                                # for timestamps
import socket                              # connection to gps device
import signal                              # handling signals
import mgrs                                # lat/lon to mgrs conversion
import gps                                 # gps device access
import multiprocessing as mp               # multiprocessing
from wraith.utils.timestamps import ts2iso # ts conversion

class GPSController(mp.Process):
    """ periodically checks gps for current location """
    def __init__(self,comms,conn,conf):
        """
         comms - internal communication
         conn - connection to/from Iyri
         conf - config file for gps
        """
        mp.Process.__init__(self)
        self._icomms = comms          # communications queue
        self._cI = conn               # connection to/from Iyri
        self._fixed = False           # fixed/dynamic
        self._poll = 0.5              # poll time
        self._qpx = float('inf')      # x quality
        self._qpy = float('inf')      # y quality
        self._gpsd = None             # connection to the gps device
        self._dd = {'id':'xxxx:xxxx', # device details (init to static)
                  'version':'0.0',
                  'flags':0,
                  'driver':'static',
                  'bps':0,
                  'path':'None'}
        self._defFLT = None           # default (static) flt
        self._m = None                # mgrs converter
        self._setup(conf)

    def terminate(self): pass

    def run(self):
        """ query for current location """
        # ignore signals being used by main program
        signal.signal(signal.SIGINT,signal.SIG_IGN)
        signal.signal(signal.SIGTERM,signal.SIG_IGN)

        # get and transmit device details
        if not self._devicedetails(): return
        self._icomms.put((self._dd['id'],ts2iso(time.time()),'!GPSD!',self._dd))

        # if fixed location, send the frontline trace & stopping details
        if self._fixed: self._icomms.put((self._dd['id'],ts2iso(time.time()),
                                          '!FLT!',self._defFLT))

        # 2 Location loop (only if dynamic)
        while not self._fixed:
            if self._cI.poll(self._poll) and self._cI.recv() == '!STOP!': break
            while self._gpsd.waiting():
                # recheck if we need to stop
                if self._cI.poll() and self._cI.recv() == '!STOP!': break
                rpt = self._gpsd.next()
                if rpt['class'] != 'TPV': continue
                try:
                    if rpt['epx'] > self._qpx or rpt['epy'] > self._qpy: continue
                    else:
                        flt = {'id':self._dd['id'],
                               'fix':rpt['mode'],
                               'coord':self._m.toMGRS(rpt['lat'],rpt['lon']),
                               'epy':rpt['epy'],
                               'epx':rpt['epx'],
                               'alt':rpt['alt'] if 'alt' in rpt else float("nan"),
                               'dir':rpt['track'] if 'track' in rpt else float("nan"),
                               'spd':rpt['spd'] if 'spd' in rpt else float("nan"),
                               'dop':{'xdop':'%.3f' % self._gpsd.xdop,
                                      'ydop':'%.3f' % self._gpsd.ydop,
                                      'pdop':'%.3f' % self._gpsd.pdop}}
                        self._icomms.put((self._dd['id'],ts2iso(time.time()),
                                          '!FLT!',flt))
                        break
                except (KeyError,AttributeError):
                    # a KeyError means not all values are present, an
                    # AttributeError means not all dop values are present
                    pass
                except: # blanket exception
                    break

        # send stop & close out connections
        self._icomms.put((self._dd['id'],ts2iso(time.time()),'!GPSD!',None))
        if self._gpsd: self._gpsd.close()
        self._cI.close()

    def _devicedetails(self):
        """ Device Details Loop - get complete details or quit on done """
        while self._dd['flags'] is None: # static is initiated already
            if self._cI.poll(self._poll) and self._cI.recv() == '!STOP!': return False
            else:
                # loop while data is on serial, checking each time if we need to stop
                while self._gpsd.waiting():
                    if self._cI.poll() and self._cI.recv() == '!STOP!': return False
                    dev = self._gpsd.next()
                    try:
                        if dev['class'] == 'VERSION':
                            self._dd['version'] = dev['release']
                        elif dev['class'] == 'DEVICE':
                            # flags not present until identifiable packets come
                            # from device
                            self._dd['flags'] = dev['flags']
                            self._dd['driver'] = dev['driver']
                            self._dd['bps'] = dev['bps']
                            self._dd['path'] = dev['path']
                    except KeyError:
                        pass
                    except:
                        return False
        self._cI.send(('info','GPSD','Connect',"GPS v%s connected" % self._dd['version']))
        return True

    def _setup(self,conf):
        """ attempt to connect to device if fixed is off """
        # if dynamic, attempt connect to device otherwise configure static flt
        self._fixed = True if conf['fixed'] else False
        self._m = mgrs.MGRS()
        if not self._fixed:
            # pull out parameters & configure empty device details
            self._poll = conf['poll']
            self._qpx = conf['epx']
            self._qpy = conf['epy']
            self._dd = {'id':conf['id'],
                        'version':None,
                        'driver':None,
                        'bps':None,
                        'path':None,
                        'flags':None}

            # connect to device
            try:
                self._gpsd = gps.gps('127.0.0.1',conf['port'])
                self._gpsd.stream(gps.WATCH_ENABLE)
            except socket.error as e:
                raise RuntimeError(e)
        else:
            # save default location
            self._defFLT = {'id':self._dd['id'],'fix':-1,
                            'coord':self._m.toMGRS(conf['lat'],conf['lon']),
                            'epy':0.0,'epx':0.0,'spd':0.0,
                            'alt':conf['alt'],'dir':conf['dir'],
                            'dop':{'xdop':1,'ydop':1,'pdop':1}}