#1/usr/bin/env python

""" rdoctl.py: Radio Controller

An interface to an underlying radio (wireless nic). Collects all frames and
forwards to the Collator.

RadioController will 'spawn' a Tuner to handle all channel switching etc and
will concentrate only on pulling frames off the 'wire'.

The convention used here is to allow the Tuner to receive all notifications
from iyri because they may contain user commands. The Tuner will then pass on
to the RadioController
"""
__name__ = 'rdoctl'
__license__ = 'GPL v3.0'
__version__ = '0.1.2'
__date__ = 'January 2016'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

from time import time,sleep                 # current time, waiting
import signal                               # handling signals
import socket                               # reading frames
from Queue import Empty                     # queue empty exception
import multiprocessing as mp                # for Process
import pyric                                # pyric errors
from pyric import pyw                       # card manips
import pyric.utils.hardware as hw           # driver/chipset
import pyric.lib.libnl as nl                # allocate/free nl sockets
from pyric import pyw                       # & nic functions
from wraith.utils.timestamps import isots   # converted timestamp
from wraith.iyri.tuner import Tuner         # our tuner
from wraith.iyri.constants import *         # tuner states & buffer dims
from wraith.utils.valrep import validhwaddr # validate macs

class Radio(dict):
    """
     Wrapper around a dict of radio properties. Exposes each key->value pair
     through '.'
    """
    def __new__(cls,d=None):
        d = super(Radio,cls).__new__(cls,dict({} if not d else d))
        if d == {}:
            d = {'nic':'','vnic':'','phy':-1,'mac':'','role':'','spoofed':'',
                 'driver':'','chipset':'','standards':[],'channels':[],'hop':-1,
                 'ival':-1,'txpwr':-1,'desc':'','nA':0,'type':'','gain':[],
                 'loss':[],'x':[],'y':[],'z':[],'mode':'','card':None}
        return d
    @property
    def nic(self): return self['nic']
    @nic.setter
    def nic(self,v): self['nic'] = str(v)
    @property
    def vnic(self): return self['vnic']
    @vnic.setter
    def vnic(self, v): self['vnic'] = str(v)
    @property
    def phy(self): return self['phy']
    @phy.setter
    def phy(self,v): self['phy'] = int(v)
    @property
    def role(self): return self['role']
    @role.setter
    def role(self,v): self['role'] = str(v)
    @property
    def mode(self): return self['mode']
    @mode.setter
    def mode(self,v): self['mode'] = str(v)
    @property
    def card(self): return self['card']
    @card.setter
    def card(self,v): self['card'] = v
    @property
    def mac(self): return self['mac']
    @mac.setter
    def mac(self,v):
        if validhwaddr(v): self['mac'] = v
        else: raise ValueError("invalid literal for hwaddr(): '{0}'".format(v))
    @property
    def spoofed(self): return self['spoofed']
    @mac.setter
    def mac(self,v):
        if validhwaddr(v): self['spoofed'] = v
        else: raise ValueError("invalid literal for hwaddr(): '{0}'".format(v))
    @property
    def driver(self): return self['driver']
    @driver.setter
    def driver(self,v): self['driver'] = str(v)
    @property
    def chipset(self): return self['chipset']
    @chipset.setter
    def chipset(self,v): self['chipset'] = str(v)
    @property
    def stds(self): return self['standards']
    @stds.setter
    def stds(self,v): self['standards'] = list(v)
    @property
    def chs(self): return self['channels']
    @chs.setter
    def chs(self,v): self['channels'] = list(v)
    @property
    def hop(self): return self['hop']
    @hop.setter
    def hop(self,v): self['hop'] = float(v)
    @property
    def ival(self): return self['ival']
    @ival.setter
    def ival(self,v): self['ival'] = float(v)
    @property
    def txpwr(self): return self['txpwr']
    @txpwr.setter
    def txpwr(self,v): self['txpwr'] = int(v)
    @property
    def desc(self): return self['desc']
    @desc.setter
    def desc(self,v): self['desc'] = str(v)
    @property
    def nA(self): return self['nA']
    @nA.setter
    def nA(self,v): self['nA'] = int(v)
    @property
    def anttypes(self): return self['type']
    @anttypes.setter
    def anttypes(self,v): self['type'] = list(v)
    @property
    def antgains(self): return self['gain']
    @antgains.setter
    def antgains(self,v): self['gain'] = list(v)
    @property
    def antlosses(self): return self['loss']
    @antlosses.setter
    def antlosses(self,v): self['loss'] = list(v)
    @property
    def antxs(self): return self['x']
    @antxs.setter
    def antxs(self,v): self['x'] = list(v)
    @property
    def antys(self): return self['y']
    @antys.setter
    def antys(self,v): self['y'] = list(v)
    @property
    def antzs(self): return self['z']
    @antzs.setter
    def antzs(self,v): self['z'] = list(v)

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
        self._scan = []           # scan list
        self._ds = []             # dwell times list
        self._paused = False      # initial state: pause on True, scan otherwise
        self._chi = 0             # initial channel index
        self._s = None            # the raw socket
        self._rdo = Radio()       # the radio in question
        self._omode = ''          # mode of original device
        self._setup(conf)

    def terminate(self): pass

    def run(self):
        """ run execution loop """
        # ignore signals being used by main program
        signal.signal(signal.SIGINT,signal.SIG_IGN)
        signal.signal(signal.SIGTERM,signal.SIG_IGN)

        # start tuner
        stuner = TUNE_PAUSE if self._paused else TUNE_SCAN
        try:
            qT = mp.Queue()
            tuner = Tuner(qT,self._cI,self._rdo,self._scan,self._ds,self._chi,stuner)
            tuner.start()
            self._icomms.put((self._rdo.vnic,isots(),RDO_RADIO,self.radio))
        except Exception as e:
            self._cI.send((IYRI_ERR,self._rdo.role,type(e).__name__,e))
            self._icomms.put((self._rdo.vnic,isots(),RDO_FAIL,e))
        else:
            msg = "tuner-{0} up".format(tuner.pid)
            self._cI.send((IYRI_INFO,self._rdo.role,'Tuner',msg))

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
                    self._cI.send((CMD_ERR,self._rdo.role,msg[0],msg[1]))
                elif ev == RDO_FAIL:
                    self._cI.send((IYRI_ERR,self._rdo.role,'Tuner',msg[1]))
                    self._icomms.put((self._rdo.vnic,ts,RDO_FAIL,msg[1]))
                elif ev == RDO_STATE:
                    self._cI.send((CMD_ACK,self._rdo.role,msg[0],msg[1]))
                elif ev == RDO_HOLD:
                    stuner = TUNE_HOLD
                    self._icomms.put((self._rdo.vnic,ts,RDO_HOLD,msg[1]))
                    if msg[0] > -1:
                        self._cI.send((CMD_ACK,self._rdo.role,msg[0],msg[1]))
                elif ev == RDO_SCAN:
                    stuner = TUNE_SCAN
                    self._icomms.put((self._rdo.vnic,ts,RDO_SCAN,msg[1]))
                    if msg[0] > -1:
                        self._cI.send((CMD_ACK,self._rdo.role,msg[0],msg[1]))
                elif ev == RDO_LISTEN:
                    stuner = TUNE_LISTEN
                    self._icomms.put((self._rdo.vnic,ts,RDO_LISTEN,msg[1]))
                    if msg[0] > -1:
                        self._cI.send((CMD_ACK,self._rdo.role,msg[0],msg[1]))
                elif ev == RDO_PAUSE:
                    stuner = TUNE_PAUSE
                    self._icomms.put((self._rdo.vnic,ts,RDO_PAUSE,' '))
                    if msg[0] > -1:
                        self._cI.send((CMD_ACK,self._rdo.role,msg[0],msg[1]))
            except Empty: # no notices from Tuner
                if err: continue # error state, wait till iyri sends poison pill
                try:
                    # if paused, pull any frame off and ignore otherwise pass on
                    if stuner == TUNE_PAUSE: _ = self._s.recv(n)
                    else:
                        l = self._s.recv_into(self._buffer[(ix*n):(ix*n)+n],n)
                        self._icomms.put((self._rdo.vnic,isots(),RDO_FRAME,(ix,l)))
                        ix = (ix+1) % m
                except socket.timeout: pass
                except socket.error as e:
                    err = True
                    self._cI.send((IYRI_ERR,self._rdo.role,'Socket',e))
                    self._icomms.put((self._rdo.vnic,isots(),RDO_FAIL,e))
                except Exception as e:
                    err = True
                    self._cI.send((IYRI_ERR,self._rdo.role,type(e).__name__,e))
                    self._icomms.put((self._rdo.vnic,isots(),RDO_FAIL,e))

        # wait on Tuner to finish
        while mp.active_children(): sleep(0.5)

        # notify Iyri and Collator we are down & shut down
        self._cI.send((IYRI_DONE,self._rdo.role,'done','done'))
        self._icomms.put((self._rdo.vnic,isots(),RDO_RADIO,None))
        if not self._shutdown():
            try:
                self._cI.send((IYRI_WARN,self._rdo.role,'Shutdown',"Incomplete reset"))
            except (EOFError,IOError): pass

    @property
    def radio(self):
        """ returns a dict describing this radio """
        return {'nic':self._rdo.nic,
                'vnic':self._rdo.vnic,
                'phy':self._rdo.phy,
                'mac':self._rdo.mac,
                'role':self._rdo.role,
                'spoofed':self._rdo.spoofed,
                'driver':self._rdo.driver,
                'chipset':self._rdo.chipset,
                'standards':self._rdo.stds,
                'channels':self._rdo.chs,
                'hop':'{0:.3}'.format(self._rdo.hop),
                'ival':'{0:.3}'.format(self._rdo.ival),
                'txpwr':self._rdo.txpwr,
                'desc':self._rdo.desc,
                'nA':self._rdo.nA,
                'type':self._rdo.anttypes,
                'gain':self._rdo.antgains,
                'loss':self._rdo.antlosses,
                'x':self._rdo.antxs,
                'y':self._rdo.antys,
                'z':self._rdo.antzs}

    # private helper functions

    def _setup(self,conf):
        """
         1) sets radio properties as specified in conf
         2) prepares specified nic for monitoring and binds it
         3) creates a scan list and compile statistics

         :param conf: radio configuration
        """
        # set radio properties as specified in conf
        if conf['nic'] not in pyw.winterfaces():
            raise RuntimeError("{0}:radio.nic:not found".format(conf['role']))
        else:
            self._rdo['nic'] = conf['nic']
        self._rdo.role = conf['role']  # save role
        self._paused = conf['paused']  # & initial state (paused|scan)
        if conf['spoofed']: self._rdo = conf['spoofed']
        self._desc = conf['desc']
        if conf['antennas']['num'] > 0:
            self._rdo.nA = conf['antennas']['num']
            self._rdo.anttypes = conf['antennas']['type']
            self._rdo.antgains = conf['antennas']['gain']
            self._rdo.antlosses = conf['antennas']['loss']
            self._rdo.antxs = [v[0] for v in conf['antennas']['xyz']]
            self._rdo.antys = [v[1] for v in conf['antennas']['xyz']]
            self._rdo.antzs = [v[2] for v in conf['antennas']['xyz']]

        # determine virtual interface name
        ns = []
        for wiface in pyw.winterfaces():
            cs = wiface.split('iyri')
            try:
                if len(cs) == 2: ns.append(int(cs[1]))
            except ValueError:
                pass
        n = 0 if not ns else max(ns)+1
        self._rdo.vnic = "iyri{0}".format(n)

        # wrap remaining in a try block, we must attempt to restore card and
        # release the socket after any failures
        self._s = None
        nlsock = None
        try:
            # get a netlink socket. We use this socket for all calls and
            # free it on exit from the try block
            nlsock = nl.nl_socket_alloc()

            # get radio properties from device/physical
            self._rdo.driver,self._rdo.chipset = hw.ifcard(self._rdo.nic)
            dinfo = pyw.devinfo(self._rdo.nic,nlsock)
            card = dinfo['card']
            self._rdo.mac = dinfo['mac']
            self._omode = dinfo['mode']
            self._rdo.stds = pyw.devstds(card)
            self._rdo.chs = pyw.phyinfo(card,nlsock)['channels']

            # create our monitor interface, del. all associated interfaces
            for iface in pyw.ifaces(card,nlsock): pyw.devdel(iface[0])
            self._rdo.card = pyw.devadd(card,self._rdo.vnic,'monitor',nlsock)
            self._rdo.mode = 'monitor'
            pyw.up(self._rdo.card)

            # NOTE: we wait until bringing the card up to get tx in case
            # the reg. domain was changed
            self._rdo.txpwr = pyw.txget(self._rdo.card)

            # bind socket w/ a timeout of 5 in case there is no wireless traffic
            self._s = socket.socket(socket.AF_PACKET,socket.SOCK_RAW,socket.htons(0x0003))
            self._s.settimeout(5)
            self._s.bind((self._rdo.vnic,0x0003))

            #3) creates a scan list and compile statistics
            ss = conf['scan']
            ps = conf['pass']
            cs = self._rdo.chs
            scan = [(c[0],c[1]) for c in ss if c[0] in cs and c in ps]

            # sum hop times with side effect of removing any invalid channel tuples
            # i.e. Ch 14, Width HT40+ and any user specified channels the card
            # cannot tune to.
            i = 0
            self._rdo.hop = 0
            while scan:
                try:
                    t = time()
                    pyw.chset(self._rdo.card,scan[i][0],scan[i][1],nlsock)
                    self._rdo.hop += (time() - t)
                    i += 1
                except pyric.error:
                    del scan[i]
                except IndexError:
                    break

            # something bad happened if we have no channels remaining in scan
            if not scan:
                raise ValueError("Empty scan pattern")
            else:
                self._scan = scan

            # calculate avg hop time, and interval time
            self._rdo.hop /= float(len(scan))
            self._rdo.ival = len(scan) * conf['dwell'] + len(scan) * self._rdo.hop

            # create list of dwell times
            # **** This is not used yet, but may be in the future, if we can
            # determine an algorithm that adjust dwell times based on # of
            # packets coming in
            self._ds = [conf['dwell']] * len(self._scan)

            # get start ch & set the initial channel
            try:
                self._chi = scan.index(conf['scan_start'])
            except ValueError:
                self._chi = 0
            self._rdo.setch(scan[self._chi][0],scan[self._chi][1])
        except socket.error as e:
            self._shutdown()
            raise RuntimeError("{0}:Raw Socket:{1}".format(self._rdo.role,e))
        except pyric.error as e:
            self._shutdown()
            raise RuntimeError("{0}:pyw:Error {1}->{2}".format(self._rdo.role,
                                                               e.errno,
                                                               e.strerror))
        except (ValueError,TypeError) as e:
            self._shutdown()
            raise RuntimeError("{0}:config:{1}".format(self._rdo.role,e))
        except Exception as e: # blanket exception
            self._shutdown()
            raise RuntimeError("{0}:Unknown:{1}".format(self._rdo.role,e))
        finally:
            if nlsock: nl.nl_socket_free(nlsock)

    def _shutdown(self):
        """ restore everything. returns whether a full reset or not occurred """
        # try shutting down & resetting radio (if it failed we may not be able to)
        clean = True
        try:
            # unbind socket if necessary
            if self._s:
                self._s.shutdown(socket.SHUT_RD)
                self._s.close()

            # reset radio if necessary
            oldcard = None
            if self._rdo:
                if self._rdo.mode == 'monitor':
                    # delete the monitor card and restore the original
                    oldcard = pyw.devadd(self._rdo.card,self._rdo.nic,self._omode)
                    pyw.devdel(self._rdo.card)

                if self._rdo.spoofed: pyw.macset(self._rdo.mac)
            if oldcard: pyw.up(oldcard)

            # close comm channel
            self._cI.close()
        except pyric.error: clean = False
        except (EOFError,IOError): pass
        except: clean = False
        return clean