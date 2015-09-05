#!/usr/bin/env python

""" iyri.py: main process captures and collates raw 802.11-2012 traffic

802.11-2012 sensor that collects raw 802.11 frames and gps data for processing
by an external process. Provides c2c functionality via a socket on port 2526
unless otherwise specified in the config file.

The protocol used is similar to kismet (see below)
messages from client will be in the following format
 !<id> <cmd> <radio> [param]\n
 where:
  id is an integer (unique)
  cmd is oneof {state|scan|hold|listen|pause|txpwr|spoof}
  radio is oneof {both|all|abad|shama} where both enforces abad and
   shama radio and all enforces shama only if present
  param is:
   o of the format channel:width if cmd is listen where width is oneof {'None','HT20','HT40+','HT40-'}
   o of the format pwr:option where pwr is in dBm and option is oneof {fixed|auto|limit}
   o a macaddr if cmd is spoof
Iryi will notify the client if the cmd specified by id is invalid or valid with
 OK <id> or
 ERR <id> \001Reason for Failure\001
If the command was invalid and no command id could be read it will be set to ?

Note: Iryi only allows one client connection at a time
"""

#__name__ = 'iyri'
__license__ = 'GPL v3.0'
__version__ = '0.1.0'
__date__ = 'August 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import os                                       # for path validations
import re                                       # for reg expr
import signal                                   # signal processing
import time                                     # for sleep, timestamps
import logging                                  # log
import logging.config                           # log configuration
import logging.handlers                         # handlers for log
import multiprocessing as mp                    # multiprocessing process, events etc
import ConfigParser                             # reading configuration files
import socket                                   # for the c2c server
import threading                                # for the c2c server
import select                                   # c2c & main loop
from wraith import iyri                         # for rev number, author
from wraith.iyri.collate import Collator        # the collator
from wraith.iyri.rdoctl import RadioController  # Radio object etc
from wraith.radio import channels               # channel specifications
from wraith.radio import iw                     # channel widths and region set/get
from wraith.radio.iwtools import wifaces        # check for interface presents
from wraith.utils.cmdline import runningprocess # check for psql running
from wraith.iyri.constants import *             # buffer dims

# auxiliary function - pulled out of Iryi class so it can be used elsewhere
# with minimal hassle
def parsechlist(pattern,ptype):
    """
      parse channel list pattern of type ptype = oneof {'scan'|'pass'} and return
      a list of tuples (ch,chwidth)
    """
    if not pattern: chs,ws = [],[]
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
                    raise ValueError("Band specification %s for %s not supported" % (chs,ptype))
            elif '-' in chs: # range specification
                [l,u] = chs.split('-')
                chs = [c for c in xrange(int(l),int(u)+1) if c in channels.channels()]
            else: # list or single specification
                try:
                    chs = [int(c) for c in chs.split(',')]
                except ValueError:
                    raise ValueError("Invalid channel list specification %s for %s" % (chs,ptype))

            # parse width portion
            if not ws or ws.lower() == 'all': ws = []
            else:
                if ws.lower() == "noht": ws = [None,'HT20']
                elif ws.lower() == "ht": ws = ['HT40+','HT40-']
                else: raise ValueError("Invalid specification for width %s for %s" % (ws,ptype))

    # compile all possible combinations
    if (chs,ws) == ([],[]):
        if ptype == 'scan': return [(ch,chw) for chw in iw.IW_CHWS for ch in channels.channels()]
    elif not chs: return [(ch,chw) for chw in ws for ch in channels.channels()]
    elif not ws: return [(ch,chw) for chw in iw.IW_CHWS for ch in chs]
    else:
        return [(ch,chw) for chw in ws for ch in chs]

    return [],[]

#### set up log -> have to configure absolute path
GPATH = os.path.dirname(os.path.abspath(__file__))
logpath = os.path.join(GPATH,'iyri.log.conf')
logging.config.fileConfig(logpath)

