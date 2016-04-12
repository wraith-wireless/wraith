#!/usr/bin/env python

""" radio.py: network interface card

Provides the Radio class, a network interface card, which consolidates network
card manipulation and attribute functionality into a single object. Also
provides several standalone functions w.r.t regulatory domain and system

At present, is a wrapper around iw.py functions which use iw and iwlist but
is now implemeting all iwconfig and ifconfig functionality through ioctl

"""
__name__ = 'radio'
__license__ = 'GPL v3.0'
__version__ = '0.0.5'
__date__ = 'February 2016'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

from toolbox.bits import issetf              # flag on verification
import pyric                                 # pyric error & error codes
from pyric import pyw                        # pyw commands
import pyric.utils as pywutils               # driver/chipset
import pyric.net.if_h as ifh                 # for interface flags
import pyric.lib.libnl as nl                 # netlink library
import pyric.lib.libio as io                 # ioctl library
from wraith.wifi.interface.oui import randhw # random hwaddr
from wraith.wifi.interface import iw         # iw cmdline parsing

# Exception
# Define error code for unitialized, all others are defined in pyric
RDO_UNINITIALIZED = -1
class RadioException(EnvironmentError): pass # tuple t = (errcode,errmessage)

#### setrd/getrd left for posterity
def setrd(rd):
    """
     set the regulatory domain
     :param rd: desired two-character domain
    """
    try:
        pyw.regdom(rd)
    except pyric.error as e:
        raise RadioException(e.errno,e.strerror)

def getrd():
    """ return the current regulatory domain """
    try:
        return pyw.regdom()
    except pyric.error as e:
        raise RadioException(e.errno, e.strerror)

class Radio(object):
    """ define properties/methods of a wireless network interface """
    def __init__(self,nic=None,vnic=None,spoof=None):
        """
         initializes Radio from network interface card. If vnic is present will
         create a monitor interface on this Radio. If spoofed is present, will
         set the spoofed hw address
         :param nic: name of nic to initialize
         :param vnic: name of virtual interface to create in monitor mode
         :param spoof: spoofed hwaddress if desired

         If the Radio is not initialized i.e. nic is None, the appropiate method
         for later setup is
          1) setnic
          2) spoof (optional)
          3) watch(vnic)
        """
        # default/uninstantiated attributes
        # NOTE: we only set member variables for those "immutable" properties
        # of a wireless nic such as phy (the physical name of the card) of driver
        # those properties that can change i.e. txpwr, current channel etc
        # will be determined by 'querying' the card
        self._phy = None       # the <phy> of the card specified by nic
        self._ifindex = None   # ifindex
        self._hwaddr = None    # the real hw addr
        self._spoofed = None   # the current/spoofed hw addr
        self._standards = None # supported standards i.e. 'b','g','n'
        self._channels = []    # list of supported channels (by number)
        self._driver = None    # driver if known
        self._chipset = None   # chipset if known

        # these attributes are mutable but we use them as semi-immutable
        # NOTE: the Radio will be identified by either the nic, meaning it is
        # not yet initialized or vnic meaning it is in monitor mode
        self._nic = None
        self._nicmode = None
        self._vnic = None

        # internal attributes for kernel/device comms
        self._nlsock = None # netlink socket
        self._seq = None    # netlink seq number
        self._iosock = None # ioctl socket

        # create the netlink socket & get the family id
        try:
            self._nlsock = nl.nl_socket_alloc()
        except pyric.error as e:
            raise RadioException(e.errno,e.strerror)

        # create the ioctl socket
        try:
            self._iosock = io.io_socket_alloc()
        except pyric.error as e:
            raise RadioException(e.errno,e.strerror)

        if nic: self._setup(nic,vnic,spoof)

    def __del__(self):
        """ closes out the internal sockets """
        if self._nlsock: nl.nl_socket_free(self._nlsock)
        if self._iosock: io.io_socket_free(self._iosock)

    def setnic(self,nic):
        """
         (re)initializes Radio using nic
         :param nic: name of interface
        """
        self._phy = None
        self._ifindex = None
        self._hwaddr = None
        self._spoofed = None
        self._standards = []
        self._channels = []
        self._driver = None
        self._chipset = None
        self._nic = None
        self._vnic = None
        self._setup(nic)

