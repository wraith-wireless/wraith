#!/usr/bin/env python

""" dyskt.py: main process captures and collates raw 802.11-2012 traffic

802.11-2012 sensor that collects araw 802.11 frames and gps data for processing
by an external process.
"""

__name__ = 'dyskt'
__license__ = 'GPL'
__version__ = '0.0.10'
__date__ = 'November 2014'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@hushmail.com'
__status__ = 'Development'

import os                           # for path validations
import signal                       # signal processing
import time                         # for sleep, timestamps
import logging                      # log
import logging.config               # log configuration
import logging.handlers             # handlers for log
import multiprocessing as mp        # multiprocessing process, events etc
import argparse as ap               # reading command line arguments
import ConfigParser                 # reading configuration files
from wraith import dyskt            # for rev number, author
from internal import Report         # message report template
from rto import RTO                 # the rto
from rdoctl import RadioController  # Radio object etc
from wraith.radio import channels   # channel specifications
from wraith.radio.iw import IW_CHWS # channel widths

#### set up log
# have to configure absolute path
GPATH = os.path.dirname(os.path.abspath(__file__))
logpath = os.path.join(GPATH,'dyskt.log.conf')
logging.config.fileConfig(logpath)

#### OUR EXCEPTIONS
class DySKTException(Exception): pass
class DySKTConfException(DySKTException): pass
class DySKTParamException(DySKTException): pass
class DySKTRuntimeException(DySKTException): pass

#### CONSTANTS
# WASP STATES
DYSKT_INVALID         = -1 # dyskt is unuseable
DYSKT_CREATED         =  0 # dyskt is created but not yet started
DYSKT_RUNNING         =  1 # dyskt is currently executing
DYSKT_PAUSED_RECON    =  2 # dyskt recon radio is paused
DYSKT_PAUSED_COLL     =  3 # dyskt collection radio is paused
DYSKT_PAUSED_BOTH     =  4 # both radios are paused
DYSKT_EXITING         =  5 # dyskt has finished execution loop
DYSKT_DESTROYED       =  6 # dyskt is destroyed

