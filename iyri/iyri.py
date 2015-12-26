#!/usr/bin/env python

""" iyri.py: main process captures and collates raw 802.11-2012 traffic

802.11-2012 sensor that collects raw 802.11 frames, gps data and processes the
data, storing it in a local postgres database. Provides c2c functionality via a
socket on port 2526 unless otherwise specified in the config file.

The protocol used is similar to kismet (see below)
messages from client will be in the following format
 !<id> <cmd> <radio> [param]\n
 where:
  id is an integer (unique)
  cmd is oneof {state|scan|hold|listen|pause|txpwr|spoof}
  radio is oneof {both|all|abad|shama} where both enforces abad and
   shama radio and all enforces shama only if present
  param is:
   o of the format channel:width if cmd is listen where width is oneof
     {'None','HT20','HT40+','HT40-'}
   o of the format pwr:option where pwr is in dBm and option is oneof
     {fixed|auto|limit}
   o a macaddr if cmd is spoof
Iryi will notify the client if the cmd specified by id is invalid or valid with
 OK <id> [\001output\001]or
 ERR <id> \001Reason for Failure\001
If the command was invalid and no command id could be read it will be set to ?

Note: Iryi only allows one client connection at a time
"""

#__name__ = 'iyri'
__license__ = 'GPL v3.0'
__version__ = '0.1.0'
__date__ = 'September 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import os                                       # for path validations
import signal                                   # signal processing
from time import sleep                          # for sleep
import logging                                  # log
import logging.config                           # log configuration
import logging.handlers                         # handlers for log
import multiprocessing as mp                    # multiprocessing process, events etc
import ConfigParser                             # reading configuration files
import socket,threading                         # for the c2c server
import select                                   # c2c & main loop
from wraith.iyri import __version__ as ivers    # for iyri version
from wraith.iyri.collate import Collator        # the collator
from wraith.iyri.rdoctl import RadioController  # Radio object etc
from wraith.iyri.gpsctl import GPSController    # gps device
from wraith.wifi import iw                      # regset/get & channels
from wraith.wifi.iwtools import wifaces         # check for interface presents
from wraith.utils.cmdline import runningprocess # check for psql running
from wraith.utils import valrep                 # validation functionality
from wraith.iyri.constants import *             # buffer dims

