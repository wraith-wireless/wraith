#1/usr/bin/env python

""" rdoctl.py: Radio Controller

An interface to an underlying radio (wireless nic). Collects all frames and
forwards to the Collator.

RadioController will spawn a Tuner to handle all channel switching etc.

The convention used here is to allow the Tuner to receive all notifications
from iyri because they may contain user commands.
"""
__name__ = 'rdoctl'
__license__ = 'GPL v3.0'
__version__ = '0.1.1'
__date__ = 'January 2016'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

from time import time,sleep                # current time, waiting
import signal                              # handling signals
import socket                              # reading frames
from Queue import Empty             # thread-safe queue
import multiprocessing as mp               # for Process
from wraith.wifi import iw                 # iw command line interface
import wraith.wifi.iwtools as iwt          # nic command line interaces
from wraith.utils.timestamps import ts2iso # time stamp conversion
from wraith.iyri.tuner import Tuner        # our tuner
from wraith.iyri.constants import *        # tuner states & buffer dims

class RadioController(mp.Process):
    """ RadioController - handles radio initialization and collection """
    def __init__(self,comms,conn,buff,conf):
        """
         initialize radio for collection
         :param comms: internal communication to Collator
         :param conn: connection to/from Iyri
         :param buff: the circular buffer for frames
         :param conf: radio configuration dict. Must have key->value pairs for
          keys = role,nic,dwell,scan and pass and optionally for keys = spoof,
          ant_gain,ant_type,ant_loss,desc
        """
        mp.Process.__init__(self)
        self._icomms = comms      # communications queue
        self._cI = conn           # message connection to/from Iyri
        self._buffer = buff       # buffer for frames
        self._qT = None           # queue for tuner messages
        self._role = None         # role this radio plays
        self._nic = None          # radio network interface controller name
        self._mac = None          # real mac address
        self._phy = None          # the phy of the device
        self._vnic = None         # virtual monitor name
        self._std = None          # supported standards
        self._scan = []           # scan list
        self._hop = None          # hop time
        self._interval = None     # interval time
        self._chs = []            # supported channels
        self._ds = []             # dwell times list
        self._txpwr = 0           # current tx power
        self._driver = None       # the driver
        self._chipset = None      # the chipset
        self._spoofed = ""        # spoofed mac address
        self._record = False      # write frames to file?
        self._desc = None         # optional description
        self._paused = False      # initial state: pause on True, scan otherwise
        self._chi = 0             # initial channel index
        self._s = None            # the raw socket
        self._antenna = {'num':0, # antenna details
                         'gain':None,
                         'type':None,
                         'loss':None,
                         'x':None,
                         'y':None,
                         'z':None}
        self._setup(conf)

    def terminate(self): pass

    def run(self):
        """ run execution loop """
        # ignore signals being used by main program
        signal.signal(signal.SIGINT,signal.SIG_IGN)
        signal.signal(signal.SIGTERM,signal.SIG_IGN)

        # start tuner thread
        stuner = TUNE_PAUSE if self._paused else TUNE_SCAN
        try:
            qT = mp.Queue()
            tuner = Tuner(qT,self._cI,self._vnic,self._scan,self._ds,self._chi,stuner)
            tuner.start()
            self._icomms.put((self._vnic,ts2iso(time()),RDO_RADIO,self.radio))
        except Exception as e:
            self._cI.send((IYRI_ERR,self._role,type(e).__name__,e))
            self._icomms.put((self._vnic,ts2iso(time()),RDO_FAIL,e))
        else:
            msg = "tuner-{0} up".format(tuner.pid)
            self._cI.send((IYRI_INFO,self._role,'Tuner',msg))

        # execute sniffing loop
        # RadioController will check for any notifications from the Tuner, a tuple
        # t = (event,timestamp,message) where message is another tuple of the form
        # m = (cmdid,description) such that cmdid != -1 if this command comes from
        # an external source. If there are no notifications from Tuner, check if
        # any frames are queued on the socket and read them in to the buffer.
        # If we're paused, read into a null buffer
        ix = 0      # index of current frame
        m = DIM_M   # save some space with
        n = DIM_N   # these
        err = False # error state, do nothing until we get POISON pill
        while True:
            try:
                # pull any notification from Tuner & process
                ev,ts,msg = qT.get_nowait()
                if ev == POISON: break
                elif ev == CMD_ERR:
                    self._cI.send((CMD_ERR,self._role,msg[0],msg[1]))
                elif ev == RDO_FAIL:
                    self._cI.send((IYRI_ERR,self._role,'Tuner',msg[1]))
                    self._icomms.put((self._vnic,ts,RDO_FAIL,msg[1]))
                elif ev == RDO_STATE:
                    self._cI.send((CMD_ACK,self._role,msg[0],msg[1]))
                elif ev == RDO_HOLD:
                    stuner = TUNE_HOLD
                    self._icomms.put((self._vnic,ts,RDO_HOLD,msg[1]))
                    if msg[0] != -1:
                        self._cI.send((CMD_ACK,self._role,msg[0],msg[1]))
                elif ev == RDO_SCAN:
                    stuner = TUNE_SCAN
                    self._icomms.put((self._vnic,ts,RDO_SCAN,msg[1]))
                    if msg[0] != -1:
                        self._cI.send((CMD_ACK,self._role,msg[0],msg[1]))
                elif ev == RDO_LISTEN:
                    stuner = TUNE_LISTEN
                    self._icomms.put((self._vnic,ts,RDO_LISTEN,msg[1]))
                    if msg[0] > -1:
                        self._cI.send((CMD_ACK,self._role,msg[0],msg[1]))
                elif ev == RDO_PAUSE:
                    stuner = TUNE_PAUSE
                    self._icomms.put((self._vnic,ts,RDO_PAUSE,' '))
                    if msg[0] > -1:
                        self._cI.send((CMD_ACK,self._role,msg[0],msg[1]))
            except Empty: # no notices from Tuner
                if err: continue # error state, wait till iyri sends poison pill
                try:
                    # if paused, pull any frame off and ignore otherwise pass on
                    if stuner == TUNE_PAUSE: _ = self._s.recv(n)
                    else:
                        l = self._s.recv_into(self._buffer[(ix*n):(ix*n)+n],n)
                        ts = ts2iso(time())
                        self._icomms.put((self._vnic,ts,RDO_FRAME,(ix,l)))
                        ix = (ix+1) % m
                except socket.timeout: pass
                except socket.error as e:
                    err = True
                    self._cI.send((IYRI_ERR,self._role,'Socket',e))
                    self._icomms.put((self._vnic,ts2iso(time()),RDO_FAIL,e))
                except Exception as e:
                    err = True
                    self._cI.send((IYRI_ERR,self._role,type(e).__name__,e))
                    self._icomms.put((self._vnic,ts2iso(time()),RDO_FAIL,e))

        # ensure Tuner has finished
        while mp.active_children(): sleep(0.5)

        # notify Collator we are down & shut down
        self._icomms.put((self._vnic,ts2iso(time()),RDO_RADIO,None))
        if not self._shutdown():
            try:
                self._cI.send((IYRI_WARN,self._role,'Shutdown',"Incomplete reset"))
            except (EOFError,IOError): pass

    @property
    def radio(self):
        """ returns a dict describing this radio """
        return {'nic':self._nic,
                'vnic':self._vnic,
                'phy':self._phy,
                'mac':self._mac,
                'role':self._role,
                'spoofed':self._spoofed,
                'record':self._record,
                'driver':self._driver,
                'chipset':self._chipset,
                'standards':self._std,
                'channels':self._chs,
                'hop':'{0:.3}'.format(self._hop),
                'ival':'{0:.3}'.format(self._interval),
                'txpwr':self._txpwr,
                'desc':self._desc,
                'nA':self._antenna['num'],
                'type':self._antenna['type'],
                'gain':self._antenna['gain'],
                'loss':self._antenna['loss'],
                'x':self._antenna['x'],
                'y':self._antenna['y'],
                'z':self._antenna['z']}

    # private helper functions

    def _setup(self,conf):
        """
         1) sets radio properties as specified in conf
         2) prepares specified nic for monitoring and binds it
         3) creates a scan list and compile statistics

         :param conf: radio configuration
        """
        # 1) set radio properties as specified in conf
        if conf['nic'] not in iwt.wifaces():
            raise RuntimeError("{0}:iwtools.wifaces:not found".format(conf['role']))
        self._nic = conf['nic']        # save nic name
        self._role = conf['role']      # & role
        self._paused = conf['paused']  # & initial state (paused|scan)
        self._record = conf['record']  # & write frames

        # get the phy and associated interfaces
        try:
            self._phy,ifaces = iw.dev(self._nic)
            self._mac = ifaces[0]['addr']
        except (KeyError, IndexError):
            err = "{0}:iw.dev:error getting interfaces".format(self._role)
            raise RuntimeError(err)
        except iw.IWException as e:
            err = "{0}:iw.dev:failed to get phy <{1}>".format(self._role,e)
            raise RuntimeError(err)

        # get properties (the below will return None rather than throw exception)
        self._chs = iw.chget(self._phy)
        self._std = iwt.iwconfig(self._nic,'Standards')
        self._txpwr = iwt.iwconfig(self._nic,'Tx-Power')
        self._driver = iwt.getdriver(self._nic)
        self._chipset = iwt.getchipset(self._driver)

        # spoof the mac address ??
        if conf['spoofed']:
            mac = None if conf['spoofed'].lower() == 'random' else conf['spoofed']
            try:
                iwt.ifconfig(self._nic,'down')
                self._spoofed = iwt.sethwaddr(self._nic,mac)
            except iwt.IWToolsException as e:
                raise RuntimeError("{0}:iwtools.sethwaddr:{1}".format(self._role,e))

        # 2) prepare specified nic for monitoring and bind it
        # delete all associated interfaces - we want full control
        for iface in ifaces: iw.devdel(iface['nic'])

        # determine virtual interface name
        ns = []
        for wiface in iwt.wifaces():
            cs = wiface.split(self._role)
            try:
                if len(cs) > 1: ns.append(int(cs[1]))
            except ValueError: pass
        n = 0 if not 0 in ns else max(ns)+1
        self._vnic = "iyri{0}".format(n)

        # sniffing interface
        try:
            iw.phyadd(self._phy,self._vnic,'monitor') # create a monitor,
            iwt.ifconfig(self._vnic,'up')             # and turn it on
        except iw.IWException as e:
            # never added virtual nic, restore nic
            errMsg = "{0}:iw.phyadd:{1}".format(self._role,e)
            try:
                iwt.ifconfig(self._nic,'up')
            except iwt.IWToolsException:
                errMsg += " Failed to restore {0}".format(self._nic)
            raise RuntimeError(errMsg)
        except iwt.IWToolsException as e:
            # failed to 'raise' virtual nic, remove vnic and add nic
            errMsg = "{0}:iwtools.ifconfig:{1}".format(self._role,e)
            try:
                iw.phyadd(self._phy,self._nic,'managed')
                iw.devdel(self._vnic)
                iwt.ifconfig(self._nic,'up')
            except (iw.IWException,iwt.IWToolsException):
                errMsg += " Failed to restore {0}".format(self._nic)
            raise RuntimeError(errMsg)

        # wrap remaining in a try block, we must attempt to restore card and
        # release the socket after any failures ATT
        self._s = None
        try:
            # bind socket w/ a timeout of 5 just in case there is no wireless traffic
            self._s = socket.socket(socket.AF_PACKET,
                                    socket.SOCK_RAW,
                                    socket.htons(0x0003))
            self._s.settimeout(5)
            self._s.bind((self._vnic,0x0003))

            # read in antenna details and radio description
            if conf['antennas']['num'] > 0:
                self._antenna['num'] = conf['antennas']['num']
                self._antenna['type'] = conf['antennas']['type']
                self._antenna['gain'] = conf['antennas']['gain']
                self._antenna['loss'] = conf['antennas']['loss']
                self._antenna['x'] = [v[0] for v in conf['antennas']['xyz']]
                self._antenna['y'] = [v[1] for v in conf['antennas']['xyz']]
                self._antenna['z'] = [v[2] for v in conf['antennas']['xyz']]
            self._desc = conf['desc']

            #3) creates a scan list and compile statistics
            scan = [(str(t[0]),t[1]) for t in conf['scan'] if str(t[0]) in self._chs and not t in conf['pass']]

            # sum hop times with side effect of removing any invalid channel tuples
            # i.e. Ch 14, Width HT40+ and any user specified channels the card
            # cannot tune to.
            i = 0
            self._hop = 0
            while scan:
                try:
                    t = time()
                    iw.chset(self._vnic,scan[i][0],scan[i][1])
                    self._hop += (time() - t)
                    i += 1
                except iw.IWException as e:
                    # if invalid argument, drop the channel otherwise reraise error
                    if iw.ecode(str(e)) == iw.IW_INVALIDARG:
                        del scan[i]
                    else:
                        raise
                except IndexError:
                    break
            if not scan: raise ValueError("Empty scan pattern")
            else: self._scan = scan

            # calculate avg hop time, and interval time
            # NOTE: these are not currently used but may be useful later
            self._hop /= len(scan)
            self._interval = len(scan) * conf['dwell'] + len(scan) * self._hop

            # create list of dwell times
            self._ds = [conf['dwell']] * len(self._scan)

            # get start ch & set the initial channel
            try:
                self._chi = scan.index(conf['scan_start'])
            except ValueError: pass
            iw.chset(self._vnic,scan[self._chi][0],scan[self._chi][1])
        except socket.error as e:
            self._shutdown()
            raise RuntimeError("{0}:Raw Socket:{1}".format(self._role,e))
        except iw.IWException as e:
            self._shutdown()
            err = "{0}:iw.chset:Failed to set channel: {1}".format(self._role,e)
            raise RuntimeError(err)
        except (ValueError,TypeError) as e:
            self._shutdown()
            raise RuntimeError("{0}:config:{1}".format(self._role,e))
        except Exception as e: # blanket exception
            self._shutdown()
            raise RuntimeError("{0}:Unknown:{1}".format(self._role,e))

    def _shutdown(self):
        """ restore everything. returns whether a full reset or not occurred """
        # try shutting down & resetting radio (if it failed we may not be able to)
        clean = True
        try:
            iw.devdel(self._vnic)
            iw.phyadd(self._phy,self._nic)
            if self._spoofed: iwt.resethwaddr(self._nic)
            iwt.ifconfig(self._nic,'up')
            if self._s:
                self._s.shutdown(socket.SHUT_RD)
                self._s.close()
            self._cI.close()
        except iw.IWException: clean = False
        except (EOFError,IOError): pass
        except: clean = False
        return clean