class C2CClientExit(Exception): pass
class C2C(threading.Thread):
    """
     A "threaded socket", facilitates communication betw/ Iryi and a client
      1) accepts one and only one client at a time
      2) is non-blocking (the listening socket)
      3) handles a very simple protocol based on kismet's (see above)
     Note: the C2C has a very simplistic error handling. On any error, will reset
     itself
    """
    def __init__(self,conn,port):
        """
         initialize
          conn: connection pipe
          port: port to listen for connections on
        """
        threading.Thread.__init__(self)
        self._cD = conn     # connection to/from Iryi
        self._lp = port     # port to listen on
        self._sock = None   # the listen socket
        self._caddr = None  # the client addr
        self._csock = None  # the client socket

    def run(self):
        """ execution loop check/respond to clients """
        while True:
            try:
                # should we listen? or accept?
                if not self._sock and not self._caddr: self._listen()
                elif self._sock and not self._caddr:
                    if self._accept():
                        logging.info("Client %s connected",self.clientstr)
                        self._send("Iryi v%s\n" % iyri.__version__)

                # prepare inputs
                ins = [self._cD,self._csock] if self._csock else [self._cD]

                # block on inputs & process if present
                rs,_,_ = select.select(ins,[],[],0.25)
                if self._cD in rs:
                    # token from Iryi
                    tkn = self._cD.recv()
                    if tkn == '!STOP!': break
                    else: self._send(tkn)
                if self._csock in rs:
                    # cmd from client
                    cmd = self._recv()
                    if cmd: self._cD.send(('cmd','c2c','msg',cmd))
            except (select.error,socket.error): # hide any select errors
                self._shutdown() # reset everything
            except C2CClientExit:
                # used to signal an exiting client
                logging.info("Client exited")
                self._shutdown()
        self._shutdown() # cleanup

    def _listen(self):
        """ open socket for listening """
        if self._sock is None:
            self._sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            self._sock.setblocking(0)
            self._sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            self._sock.bind(('localhost',self._lp))
            self._sock.listen(0)

    def _accept(self):
        """ accept a client request """
        if self._caddr: return False

        # see if a client wants to connect
        try:
            # if we get a client connection, shutdown the listening the socket
            # so no future clients will hang waiting on it
            self._csock,self._caddr = self._sock.accept()
            self._sock.shutdown(socket.SHUT_RDWR)
            self._sock.close()
            self._sock = None
            return True
        except socket.error:
            return False

    def _recv(self):
        """ recv from client """
        if self._csock:
            msg = ''
            while len(msg) == 0 or msg[-1:] != '\n':
                data = self._csock.recv(1024)
                if not data: raise C2CClientExit
                msg += data
            return msg

    def _send(self,msg):
        """ send msg to client """
        if self._csock: self._csock.send(msg)

    def _shutdown(self,how=socket.SHUT_RDWR):
        """ close connection (if present) and listening socket """
        # start with client connection
        try:
            if self._csock:
                self._csock.shutdown(how)
                self._csock.close()
        except:
            pass
        finally:
            self._csock = self._caddr = None

        # then listening socket
        try:
            if self._sock: self._sock.shutdown(how)
            self._sock.close()
        except:
            pass
        finally:
            self._sock = None

    @property # will throw error on no client
    def clientstr(self):
        try:
            return "%s:%d" % (self._caddr[0],self._caddr[1])
        except:
            return ""

#### Iryi EXCEPTIONS
class IryiException(Exception): pass
class IryiConfException(IryiException): pass
class IryiParamException(IryiException): pass
class IryiRuntimeException(IryiException): pass