#### attributes

    @property # :returns: physical name of Radio
    def phy(self): return self._phy

    @property # :returns: True if Radio is up
    def isup(self):
        nic = self.curnic
        if nic is None: raise RadioException(RDO_UNINITIALIZED,"Uninitialized")
        try:
            return issetf(pyw.ifflagsex(self._iosock,nic),ifh.IFF_UP)
        except pyric.error as e:
            raise RadioException(e.errno,e.strerror)

    @property # :returns: interface index
    def ifindex(self): return self._ifindex

    @property # :returns: the nic name (if any)
    def nic(self): return self._nic

    @property # :returns: the nic name (if any)
    def vnic(self): return self._vnic

    @property # :returns: 'current' nic
    def curnic(self): return self._vnic or self._nic

    @property
    def ifaces(self):
        """
         current interfaces belonging to this Radio
         :returns: all (current) interfaces on this Radio
          as a list of dicts
        """
        if not self._phy: raise RadioException(RDO_UNINITIALIZED,"Uninitialized")
        try:
            return iw.dev()[self._phy]
        except iw.IWException as e:
            raise RadioException((iw.ecode(e),e))
        except KeyError:
            raise RadioException(pyric.NLE_NODEV,"No such device (-19)")

    @property
    def channel(self):
        """
         :returns: the channel # Radio is currently on or None
         NOTE: this will only work if Radio is associated with an AP - will
         not work if Radio is in monitor mode
        """
        nic = self.curnic
        if nic is None: raise RadioException(RDO_UNINITIALIZED,"Uninitialized")
        try:
            return iw.curchget(nic)
        except iw.IWException as e:
            raise RadioException(iw.ecode(e),e)

    @property
    def channels(self):
        """ :returns: list of all supported channels of this Radio """
        if not self._channels: raise RadioException(RDO_UNINITIALIZED,"Uninitialized")
        return self._channels

    @property
    def standards(self):
        """ :returns: supported standards i.e. 'a', 'b' etc """
        if not self._standards: raise RadioException(RDO_UNINITIALIZED,"Uninitialized")
        return self._standards

    @property
    def hwaddr(self):
        """ :returns: actual hardware address """
        nic = self.curnic
        if nic is None: raise RadioException(RDO_UNINITIALIZED,"Uninitialized")
        try:
            return pyw.ifhwaddrex(self._iosock,nic)
        except pyric.error as e:
            raise RadioException(e.errno,e.strerror)

    @property
    def spoofed(self):
        """:returns: spoofed hardware address """
        nic = self.curnic
        if nic is None: raise RadioException(RDO_UNINITIALIZED,"Uninitialized")
        return self._spoofed

    @property
    def mode(self):
        """ :returns the mode of this Radio """
        # does not work
        nic = self.curnic
        if nic is None: raise RadioException(RDO_UNINITIALIZED,"Uninitialized")
        try:
            _,ifaces = iw.dev(nic)
            for iface in ifaces:
                if iface['nic'] == nic: return iface['type']
            return None
        except iw.IWException as e:
            raise RadioException(iw.ecode(e),e)

    @property
    def txpwr(self):
        """ :returns: current transmit power (in dBm) """
        nic = self.curnic
        if nic is None: raise RadioException(RDO_UNINITIALIZED,"Uninitialized")
        try:
            return pyw.txpwrex(self._iosock,nic)
        except pyric.error as e:
            raise RadioException(e.errno,e.strerror)

    @property
    def driver(self):
        """ :returns: driver for this Radio """
        nic = self.curnic
        if nic is None: RadioException((RDO_UNINITIALIZED,"Uninitialized"))
        return self._driver

    @property
    def chipset(self):
        """:returns: chipset for this Radio """
        nic = self.curnic
        if nic is None: raise RadioException(RDO_UNINITIALIZED,"Uninitialized")
        return self._chipset