class DySKT(object):
    """ DySKT - primary process of the Wraith sensor """
    def __init__(self,conf=None):
        """ initialize variables """
        # get parameters
        self._cpath = conf if conf else os.path.join(GPATH,'dyskt.conf')
        
        # internal variables
        self._state = DYSKT_INVALID # current state
        self._conf = {}             # dyskt configuration dict
        self._halt = None           # the stop event
        self._pConns = None         # token pipes for children
        self._ic = None             # internal comms queue
        self._rto = None            # data collation/forwarding
        self._rr = None             # recon radio
        self._cr = None             # collection radio
    
    def _create(self):
        """ create DySKT and member processes """
        # read in and validate the conf file 
        self._readconf()

        # intialize shared objects
        self._halt = mp.Event() # our stop event
        self._ic = mp.Queue()         # comms for children
        self._pConns = {}       # dict of connections to children

        # initialize children
        # Each child is expected to initialize in the _init_ function and throw
        # a RuntimeError failure
        logging.info("Initializing subprocess...")
        try:
            # recon radio is mandatory
            logging.info("Starting Reconnaissance Radio")
            (conn1,conn2) = mp.Pipe()
            self._pConns['recon'] = conn1
            self._rr = RadioController(self._ic,conn2,self._conf['recon'])

            # collection if present
            if self._conf['collection']:
                try:
                    logging.info("Starting Collection Radio")
                    (conn1,conn2) = mp.Pipe()
                    self._pConns['collection'] = conn1
                    self._cr = RadioController(self._ic,conn2,self._conf['collection'])
                except RuntimeError as e:
                    # continue without collector, but log it
                    logging.warning("Collection Radio (%s), continuing without",e)

            # RTO
            # For the RTO, we use the interal comms queue otherwise it will
            # deadlock on waiting for reports from one of the radios
            logging.info("Starting RTO")
            (conn1,conn2) = mp.Pipe()
            self._pConns['rto'] = conn1
            self._rto = RTO(self._ic,conn2,self._conf)
        except RuntimeError as e:
            # e should have the form "Major:Minor:Description"
            ms = e.message.split(':')
            logging.error("%s (%s) %s",ms[0],ms[1],ms[2])
            self._state = DYSKT_INVALID
        except Exception as e:
            # catchall
            logging.error(e)
            self._state = DYSKT_INVALID
        else:
            # start children execution
            self._state = DYSKT_CREATED
            self._rr.start()
            if self._cr: self._cr.start()
            self._rto.start()

    def _destroy(self):
        """ destroy DySKT cleanly """
        # change our state
        self._state = DYSKT_EXITING

        # halt main execution loop & send out poison pills
        logging.info("Stopping Sub-processes")
        self._halt.set() # stops main loop in start
        self._ic.put(Report('dyskt',time.time(),'!CHECK!',[]))
        for key in self._pConns.keys():
            try:
                self._pConns[key].send('!STOP!')
            except IOError:
                # ignore any broken pipe errors
                pass
            self._pConns[key].close()
        while mp.active_children(): time.sleep(0.5)

        # change our state
        self._state = DYSKT_DESTROYED

    @property
    def state(self): return self._state

    def start(self):
        """ start execution """
        # setup signal handlers for pause(s),resume(s),stop
        signal.signal(signal.SIGINT,self.stop)   # CTRL-C and kill -INT stop
        signal.signal(signal.SIGTERM,self.stop)  # kill -TERM stop

        # initialize, quit on failure
        logging.info("**** Starting DySKT %s ****" % dyskt.__version__)
        self._create()
        if self.state == DYSKT_INVALID:
            # make sure we do not leave system in corrupt state (i.e. no wireless nics)
            self._destroy()
            raise DySKTRuntimeException("DySKT failed to initialize, shutting down")

        # set state to running
        self._state = DYSKT_RUNNING

        # execution loop
        while not self._halt.is_set():
            # get message a tuple: (level,originator,type,message)
            for key in self._pConns.keys():
                try:
                    if self._pConns[key].poll():
                        (l,o,t,m) = self._pConns[key].recv()
                        if l == "err":
                            # only process errors involved during execution
                            if DYSKT_CREATED < self.state < DYSKT_EXITING:
                                if o == 'collection':
                                    # allow collection radio to fail and still continue
                                    logging.warning("Collection radio dropped. Continuing...")
                                    self._pConns['collection'].send('!STOP!')
                                    self._pConns['collection'].close()
                                    del self._pConns['collection']
                                    mp.active_children()
                                else:
                                    logging.error("%s failed. (%s) %s",o,t,m)
                                    self.stop()
                        elif l == "warn": logging.warning("%s: (%s) %s",o,t,m)
                        elif l == "info": logging.info("%s: (%s) %s",o,t,m)
                except Exception as e:
                    # blanke exception
                    logging.error("DySKT failed. (Unknown) %s",e)
            time.sleep(1)

    # noinspection PyUnusedLocal
    def stop(self,signum=None,stack=None):
        """ stop execution """
        if DYSKT_RUNNING <= self.state < DYSKT_EXITING:
            logging.info("**** Stopping DySKT ****")
            self._destroy()

    def _readconf(self):
        """ read in config file at cpath """
        logging.info("Reading configuration file...")
        conf = ConfigParser.RawConfigParser()
        if not conf.read(self._cpath):
            raise DySKTConfException('%s is invalid' % self._cpath)

        # intialize conf to empty dict
        self._conf = {}

        try:
            # read in the recon radio configuration
            self._conf['recon'] = self._readradio(conf,'Recon')
            try:
                # catch any collection exceptions and log a warning
                if conf.has_section('Collection'):
                    self._conf['collection'] = self._readradio(conf,'Collection')
                else:
                    self._conf['collection'] = None
                    logging.info("No collection radio specified")
            except (ConfigParser.NoSectionError,ConfigParser.NoOptionError,ValueError):
                logging.warning("Invalid collection specification. Continuing without...")

            # GPS section
            self._conf['gps'] = {}
            if conf.has_section('GPS'):
                self._conf['gps']['fixed'] = conf.getboolean('GPS','fixed')
                if self._conf['gps']['fixed']:
                    self._conf['gps']['lat'] = conf.getfloat('GPS','lat')
                    self._conf['gps']['lon'] = conf.getfloat('GPS','lon')
                    self._conf['gps']['alt'] = conf.getfloat('GPS','alt')
                    self._conf['gps']['dir'] = conf.getfloat('GPS','heading')
                else:
                    self._conf['gps']['host'] = conf.get('GPS','host')
                    self._conf['gps']['port'] = conf.getint('GPS','port')
                    self._conf['gps']['id'] = conf.get('GPS','devid')
                    self._conf['gps']['poll'] = conf.getfloat('GPS','poll')
                    self._conf['gps']['epx'] = conf.getfloat('GPS','epx')
                    self._conf['gps']['epy'] = conf.getfloat('GPS','epy')

            # Storage section
            self._conf['store'] = {'host':conf.get('Storage','host'),
                                   'port':conf.getint('Storage','port')}

            # C2C section
            self._conf['c2c'] = {'port',conf.getint('C2C','port')}
        except ConfigParser.NoSectionError as e:
            raise DySKTConfException("%s" % e)
        except ConfigParser.NoOptionError as e:
            raise DySKTConfException("%s" % e)
        except ValueError as e:
            raise DySKTConfException("%s" % e)

    def _readradio(self,conf,rtype='Recon'):
        """ read in the rtype radio configuration from conf and return parsed dict """
        # get nic and set role setting default antenna config
        r = {'nic':conf.get(rtype,'nic'),
             'spoofed':None,
             'ant_gain':0.0,
             'ant_loss':0.0,
             'ant_offset':0.0,
             'ant_type':0.0,
             'desc':"unknown",
             'scan_start':None,
             'role':rtype.lower()}

        # get optional properties
        if conf.has_option(rtype,'spoof'):
            r['spoofed'] = conf.get(rtype,'spoof')
        if conf.has_option(rtype,'antenna_gain'):
            r['ant_gain'] = conf.getfloat(rtype,'antenna_gain')
        if conf.has_option(rtype,'antenna_type'):
            r['ant_type'] = conf.get(rtype,'antenna_type')
        if conf.has_option(rtype,'antenna_loss'):
            r['ant_loss'] = conf.getfloat(rtype,'antenna_loss')
        if conf.has_option(rtype,'antenna_offset'):
            r['ant_offset'] = conf.getfloat(rtype,'antenna_offset')
        if conf.has_option(rtype,'desc'):
            r['desc'] = conf.get(rtype,'desc')

        # get scan pattern
        r['dwell'] = conf.getfloat(rtype,'dwell')
        if r['dwell'] <= 0: raise ValueError("dwell must be > 0")
        r['scan'] = self._parsechlist(conf.get(rtype,'scan'),'scan')
        r['pass'] = self._parsechlist(conf.get(rtype,'pass'),'pass')
        if conf.has_option(rtype,'scan_start'):
            try:
                (ch,chw) = conf.get(rtype,'scan_start').split(':')
                ch = int(ch) if ch else r['scan'][0][0]
                if not chw in IW_CHWS: chw = r['scan'][0][1]
                r['scan_start'] = (ch,chw) if (ch,chw) in r['scan'] else r['scan'][0]
            except ValueError:
                # use default
                r['scan_start'] = r['scan'][0]
        else:
            r['scan_start'] = r['scan'][0]

        return r

    @staticmethod
    def _parsechlist(pattern,ptype):
        """
         parse channel list pattern of type ptype = oneof {'scan','pass'} and return
         a list of tuples (ch,chwidth)
        """
        if not pattern:
            chs,ws = ([],[])
        else:
            # split the pattern by ch,width separator
            chs,ws = pattern.split(':')

            # parse channel portion
            if not chs: chs = []
            else:
                if chs.lower().startswith('b'): # band specification
                    band = chs[1:]
                    if band == '2.4':
                        chs = sorted(channels.ISM_24_C2F.keys())
                    elif band == '5':
                        chs = sorted(channels.UNII_5_C2F.keys())
                    else:
                        raise ValueError("Band specification %s not supported" % chs)
                elif '-' in chs: # range specification
                    [l,u] = chs.split('-')
                    chs = [c for c in xrange(int(l),int(u)+1) if c in channels.channels()]
                else: # list or single specification
                    try:
                        chs = [int(c) for c in chs.split(',')]
                    except ValueError:
                        raise ValueError("Invalid channel list specification %s" % chs)

            # parse width portion
            if not ws or ws.lower() == 'all': ws = []
            else:
                if ws.lower() == "noht": ws = [None,'HT20']
                elif ws.lower() == "ht": ws = ['HT40+','HT40-']
                else: raise ValueError("Invalid specification for width: %s" % ws)

        # compile all possible combinations
        if (chs,ws) == ([],[]):
            if ptype == 'scan': return [(ch,chw) for chw in IW_CHWS for ch in channels.channels()]
        elif not chs:
            return [(ch,chw) for chw in ws for ch in channels.channels()]
        elif not ws:
            return [(ch,chw) for chw in IW_CHWS for ch in chs]
        else:
            return [(ch,chw) for chw in ws for ch in chs]

        return [],[]

if __name__ == 'dyskt':
    try:
        # setup the argument parser
        desc = "DySKT %s - (C) %s %s" % (dyskt.__version__,
                                         dyskt.__date__.split(" ")[1],
                                         dyskt.__author__)
        opts = ap.ArgumentParser(description=desc)
        opts.add_argument("--config",help="load specified configuration file")
        args = opts.parse_args()
        
        # set optional values
        cpath = args.config if args.config else None
        
        # verify validity
        if cpath:
            if not os.path.exists(cpath):
                raise DySKTConfException("Config file %s does not exist" % cpath)
        
        # create DySKT and start execution
        logging.info("DySKT %s",dyskt.__version__)
        skt = DySKT(cpath)
        skt.start()
    except DySKTConfException as err:
        logging.error("Configuration Error: %s",err)
    except DySKTParamException as err:
        logging.error("Parameter Error: %s",err)
    except DySKTRuntimeException as err:
        logging.error("Runtime Error: %s",err)
    except DySKTException as err:
        logging.error("General Error: %s",err)
    except Exception as err:
        logging.exception("Unknown Error: %s",err)