class Iryi(object):
    """ Iryi - primary process of the Wraith sensor """
    def __init__(self,conf=None):
        """ initialize variables """
        # get parameters
        self._cpath = conf if conf else os.path.join(GPATH,'iyri.conf')
        
        # internal variables
        self._state = IYRI_INVALID  # current state
        self._conf = {}             # iyri configuration dict
        self._halt = None           # the stop event
        self._pConns = None         # token pipes for children (& c2c)
        self._ic = None             # internal comms queue
        self._collator = None       # data collation/forwarding
        self._ar = None             # abad radio
        self._abuffer = None        # abad radio buffer
        self._sr = None             # shama radio
        self._sbuffer = None        # shama radio buffer
        self._rd = None             # regulatory domain
        self._c2c = None            # our c2c

    @property
    def state(self): return self._state

    def run(self):
        """ start execution """
        # setup signal handlers for pause(s),resume(s),stop
        signal.signal(signal.SIGINT,self.stop)   # CTRL-C and kill -INT stop
        signal.signal(signal.SIGTERM,self.stop)  # kill -TERM stop

        # initialize, quit on failure
        logging.info("**** Starting Iryi %s ****",iyri.__version__)
        self._sreate()
        if self.state == IYRI_INVALID:
            # make sure we do not leave system in corrupt state (i.e. w/o nics)
            self._destroy()
            raise IryiRuntimeException("Iryi failed to initialize, shutting down")

        # set state to running
        self._state = IYRI_RUNNING

        # execution loop
        while not self._halt.is_set():
            # get message(s) a tuple: (level,originator,type,message) from children
            rs = [] # hide pycharm unreferenced variable warning
            try:
                rs,_,_ = select.select(self._pConns.values(),[],[],0.5)
            except select.error as e: # hide (4,'Interupted system call') errors
                if e[0] == 4: continue

            for r in rs:
                try:
                    l,o,t,m = r.recv()
                    if l == 'err':
                        # only process errors invovled during execution
                        if IYRI_CREATED < self.state < IYRI_EXITING:
                            # continue w/out shama if it fails
                            if o == 'shama':
                                logging.warning("Shama dropped: %s",m)
                                self._pConns['shama'].send('!STOP!')
                                self._pConns['shama'].close()
                                del self._pConns['shama']
                                mp.active_children()
                                self._sr = None
                            else:
                                logging.error("%s failed (%s) %s",o,t,m)
                                self.stop()
                        else:
                            logging.warning("Uninitiated error (%) %s from %s",t,m,o)
                    elif l == 'warn': logging.warning("%s: (%s) %s",o,t,m)
                    elif l == 'info': logging.info("%s: (%s) %s",o,t,m)
                    elif l == 'cmd':
                        cid,cmd,rdos,ps = self._processcmd(m)
                        if cid is None: continue
                        for rdo in rdos:
                            logging.info("Client sent %s w/ id %d to %s",cmd,cid,rdo)
                            self._pConns[rdo].send('%s:%d:%s' % (cmd,cid,'-'.join(ps)))
                    elif l == 'cmderr':
                        self._pConns['c2c'].send("ERR %d \001%s\001\n" % (t,m))
                        logging.info('Command %d failed: %s',t,m)
                    elif l == 'cmdack':
                        self._pConns['c2c'].send("OK %d \001%s\001\n" % (t,m))
                        logging.info('Command %d succeeded',t)
                except Exception as e:
                    logging.error("Iryi failed. %s->%s", type(e),e)
                    self.stop()

    # noinspection PyUnusedLocal
    def stop(self,signum=None,stack=None):
        """ stop execution """
        if IYRI_RUNNING <= self.state < IYRI_EXITING:
            logging.info("**** Stopping Iryi ****")
            self._destroy()

    #### PRIVATE HELPERS

    def _create(self):
        """ create Iryi and member processes """
        # read in and validate the conf file
        self._readconf()

        # intialize shared objects
        self._halt = mp.Event() # our stop event
        self._ic = mp.Queue()   # comms for children
        self._pConns = {}       # dict of connections to children

        # initialize children
        # Each child is expected to initialize in the _init_ function and throw
        # a RuntimeError on failure. For non-mandatory components, all exceptions
        # are caught in in inner exceptions, mandatory are caught in the the outer
        # exception and result in shutting down

        try:
            # don't even bother if psql is local and it's not running
            if self._conf['store']['host'] == '127.0.0.1' or\
               self._conf['store']['host'] == 'localhost':
                if not runningprocess('postgres'):
                    raise RuntimeError("Backend:PostgreSQL:service not running")

            # create circular buffers
            self._abuffer = memoryview(mp.Array('B',M*N,lock=False))
            if self._conf['shama']:
                self._sbuffer = memoryview(mp.Array('B',M*N,lock=False))

            # start Collator first (IOT accept comms from the radios)
            logging.info("Initializing subprocess...")
            logging.info("Starting Collator...")
            (conn1,conn2) = mp.Pipe()
            self._pConns['collator'] = conn1
            self._collator = Collator(self._ic,conn2,self._sbuffer,self._abuffer,self._conf)
            logging.info("Collator started")

            # set the region? if so, do it prior to starting the radio(s)
            rd = self._conf['local']['region']
            if rd:
                logging.info("Setting regulatory domain to %s...",rd)
                self._rd = iw.regget()
                iw.regset(rd)
                if iw.regget() != rd:
                    logging.warning("Regulatory domain %s may not have been set",rd)
                else:
                    logging.info("Regulatory domain set to %s",rd)

            # abad radio is mandatory
            mode = 'paused' if self._conf['abad']['paused'] else 'scan'
            logging.info("Starting Abad...")
            (conn1,conn2) = mp.Pipe()
            self._pConns['abad'] = conn1
            self._ar = RadioController(self._ic,conn2,self._abuffer,self._conf['abad'])
            logging.info("Abad started in %s mode",mode)

            # shama if present
            if self._conf['shama']:
                try:
                    mode = 'paused' if self._conf['shama']['paused'] else 'scan'
                    logging.info("Starting Shama...")
                    (conn1,conn2) = mp.Pipe()
                    self._pConns['shama'] = conn1
                    self._sr = RadioController(self._ic,conn2,
                                               self._sbuffer,self._conf['shama'])
                except RuntimeError as e:
                    # continue without collector, but log it
                    logging.warning("Shama failed: %s, continuing w/out",e)
                else:
                    logging.info("Shama started in %s mode",mode)

            # c2c socket -> on failure log it and keep going
            logging.info("Starting C2C...")
            try:
                (conn1,conn2) = mp.Pipe()
                self._pConns['c2c'] = conn1
                self._c2c = C2C(conn2,self._conf['local']['c2c'])
                self._c2c.start()
            except Exception as e:
                logging.warn("C2C failed: %s, continuing without" % e)
            else:
                 logging.info("C2C listening on port %d" % self._conf['local']['c2c'])
        except RuntimeError as e:
            # e should have the form "Major:Minor:Description"
            ms = e.message.split(':')
            logging.error("%s (%s) %s",ms[0],ms[1],ms[2])
            self._state = IYRI_INVALID
        except Exception as e:
            # catchall
            logging.error(e)
            self._state = IYRI_INVALID
        except OSError as e: pass
        else:
            # start children execution
            self._state = IYRI_CREATED
            self._ar.start()
            if self._sr: self._sr.start()
            self._collator.start()

    def _destroy(self):
        """ destroy Iryi cleanly """
        # change our state
        self._state = IYRI_EXITING

        # reset regulatory domain if necessary
        if self._rd:
            try:
                logging.info("Resetting regulatory domain...")
                iw.regset(self._rd)
                if iw.regget() != self._rd: raise RuntimeError
            except:
                logging.warning("Failed to reset regulatory domain")
            else:
                logging.info("Regulatory domain reset")

        # halt main execution loop & send out poison pills
        logging.info("Stopping Sub-processes...")
        self._halt.set()
        for key in self._pConns:
            try:
                self._pConns[key].send('!STOP!')
                self._pConns[key].close()
            except IOError:
                # ignore any broken pipe errors
                pass

        # active_children has the side effect of joining the processes
        while mp.active_children(): time.sleep(0.5)
        if self._c2c:
            while self._c2c.is_alive(): self._c2c.join(0.5)
        logging.info("Sub-processes stopped")

        # change our state
        self._state = IYRI_DESTROYED

    def _readconf(self):
        """ read in config file at cpath """
        logging.info("Reading configuration file...")
        cp = ConfigParser.RawConfigParser()
        if not cp.read(self._cpath):
            raise IryiConfException('%s is invalid' % self._cpath)

        # intialize conf to empty dict
        self._conf = {}

        try:
            # read in the abad radio configuration
            self._conf['abad'] = self._readradio(cp,'Abad')
            try:
                # catch any shama exceptions and log a warning
                if cp.has_section('Shama'):
                    self._conf['shama'] = self._readradio(cp,'Shama')
                else:
                    self._conf['shama'] = None
                    logging.info("No shama radio specified")
            except (ConfigParser.NoSectionError,ConfigParser.NoOptionError,RuntimeError,ValueError):
                logging.warning("Invalid shama specification. Continuing without...")

            # GPS section
            self._conf['gps'] = {}
            self._conf['gps']['fixed'] = cp.getboolean('GPS','fixed')
            if self._conf['gps']['fixed']:
                self._conf['gps']['lat'] = cp.getfloat('GPS','lat')
                self._conf['gps']['lon'] = cp.getfloat('GPS','lon')
                self._conf['gps']['alt'] = cp.getfloat('GPS','alt')
                self._conf['gps']['dir'] = cp.getfloat('GPS','heading')
            else:
                self._conf['gps']['port'] = cp.getint('GPS','port')
                self._conf['gps']['id'] = cp.get('GPS','devid').upper()
                if re.match(GPSDID,self._conf['gps']['id']) is None:
                    raise RuntimeError("Invalid GPS device id specification")
                self._conf['gps']['poll'] = cp.getfloat('GPS','poll')
                self._conf['gps']['epx'] = cp.getfloat('GPS','epx')
                self._conf['gps']['epy'] = cp.getfloat('GPS','epy')

            # Storage section
            self._conf['store'] = {
                                   'host':cp.get('Storage','host').lower(),
                                   'port':cp.getint('Storage','port'),
                                   'db':cp.get('Storage','db'),
                                   'user':cp.get('Storage','user'),
                                   'pwd':cp.get('Storage','pwd')
                                  }
            if re.match(IPADDR,self._conf['store']['host']) is None and\
               self._conf['store']['host'] != 'localhost':
                raise RuntimeError("Invalid IP address for storage host")

            # Local section
            self._conf['local'] = {'region':None,'c2c':2526,'oui':''}
            if cp.has_option('Local','C2C'):
                try:
                    self._conf['local']['c2c'] = cp.getint('Local','C2C')
                except:
                    logging.warning("Invalid C2C port specification. Using default")

            if cp.has_option('Local','region'):
                reg = cp.get('Local','region')
                if len(reg) != 2:
                    logging.warning("Regulatory domain %s is invalid",reg)
                else:
                    self._conf['local']['region'] = cp.get('Local','region')

            if cp.has_option('Local','oui'):
                oui = cp.get('Local','oui')
                if os.path.isfile(oui): self._conf['local']['oui'] = oui
                else: logging.warning("OUI path does not exists. Ignoring")
        except (ConfigParser.NoSectionError,ConfigParser.NoOptionError) as e:
            raise IryiConfException("%s" % e)
        except (RuntimeError,ValueError) as e:
            raise IryiConfException("%s" % e)

    # noinspection PyMethodMayBeStatic
    def _readradio(self,cp,rtype='Abad'):
        """ read in the rtype radio configuration from conf and return parsed dict """
        # don't bother if specified radio is not present
        if not cp.get(rtype,'nic') in wifaces():
            raise RuntimeError("Radio %s not present/not wireless" % cp.get(rtype,'nic'))

        # get nic and set role setting default antenna config
        r = {
             'nic':cp.get(rtype,'nic'),
             'paused':False,
             'spoofed':None,
             'ant_gain':0.0,
             'ant_loss':0.0,
             'ant_offset':0.0,
             'ant_type':0.0,
             'desc':"unknown",
             'scan_start':None,
             'role':rtype.lower(),
             'antennas':{}
            }

        # get optional properties
        if cp.has_option(rtype,'spoof'):
            spoof = cp.get(rtype,'spoof').upper()
            if re.match(MACADDR,spoof) is None and spoof != 'RANDOM':
                logging.warn("Invalid spoofed MAC addr %s specified",spoof)
            else:
                r['spoofed'] = spoof
        if cp.has_option(rtype,'desc'): r['desc'] = cp.get(rtype,'desc')
        if cp.has_option(rtype,'paused'): r['paused'] = cp.getboolean(rtype,'paused')

        # process antennas - get the number first
        try:
            nA = cp.getint(rtype,'antennas') if cp.has_option(rtype,'antennas') else 0
        except ValueError:
            nA = 0

        if nA:
            # antennas has been specified, warn (and ignore) invalid specifications
            try:
                gain = map(float,cp.get(rtype,'antenna_gain').split(','))
                if len(gain) != nA: raise RuntimeError('gain')
                atype = cp.get(rtype,'antenna_type').split(',')
                if len(atype) != nA: raise RuntimeError('type')
                loss = map(float,cp.get(rtype,'antenna_loss').split(','))
                if len(loss) != nA: raise RuntimeError('loss')
                rs = cp.get(rtype,'antenna_xyz').split(',')
                xyz = []
                for t in rs: xyz.append(tuple(map(int,t.split(':'))))
                if len(xyz) != nA: raise RuntimeError('xyz')
            except ConfigParser.NoOptionError as e:
                logging.warning("Antenna %s not specified",e)
            except ValueError as e:
                logging.warning("Invalid type %s for %s antenna configuration",e,rtype)
            except RuntimeError as e:
                logging.warning("Antenna %s has invalid number of specifications",e)
            else:
                r['antennas']['num'] = nA
                r['antennas']['gain'] = gain
                r['antennas']['type'] = atype
                r['antennas']['loss'] = loss
                r['antennas']['xyz'] = xyz
        else:
            # none, set all empty
            r['antennas']['num'] = 0
            r['antennas']['gain'] = []
            r['antennas']['type'] = []
            r['antennas']['loss'] = []
            r['antennas']['xyz'] = []

        # get scan pattern
        r['dwell'] = cp.getfloat(rtype,'dwell')
        if r['dwell'] <= 0: raise ValueError("dwell must be > 0")
        r['scan'] = parsechlist(cp.get(rtype,'scan'),'scan')
        r['pass'] = parsechlist(cp.get(rtype,'pass'),'pass')
        if cp.has_option(rtype,'scan_start'):
            try:
                scanspec = cp.get(rtype,'scan_start')
                if ':' in scanspec:
                    (ch,chw) = scanspec.split(':')
                else:
                    ch = scanspec
                    chw = None
                ch = int(ch) if ch else r['scan'][0][0]
                if not chw in iw.IW_CHWS: chw = r['scan'][0][1]
                r['scan_start'] = (ch,chw) if (ch,chw) in r['scan'] else r['scan'][0]
            except ValueError:
                # use default
                r['scan_start'] = r['scan'][0]
        else:
            r['scan_start'] = r['scan'][0]

        return r

    def _processcmd(self,msg):
        """ parse and process command from c2c socket """
        # ensure there are at least 3 tokens
        tkns = None
        try:
            tkns = msg.split(' ')
        except:
            return None,None,None,None

        if len(tkns) < 3:
            self._pConns['c2c'].send("ERR ? \001invalid command format\001\n")
            return None,None,None,None

        # and a cmdid is present
        cmdid = None
        try:
            cmdid = int(tkns[0].replace('!',''))
        except:
            self._pConns['c2c'].send("ERR ? \001invalid command format\001\n")
            return None,None,None,None

        # ATT we can error/ack with associated cmd id
        cmd = tkns[1].strip().lower()
        if cmd not in ['state','scan','hold','listen','pause','txpwr','spoof']:
            self._pConns['c2c'].send("ERR %d \001invalid command\001\n" % cmdid)
            return None,None,None,None

        if cmd == 'txpwr' or cmd == 'spoof':
            self._pConns['c2c'].send("ERR %d \001%s not implemented\001\n" % (cmdid,cmd))
            return None,None,None,None

        radios = []
        radio = tkns[2].strip().lower()
        if radio not in ['both','all','abad','shama']:
            self._pConns['c2c'].send("ERR %d \001invalid radio specification: %s \001\n" % (cmdid,radio))
            return None,None,None,None

        if radio == 'all':
            radios = ['abad']
            if self._sr is not None: radios.append('shama')
        elif radio == 'both': radios = ['abad','shama']
        else: radios = [radio]
        if 'shama' in radios and self._sr is None:
            self._pConns['c2c'].send("ERR %d \001shama radio not present\001\n" % cmdid)
            return None,None,None,None

        # ensure any params are valid
        ps = []
        if cmd in ['listen','txpwr','spoof']:
            try:
                ps = tkns[3].strip().split(':')
                if len(ps) not in [2,6]: raise RuntimeError
                if cmd == 'listen':
                    # listen will be ch:chw
                    int(ps[0]) # type check
                    if ps[1] not in ['None','HT20','HT40+','HT40-']: raise RuntimeError
                elif cmd == 'txpwr':
                    # txpwr will be pwr:opt
                    int(ps[0]) # type check
                    if ps[1] not in ['fixed','auto','limit']: raise RuntimeError
                elif cmd == 'spoof':
                    # spoof will be macaddr
                    if len(ps) != 6: raise RuntimeError
                    ps = ':'.join(ps).upper() # rejoin the mac
                    if re.match(MACADDR,ps) is None: raise RuntimeError
            except:
                self._pConns['c2c'].send("ERR %d \001invalid params\001\n" % cmdid)
                return None,None,None,None

        # all good
        return cmdid,cmd,radios,ps

if __name__ == '__main__':
    try:
        logging.info("Iryi %s",iyri.__version__)
        skt = Iryi()
        skt.run()
    except IryiConfException as err:
        logging.error("Configuration Error: %s",err)
    except IryiParamException as err:
        logging.error("Parameter Error: %s",err)
    except IryiRuntimeException as err:
        logging.error("Runtime Error: %s",err)
    except IryiException as err:
        logging.error("General Error: %s",err)
    except Exception as err:
        logging.exception("Unknown Error: %s",err)