#### methods

    def up(self):
        """ turns Radio on """
        nic = self.curnic
        if nic is None: raise RadioException(RDO_UNINITIALIZED,"Uninitialized")
        try:
            pyw.ifupex(self._iosock,nic)
        except pyric.error as e:
            raise RadioException(e.errno,e.strerror)

    def down(self):
        """ turns Radio off """
        nic = self.curnic
        if nic is None: raise RadioException(RDO_UNINITIALIZED,"Uninitialized")
        try:
            pyw.ifdownex(self._iosock,nic)
        except pyric.error as e:
            raise RadioException(e.errno, e.strerror)

    def watch(self,vnic):
        """
         creates a monitor interface name vnic on this Radio, deleting all other
         associated interfaces to avoid conflicts with external processes &
         the system
         :param vnic: name of virtual interface to create in monitor mode
        """
        # get all associated interfaces and delete them
        for iface in self.ifaces: iw.devdel(iface['nic'])
        try:
            iw.phyadd(self._phy,vnic,'monitor') # add monitor mode vnic
            self._vnic = vnic
            self.up()
        except iw.IWException as e:
            raise RadioException(iw.ecode(e),e)

    def unwatch(self):
        """
         removes the virtual interface this Radio (and adds the original nic
         back to it's orginal state)
         NOTE: this does not restore all interfaces that were deleted by watch
        """
        if not self._vnic:
            raise RadioException(pyric.NLE_OPNOTSUPP,"Radio is not in monitor mode")
        try:
            iw.devdel(self._vnic)
            self._vnic = None
            iw.phyadd(self._phy,self._nic,self._nicmode)
            self.up()
        except iw.IWException as e:
            raise RadioException(iw.ecode(e),e)

    def spoof(self,hwaddr):
        """
         sets spoofed hw address
         :param hwaddr: 48 bit hex mac address of form XX:XX:XX:XX:XX:XX
        """
        if hwaddr.lower() == 'random': hwaddr = randhw()
        nic = self.curnic
        if nic is None: raise RadioException(RDO_UNINITIALIZED,"Uninitialized")
        self.down()
        try:
            newmac = pyw.ifhwaddrex(self._iosock,nic,hwaddr)
        except pyric.error as e:
            raise RadioException(e.errno,e.strerror)
        self.up()
        if newmac == hwaddr: self._spoofed = newmac

    def unspoof(self):
        """ resets hw address """
        nic = self.curnic
        if nic is None: raise RadioException(RDO_UNINITIALIZED,"Uninitialized")
        self.down()
        oldmac = pyw.ifhwaddrex(self._iosock,nic,self.hwaddr)
        try:
            self.up()
        except pyric.error as e:
            raise RadioException(e.errno,e.strerror)
        if oldmac == self.hwaddr: self._spoofed = None

    def settxpwr(self,pwr,option='fixed'):
        """
         set tx power
        :param pwr: desired txpower in dBm
        :param option: desired option oneof {'fixed'|'limit'|'auto'}
        """
        # NOTE: this does not work on my card(s) using either phy or nic
        # have also tried using ioctl w/ SIOCSIWTXPOW but this does not
        # work either.
        try:
            iw.txpwrset(self._phy,pwr,option)
        except iw.IWException as e:
            raise RadioException(iw.ecode(e),e)

    def setch(self,ch,chw=None):
        """
         sets channel
         :param ch: channel (number) to set card to
         :param chw: channel width to set to default is None
        """
        if not self._phy: raise RadioException(RDO_UNINITIALIZED,"Uninitialized")
        if not chw in pyw.CHWIDTHS:
            raise RadioException(pyric.NLE_INVAL,"Channel width is invalid")

        try:
            iw.chset(self._phy,ch,chw)
        except iw.IWException as e:
            raise RadioException(iw.ecode(e),e)

#### PRIVATE FUNCTIONS ####

    def _setup(self,nic,vnic=None,spoof=None):
        """
         initialize immutable properties from network interface card
         :param nic: name of nic to initialize
         :param vnic: name of virtual interface to create in monitor mode
         :param spoof: spoof hwaddress if desired
        """
        try:
            # initialize Radio's attributes
            interface = None
            self._phy,ifaces = iw.dev(nic)
            for iface in ifaces:
                if iface['nic'] == nic: interface = iface
            self._nic = nic
            self._nicmode = interface['type']
            self._hwaddr = pyw.ifhwaddrex(self._iosock,self._nic)
            self._ifindex = pyw.ifindexex(self._iosock,self._nic)
            self._channels = iw.chget(self._phy)
            self._standards = pyw.standardsex(self._iosock,self._nic)
            self._driver = pywutils.ifdriver(self._nic)
            self._chipset = pywutils.ifchipset(self._driver)
            if spoof: self.spoof(spoof)  # create a spoofed address?
            if vnic: self.watch(vnic)  # create in montor mode?
        except TypeError: raise RadioException(pyric.NLE_UNDEF,"Unexpected error")
        except RadioException: raise
        except pyric.error as e:
            raise RadioException(e.errno,e.strerror)
        except iw.IWException as e:
            raise RadioException(iw.ecode(e),e)