#### set up log -> have to configure absolute path
GPATH = os.path.dirname(os.path.abspath(__file__))
logpath = os.path.join(os.path.dirname(os.path.abspath(__file__)),'iyri.log.conf')
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
         initialize C2C Server
          :param conn: connection pipe from/to iyri
          :param port: port to listen for connections on
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
                        self._send("Iyri v{0}".format(ivers))

                # prepare inputs
                ins = [self._cD,self._csock] if self._csock else [self._cD]

                # block on inputs & process if present
                rs,_,_ = select.select(ins,[],[],0.25)
                if self._cD in rs: # token from Iryi
                    tkn = self._cD.recv()
                    if tkn == POISON: break
                    else: self._send(tkn)
                if self._csock in rs: # cmd from client
                    cmd = self._recv()
                    if cmd: self._cD.send((CMD_CMD,'c2c','msg',cmd))
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
        """
         send msg to client
         :param msg: reply to client
        """
        if self._csock: self._csock.send(msg)

    def _shutdown(self,how=socket.SHUT_RDWR):
        """ close connection (if present) and listening socket """
        # start with client connection
        try:
            if self._csock:
                self._csock.shutdown(how)
                self._csock.close()
        except: pass
        finally:
            self._csock = self._caddr = None

        # then listening socket
        try:
            if self._sock: self._sock.shutdown(how)
            self._sock.close()
        except: pass
        finally:
            self._sock = None

    @property
    def clientstr(self):
        try:
            return "{0}:{1}".format(self._caddr[0],self._caddr[1])
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
        """
         initialize Iyri
         :param conf: path to configuration file
        """
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
        self._sr = None             # shama radio
        self._gpsd = None           # gps device
        self._rd = None             # regulatory domain
        self._c2c = None            # our c2c

    @property
    def state(self): return self._state

    def run(self):
        """ start execution """
        # setup signal handlers for stop
        signal.signal(signal.SIGINT,self.stop)   # CTRL-C and kill -INT stop
        signal.signal(signal.SIGTERM,self.stop)  # kill -TERM stop

        # initialize, quit on failure
        logging.info("**** Starting Iryi %s ****",ivers)
        self._create()
        if self.state == IYRI_INVALID:
            # make sure we do not leave system in corrupt state (i.e. w/o nics)
            self._destroy()
            raise IryiRuntimeException("Iryi failed to initialize, shutting down")

        # set state to running
        self._state = IYRI_RUNNING

        # execution loop
        while not self._halt.is_set():
            try:
                rs,_,_ = select.select(self._pConns.values(),[],[],0.5)
            except select.error as e: # hide (4,'Interupted system call') errors
                if e[0] == 4: continue
                rs = []

            for r in rs:
                try:
                    # get message(s) a tuple: (level,originator,type,message)
                    l,o,t,m = r.recv()
                    if l == IYRI_ERR and IYRI_CREATED < self.state < IYRI_EXITING:
                        if o == 'shama': # continue w/out shama if it fails
                            logging.warning("Shama dropped: %s",m)
                            self._pConns['shama'].send(POISON)
                            self._pConns['shama'].close()
                            del self._pConns['shama']
                            mp.active_children()
                            self._sr = None
                        else:
                            logging.error("%s failed (%s) %s",o,t,m)
                            self._halt.set()
                    elif l == IYRI_WARN: logging.warning("%s: (%s) %s",o,t,m)
                    elif l == IYRI_INFO: logging.info("%s: (%s) %s",o,t,m)
                    elif l == CMD_CMD:
                        cid,cmd,rdos,ps = self._processcmd(m)
                        if cid is None: continue
                        for rdo in rdos:
                            logging.info("Client sent %s w/ id %d to %s",cmd,cid,rdo)
                            rmsg = '{0}:{1}:{2}'.format(cmd,cid,'-'.join(ps))
                            self._pConns[rdo].send(rmsg)
                    elif l == CMD_ERR:
                        resp = "ERR %d \001%s\001\n".format(t,m)
                        self._pConns['c2c'].send(resp)
                        logging.info('Command %d failed: %s',t,m)
                    elif l == CMD_ACK:
                        resp = "OK %d \001%s\001\n".format(t,m)
                        self._pConns['c2c'].send(resp)
                        logging.info('Command %d succeeded',t)
                except Exception as e:
                    logging.error("Iryi failed. %s->%s", type(e),e)
                    self.stop()

    # noinspection PyUnusedLocal
    def stop(self,signum=None,stack=None):
        """
         stop execution
         :param signum: signal number, ignored
         :param stack: stack frame at point of interruption, ignored
        """
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
            host = self._conf['store']['host']
            if host == '127.0.0.1' or host == 'localhost':
                if not runningprocess('postgres'):
                    raise RuntimeError("Backend:PostgreSQL:service not running")

            # create circular buffers
            abuffer = memoryview(mp.Array('B',DIM_M*DIM_N,lock=False))
            if self._conf['shama']:
                sbuffer = memoryview(mp.Array('B',DIM_M*DIM_N,lock=False))
            else:
                sbuffer = None

            # start Collator first (IOT accept comms)
            logging.info("Initializing subprocesses...")
            logging.info("Starting Collator...")
            (conn1,conn2) = mp.Pipe()
            self._pConns['collator'] = conn1
            self._collator = Collator(self._ic,conn2,abuffer,sbuffer,self._conf)

            # start the gps
            logging.info("Starting GPS...")
            try:
                (conn1,conn2) = mp.Pipe()
                self._gpsd = GPSController(self._ic,conn2,self._conf['gps'])
            except RuntimeError as e:
                logging.warning("GPSD failed: %s, continuing w/out" % e)
            else:
                self._pConns['gpsd'] = conn1

            # set the region? if so, do it prior to starting the radio(s)
            rd = self._conf['local']['region']
            if rd:
                logging.info("Setting regulatory domain to %s...",rd)
                self._rd = iw.regget()
                iw.regset(rd)

            # abad radio is mandatory
            amode = smode = None
            amode = 'paused' if self._conf['abad']['paused'] else 'scan'
            logging.info("Starting Abad...")
            (conn1,conn2) = mp.Pipe()
            self._pConns['abad'] = conn1
            self._ar = RadioController(self._ic,conn2,abuffer,self._conf['abad'])

            # shama if present
            if self._conf['shama']:
                smode = 'paused' if self._conf['shama']['paused'] else 'scan'
                logging.info("Starting Shama...")
                try:
                    (conn1,conn2) = mp.Pipe()
                    self._sr = RadioController(self._ic,conn2,sbuffer,self._conf['shama'])
                    self._pConns['shama'] = conn1
                except RuntimeError as e:
                    logging.warning("Shama failed: %s, continuing w/out",e)

            # c2c socket -> on failure log it and keep going
            logging.info("Starting C2C...")
            try:
                (conn1,conn2) = mp.Pipe()
                self._c2c = C2C(conn2,self._conf['local']['c2c'])
                self._pConns['c2c'] = conn1
            except Exception as e:
                logging.warn("C2C failed: %s, continuing without",e)
        except RuntimeError as e:
            # e should have the form "Major:Minor:Description"
            ms = e.message.split(':')
            logging.error("%s (%s) %s",ms[0],ms[1],ms[2])
            self._state = IYRI_INVALID
        except (EOFError,OSError): pass # hide any closed pipe errors
        except Exception as e: # catchall
            logging.error("Unidentified: %s %s\n%s",type(e).__name__,e,valrep.tb())
            self._state = IYRI_INVALID
        else:
            # start children execution
            self._state = IYRI_CREATED
            self._collator.start()
            logging.info("Collator started")
            if self._gpsd:
                self._gpsd.start()
                logging.info("GPS started")
            self._ar.start()
            logging.info("Abad started in %s mode",amode)
            if self._sr:
                self._sr.start()
                logging.info("Shama started in %s mode",smode)
            if self._c2c:
                logging.info("C2C listening on port %d",self._conf['local']['c2c'])

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
                logging.info("Regulatory domain reset")
            except:
                logging.warning("Failed to reset regulatory domain")

        # halt main execution loop & send out poison pills
        logging.info("Stopping Sub-processes...")
        self._halt.set()
        for key in self._pConns:
            try:
                self._pConns[key].send(POISON)
                self._pConns[key].close()
            except (EOFError,IOError): pass # ignore any broken pipe errors

        # active_children has the side effect of joining the processes
        while mp.active_children(): sleep(0.5)
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
            raise IryiConfException("{0} is invalid".format(self._cpath))

        try:
            # read in the abad & sham radio configurations
            self._conf['abad'] = self._readradio(cp,'Abad')
            try:
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
                self._conf['gps']['id'] = cp.get('GPS','devid').upper()
                if not valrep.validgpsdid(self._conf['gps']['id']):
                    raise RuntimeError("Invalid GPS device id specification")
                self._conf['gps']['port'] = cp.getint('GPS','port')
                self._conf['gps']['poll'] = cp.getfloat('GPS','poll')
                self._conf['gps']['epx'] = cp.getfloat('GPS','epx')
                self._conf['gps']['epy'] = cp.getfloat('GPS','epy')

            # Storage section
            self._conf['store'] = {'host':cp.get('Storage','host').lower(),
                                   'port':cp.getint('Storage','port'),
                                   'db':cp.get('Storage','db'),
                                   'user':cp.get('Storage','user'),
                                   'pwd':cp.get('Storage','pwd')}
            if not valrep.validaddr(self._conf['store']['host']):
                raise RuntimeError("Invalid IP address for storage host")

            # Local section
            self._conf['local'] = {'region':None,'c2c':2526}
            if cp.has_option('Local','C2C'):
                try:
                    self._conf['local']['c2c'] = cp.getint('Local','C2C')
                except:
                    logging.warning("Invalid C2C port. Using default")

            if cp.has_option('Local','region'):
                reg = cp.get('Local','region')
                if len(reg) != 2:
                    logging.warning("Regulatory domain %s is invalid",reg)
                else:
                    self._conf['local']['region'] = cp.get('Local','region')
        except (ConfigParser.NoSectionError,ConfigParser.NoOptionError) as e:
            raise IryiConfException(e)
        except (RuntimeError,ValueError) as e:
            raise IryiConfException(e)

    # noinspection PyMethodMayBeStatic
    def _readradio(self,cp,rtype='Abad'):
        """
         read in the rtype radio configuration from conf and return parsed dict
         :param cp: ConfigParser object
         :param rtype: radio type onoeof {'Abad'|'Shama'}
        """
        nic = cp.get(rtype,'nic')
        if not nic in wifaces():
            err = "Radio %s not present/not wireless".format(nic)
            raise RuntimeError(err)

        # get nic & set role, also setting defaults
        r = {'nic':nic,
             'paused':False,
             'spoofed':None,
             'record':True,
             'desc':"unknown",
             'scan_start':None,
             'role':rtype.lower(),
             'antennas':{'num':0,
                         'type':[],
                         'gain':[],
                         'loss':[],
                         'xyz':[]}}

        # get optional properties
        if cp.has_option(rtype,'spoof'):
            spoof = cp.get(rtype,'spoof').upper()
            if not valrep.validhwaddr(spoof):
                logging.warn("Invalid spoofed MAC addr %s specified",spoof)
            else:
                r['spoofed'] = spoof
        if cp.has_option(rtype,'desc'): r['desc'] = cp.get(rtype,'desc')
        if cp.has_option(rtype,'paused'): r['paused'] = cp.getboolean(rtype,'paused')
        if cp.has_option(rtype,'record'): r['record'] = cp.getboolean(rtype,'record')

        # process antennas - get the number first
        try:
            nA = cp.getint(rtype,'antennas') if cp.has_option(rtype,'antennas') else 0
        except ValueError:
            nA = 0

        if nA:
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
                r['antennas']['num'] = nA
                r['antennas']['gain'] = gain
                r['antennas']['type'] = atype
                r['antennas']['loss'] = loss
                r['antennas']['xyz'] = xyz
            except ConfigParser.NoOptionError as e:
                logging.warning("Antenna %s not specified",e)
            except ValueError as e:
                logging.warning("Invalid type %s for %s antenna configuration",e,rtype)
            except RuntimeError as e:
                logging.warning("Antenna %s has invalid number of specifications",e)

        # get scan pattern
        r['dwell'] = cp.getfloat(rtype,'dwell')
        if r['dwell'] <= 0: raise ValueError("dwell must be > 0")
        r['scan'] = valrep.channellist(cp.get(rtype,'scan'),'scan')
        r['pass'] = valrep.channellist(cp.get(rtype,'pass'),'pass')
        if cp.has_option(rtype,'scan_start'):
            try:
                scanspec = cp.get(rtype,'scan_start')
                if ':' in scanspec: (ch,chw) = scanspec.split(':')
                else:
                    ch = scanspec
                    chw = None
                ch = int(ch) if ch else r['scan'][0][0]
                if not chw in iw.IW_CHWS: chw = r['scan'][0][1]
                r['scan_start'] = (ch,chw) if (ch,chw) in r['scan'] else r['scan'][0]
            except ValueError:
                r['scan_start'] = r['scan'][0]
        else:
            r['scan_start'] = r['scan'][0]

        return r

    def _processcmd(self,msg):
        """
         parse and process command from c2c socket
         :param msg: the commnd from user
        """
        # get tokens & ensure there are at least 3 tokens
        try:
            tkns = msg.split(' ')
        except:
            return None,None,None,None

        if len(tkns) < 3:
            self._pConns['c2c'].send("ERR ? \001invalid command format\001\n")
            return None,None,None,None

        # get cmdid
        try:
            cmdid = int(tkns[0].replace('!',''))
        except:
            self._pConns['c2c'].send("ERR ? \001invalid command format\001\n")
            return None,None,None,None

        # ATT we can error/ack with associated cmd id
        cmd = tkns[1].strip().lower()
        if cmd not in ['state','scan','hold','listen','pause','txpwr','spoof']:
            resp = "ERR {0} \001invalid command\001\n".format(cmdid)
            self._pConns['c2c'].send(resp)
            return None,None,None,None

        if cmd == 'txpwr' or cmd == 'spoof':
            resp = "ERR {0} \001{1} not implemented\001\n".format(cmdid,cmd)
            self._pConns['c2c'].send(resp)
            return None,None,None,None

        radio = tkns[2].strip().lower()
        if radio not in ['both','all','abad','shama']:
            resp = "ERR {0} \001invalid radio spec: {1} \001\n".format(cmdid,radio)
            self._pConns['c2c'].send(resp)
            return None,None,None,None

        if radio == 'all':
            radios = ['abad']
            if self._sr is not None: radios.append('shama')
        elif radio == 'both': radios = ['abad','shama']
        else: radios = [radio]
        if 'shama' in radios and self._sr is None:
            resp = "ERR {0} \001shama radio not present\001\n".format(cmdid)
            self._pConns['c2c'].send(resp)
            return None,None,None,None

        # ensure any params are valid
        if cmd in ['listen','txpwr','spoof']:
            try:
                ps = tkns[3].strip().split(':')
                if len(ps) not in [2,6]: raise RuntimeError
                if cmd == 'listen': # listen will be ch:chw
                    int(ps[0])
                    if ps[1] not in ['None','HT20','HT40+','HT40-']: raise RuntimeError
                elif cmd == 'txpwr': # txpwr will be pwr:opt
                    int(ps[0])
                    if ps[1] not in ['fixed','auto','limit']: raise RuntimeError
                elif cmd == 'spoof': # spoof will be macaddr
                    if len(ps) != 6: raise RuntimeError
                    ps = ':'.join(ps).upper() # rejoin the mac
                    if not valrep.validhwaddr(ps): raise RuntimeError
            except:
                resp = "ERR {0} \001invalid params\001\n".format(cmdid)
                self._pConns['c2c'].send(resp)
                return None,None,None,None

        # all good
        return cmdid,cmd,radios,ps

if __name__ == '__main__':
    try:
        logging.info("Iryi %s",ivers)
        sensor = Iryi()
        sensor.run()
    except IryiConfException as e:
        logging.error("Configuration Error: %s",e)
    except IryiParamException as e:
        logging.error("Parameter Error: %s",e)
    except IryiRuntimeException as e:
        logging.error("Runtime Error: %s",e)
    except IryiException as e:
        logging.error("General Error: %s",e)
    except Exception as e:
        logging.exception("Unknown Error: %s",e)