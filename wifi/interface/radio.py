#!/usr/bin/env python

""" radio.py: network interface card

Provides the Radio class, a network interface card, which consolidates network
card manipulation and attribute functionality into a single object. Also
provides several standalone functions w.r.t regulatory domain and system

At present, is merely a wrapper around iw.py and iwtools.py functions which
use the iw, iwlist, iwconfig and ifconfig command lines tools via popen.
Will move to ioctl, netlink as appropriate commands are determined

Exports
 Radio: wireless network card
 interfaces: list of all interfaces on system
 winterfaces: list of all wireless interfaces on system
 setrd: set the regulatory domain
 getrd: get the regulatory domain
 driver: get driver for a network interface
 chipset: get chipset for a driver
"""
__name__ = 'radio'
__license__ = 'GPL v3.0'
__version__ = '0.0.1'
__date__ = 'February 2016'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import os
from wraith.wifi.interface import iw
from wraith.wifi.interface import iwtools as iwt

# widths currently supported
IW_CHWS = [None,'HT20','HT40+','HT40-']

def interfaces():
    """ :returns: a list of names of current network interfaces cards """
    # read in devices from /proc/net/dev. After splitting on newlines, the first
    # 2 lines are headers and the last line is empty so we remove them
    try:
        fin = open('/proc/net/dev','r')
        ns = fin.read().split('\n')[2:-1]
        fin.close()
    except Exception as e:
        raise RadioException('ifaces: {0}'.format(e))

    # the remaining lines are <nicname>: p1 p2 ... p3, split on ':' & strip whitespace
    nics = []
    for nic in ns: nics.append(nic.split(':')[0].strip())
    return nics

def winterfaces():
    """ :returns: a list of names of current wwireless network interfaces cards """
    # tried reading in devices from /proc/net/wireless but it did not always
    # include my usb interfaces.
    try:
        return iwt.wifaces()
    except Exception as e:
        raise RadioException('wifaces: {0}'.format(e))

def setrd(rd):
    """
     set the regulatory domain
     :param rd: desired two-character domain
    """
    try:
        iw.regset(rd)
    except iw.IWException as e:
        raise RadioException(e)

def getrd():
    """ return the current regulatory domain """
    try:
        return iw.regget()
    except iw.IWException as e:
        raise RadioException(e)

def driver(nic):
    """
     determines driver of nic
     :param nic: interface name
     :returns: driver (or unknown if cannot be found)
    """
    try:
        # find the driver for nic in driver's module, split on ':' and return
        ds = os.listdir('/sys/class/net/{0}/device/driver/module/drivers'.format(nic))
        if len(ds) > 1: return "Unknown"
        return ds[0].split(':')[1]
    except OSError:
        return "Unknown"

def chipset(driver):
    """
     returns the chipset for given driver (Thanks aircrack-ng team)
     NOTE: does not fully implement the airmon-ng getChipset where identification
      requires system commands
     :param driver: driver of device
     :returns: chipset of driver
    """
    if not driver: return "Unknown"
    if driver == "Unknown": return "Unknown"
    if driver == "Otus" or driver == "arusb_lnx": return "AR9001U"
    if driver == "WiLink": return "TIWLAN"
    if driver == "ath9k_htc" or driver == "usb": return "AR9001/9002/9271"
    if driver.startswith("ath") or driver == "ar9170usb": return "Atheros"
    if driver == "zd1211rw_mac80211": return "ZyDAS 1211"
    if driver == "zd1211rw": return "ZyDAS"
    if driver.startswith("acx"): return "TI ACX1xx"
    if driver == "adm8211": return "ADMtek 8211"
    if driver == "at76_usb": return "Atmel"
    if driver.startswith("b43") or driver == "bcm43xx": return "Broadcom"
    if driver.startswith("p54") or driver == "prism54": return "PrismGT"
    if driver == "hostap": return "Prism 2/2.5/3"
    if driver == "r8180" or driver == "rtl8180": return "RTL8180/RTL8185"
    if driver == "rtl8187" or driver == "r8187": return "RTL8187"
    if driver == "rt2570" or driver == "rt2500usb": return "Ralink 2570 USB"
    if driver == "rt2400" or driver == "rt2400pci": return "Ralink 2400 PCI"
    if driver == "rt2500" or driver == "rt2500pci": return "Ralink 2560 PCI"
    if driver == "rt61" or driver == "rt61pci": return "Ralink 2561 PCI"
    if driver == "rt73" or driver == "rt73usb": return "Ralink 2573 USB"
    if driver == "rt2800" or driver == "rt2800usb" or driver == "rt3070sta": return "Ralink RT2870/3070"
    if driver == "ipw2100": return "Intel 2100B"
    if driver == "ipw2200": return "Intel 2200BG/2915ABG"
    if driver == "ipw3945" or driver == "ipwraw" or driver == "iwl3945": return "Intel 3945ABG"
    if driver == "ipw4965" or driver == "iwl4965": return "Intel 4965AGN"
    if driver == "iwlagn" or driver == "iwlwifi": return "Intel 4965/5xxx/6xxx/1xxx"
    if driver == "orinoco": return "Hermes/Prism"
    if driver == "wl12xx": return "TI WL1251/WL1271"
    if driver == "r871x_usb_drv": return "Realtek 81XX"
    return "Unknown"

# need exceptions
class RadioException(Exception): pass            # Generic
class RadioNotInitialized(RadioException): pass  # radio is empty
class RadioNoPermission(RadioException): pass    # iw error -1
class RadioBusyDevice(RadioException): pass      # iw error -16
class RadioNicNotFound(RadioException): pass     # iw error -19
class RadioInvalidArg(RadioException): pass      # iw error -22
class RadioExceedOpenFiles(RadioException): pass # iw error -23
class RadioOpNotPermitted(RadioException): pass  # iw error -95

class Radio(object):
    """ define properties/methods of a wireless network interface """
    def __init__(self,nic=None,vnic=None,spoofed=None):
        """
         initializes Radio from network interface card. If vnic is present will
         create a monitor interface on this Radio. If spoofed is present, will
         set the spoofed hw address
         :param nic: name of nic to initialize
         :param vnic: name of virtual interface to create in monitor mode
         :param spoofed: spoofed hwaddress if desired

         If the Radio is not initialized i.e. nic is None, the appropiate method
         for later setup is
          1) setnic
          2) cloak (optional)
          3) watch
        """
        # default/uninstantiated attributes
        # NOTE: we only set member variables for those "immutable" properties
        # of a wireless nic such as phy (the physical name of the card) of driver
        # those properties that can change i.e. txpwr, current channel etc
        # will be determined by 'querying' the card
        self._phy = None      # the <phy> of the card specified by nic
        self._ifindex = None  # ifindex (do we need this)
        self._hwaddr = None   # the real hw addr
        self._spoofed = None  # the current/spoofed hw addr
        self._standards = []  # list of supported standards i.e. ['b','g','n']
        self._channels = []   # list of supported channels (by number)
        self._driver = None   # driver if known
        self._chipset = None  # chipset if known

        # these attributes are mutable be we store them for now as we need a nic
        # name for calls to iw/iwtools
        self._nic = None
        self._nicmode = None
        self._vnic = None
        if nic: self._setup(nic,vnic,spoofed)

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

    @property
    def phy(self):
        """ :returns: physical name of Radio """
        return self._phy

    @property
    def nic(self):
        """ :returns: the nic name (if any) """
        return self._nic

    @property
    def vnic(self):
        """ :returns: the nic name (if any) """
        return self._vnic

    @property
    def ifaces(self):
        """
         current interfaces belonging to this Radio
         :returns: all (current) interfaces on this Radio
          as a list of dicts
        """
        if not self._phy: raise RadioNotInitialized
        try:
            return iw.dev()[self._phy]
        except iw.IWException as e:
            ecode = iw.ecode(e)
            if ecode == iw.IW_PERMISSION: raise RadioNoPermission(e)
            elif ecode == iw.IW_BUSY: raise RadioBusyDevice(e)
            elif ecode == iw.IW_NONIC: raise RadioNicNotFound(e)
            elif ecode == iw.IW_INVALIDARG: raise RadioInvalidArg(e)
            elif ecode == iw.IW_EXCEED: raise RadioExceedOpenFiles(e)
            elif ecode == iw.IW_OPERATION: raise RadioOpNotPermitted(e)
            else: raise RadioException(e)
        except KeyError:
            raise RadioNicNotFound("No such device (-19)")

    @property
    def channel(self):
        """
         :returns: the channel # Radio is currently on or None
         NOTE: this will only work if Radio is associated with an AP - will
         not work if Radio is in monitor mode
        """
        nic = self._vnic if self._vnic else self._nic
        if nic is None: raise RadioNotInitialized
        try:
            return iw.curchget(nic)
        except iw.IWException as e:
            raise RadioException(e)

    @property
    def channels(self):
        """ :returns: list of all supported channels of this Radio """
        if not self._channels: raise RadioNotInitialized
        return self._channels

    @property
    def standards(self):
        """ :returns: supported standards i.e. 'a', 'b' etc """
        if not self._standards: raise RadioNotInitialized
        return self._standards

    @property
    def hwaddr(self):
        """ :returns: actual hardware address """
        nic = self._vnic if self._vnic else self._nic
        if nic is None: raise RadioNotInitialized
        return self._hwaddr

    @property
    def spoofed(self):
        """:returns: spoofed hardware address """
        nic = self._vnic if self._vnic else self._nic
        if nic is None: raise RadioNotInitialized
        return self._spoofed

    @property
    def mode(self):
        """ :returns the mode of this Radio """
        # does not work
        nic = self._vnic if self._vnic else self._nic
        if nic is None: raise RadioNotInitialized
        try:
            _,ifaces = iw.dev(nic)
            for iface in ifaces:
                if iface['nic'] == nic: return iface['type']
            return None
        except iw.IWException as e:
            ecode = iw.ecode(e)
            if ecode == iw.IW_PERMISSION: raise RadioNoPermission(e)
            elif ecode == iw.IW_BUSY: raise RadioBusyDevice(e)
            elif ecode == iw.IW_NONIC: raise RadioNicNotFound(e)
            elif ecode == iw.IW_INVALIDARG: raise RadioInvalidArg(e)
            elif ecode == iw.IW_EXCEED: raise RadioExceedOpenFiles(e)
            elif ecode == iw.IW_OPERATION: raise RadioOpNotPermitted(e)
            else: raise RadioException(e)

    @property
    def txpwr(self):
        """ :returns: current transmit power (in dBm) """
        nic = self._vnic if self._vnic else self._nic
        if nic is None: raise RadioNotInitialized
        try:
            return iw.txpwrget(nic)
        except iw.IWException as e:
            ecode = iw.ecode(e)
            if ecode == iw.IW_PERMISSION: raise RadioNoPermission(e)
            elif ecode == iw.IW_BUSY: raise RadioBusyDevice(e)
            elif ecode == iw.IW_NONIC: raise RadioNicNotFound(e)
            elif ecode == iw.IW_INVALIDARG: raise RadioInvalidArg(e)
            elif ecode == iw.IW_EXCEED: raise RadioExceedOpenFiles(e)
            elif ecode == iw.IW_OPERATION: raise RadioOpNotPermitted(e)
            else: raise RadioException(e)

    @property
    def driver(self):
        """ :returns: driver for this Radio """
        nic = self._vnic if self._vnic else self._nic
        if nic is None: raise RadioNotInitialized
        return self._driver

    @property
    def chipset(self):
        """:returns: chipset for this Radio """
        nic = self._vnic if self._vnic else self._nic
        if nic is None: raise RadioNotInitialized
        return self._chipset

#### methods

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
            iwt.ifconfig(vnic,'up')             # & bring it up
            self._vnic = vnic
        except iwt.IWToolsException as e: raise RadioException(e)
        except iw.IWException as e:
            ecode = iw.ecode(e)
            if ecode == iw.IW_PERMISSION: raise RadioNoPermission(e)
            elif ecode == iw.IW_BUSY: raise RadioBusyDevice(e)
            elif ecode == iw.IW_NONIC: raise RadioNicNotFound(e)
            elif ecode == iw.IW_INVALIDARG: raise RadioInvalidArg(e)
            elif ecode == iw.IW_EXCEED: raise RadioExceedOpenFiles(e)
            elif ecode == iw.IW_OPERATION: raise RadioOpNotPermitted(e)
            else: raise RadioException(e)

    def unwatch(self):
        """
         removes the virtual interface this Radio (and adds the original nic
         back to it's orginal state)
         NOTE: this does not restore all interfaces that were deleted by watch
        """
        if not self._vnic: raise RadioException("Radio is not in monitor mode")
        try:
            iw.devdel(self._vnic)
            iw.phyadd(self._phy,self._nic,self._nicmode)
            iwt.ifconfig(self._nic,'up')
            self._vnic = None
        except iwt.IWToolsException as e: raise RadioException(e)
        except iw.IWException as e:
            ecode = iw.ecode(e)
            if ecode == iw.IW_PERMISSION: raise RadioNoPermission(e)
            elif ecode == iw.IW_BUSY: raise RadioBusyDevice(e)
            elif ecode == iw.IW_NONIC: raise RadioNicNotFound(e)
            elif ecode == iw.IW_INVALIDARG: raise RadioInvalidArg(e)
            elif ecode == iw.IW_EXCEED: raise RadioExceedOpenFiles(e)
            elif ecode == iw.IW_OPERATION: raise RadioOpNotPermitted(e)
            else: raise RadioException(e)

    def cloak(self,hwaddr):
        """
         sets spoofed hw address
         :param hwaddr: 48 bit hex mac address of form XX:XX:XX:XX:XX:XX
        """
        nic = self._vnic if self._vnic else self._nic
        if nic is None: raise RadioNotInitialized
        try:
            iwt.ifconfig(nic,'down')
            self._spoofed = iwt.sethwaddr(nic,hwaddr)
            iwt.ifconfig(nic,'up')
        except iwt.IWToolsException as e:
            raise RadioException(e)

    def uncloak(self):
        """ resets hw address """
        nic = self._vnic if self._vnic else self._nic
        if nic is None: raise RadioNotInitialized
        try:
            iwt.ifconfig(nic,'down')
            iwt.resethwaddr(nic)
            iwt.ifconfig(nic,'up')
            self._spoofed = None
        except iwt.IWToolsException as e:
            raise RadioException(e)

    def settxpwr(self,pwr,option='fixed'):
        """
         set tx power
        :param pwr: desired txpower in dBm
        :param option: desired option oneof {'fixed'|'limit'|'auto'}
        """
        # this will not work for all cards
        try:
            iw.txpwrset(self._phy,pwr,option)
        except iw.IWException as e:
            ecode = iw.ecode(e)
            if ecode == iw.IW_PERMISSION: raise RadioNoPermission(e)
            elif ecode == iw.IW_BUSY: raise RadioBusyDevice(e)
            elif ecode == iw.IW_NONIC: raise RadioNicNotFound(e)
            elif ecode == iw.IW_INVALIDARG: raise RadioInvalidArg(e)
            elif ecode == iw.IW_EXCEED: raise RadioExceedOpenFiles(e)
            elif ecode == iw.IW_OPERATION: raise RadioOpNotPermitted(e)
            else: raise RadioException(e)

    def setch(self,ch,chw=None):
        """
         sets channel
         :param ch: channel (number) to set card to
         :param chw: channel width to set to default is None
        """
        if not self._phy: raise RadioNotInitialized
        if not chw in iw.IW_CHWS:
            raise RadioInvalidArg("Channel width is invalid (-19)")

        try:
            iw.chset(self._phy,ch,chw)
        except iw.IWException as e:
            ecode = iw.ecode(e)
            if ecode == iw.IW_PERMISSION: raise RadioNoPermission(e)
            elif ecode == iw.IW_BUSY: raise RadioBusyDevice(e)
            elif ecode == iw.IW_NONIC: raise RadioNicNotFound(e)
            elif ecode == iw.IW_INVALIDARG: raise RadioInvalidArg(e)
            elif ecode == iw.IW_EXCEED: raise RadioExceedOpenFiles(e)
            elif ecode == iw.IW_OPERATION: raise RadioOpNotPermitted(e)
            else: raise RadioException(e)

#### PRIVATE FUNCTIONS ####

    def _setup(self,nic,vnic=None,spoofed=None):
        """
         initialize immutable properties from network interface card
         :param nic: name of nic to initialize
         :param vnic: name of virtual interface to create in monitor mode
         :param spoofed: spoofed hwaddress if desired (can be 'random')
        """
        try:
            interface = None
            self._phy,ifaces = iw.dev(nic)
            for iface in ifaces:
                if iface['nic'] == nic: interface = iface
            self._nic = nic
            self._nicmode = interface['type']
            self._hwaddr = interface['addr']
            self._ifindex = interface['ifindex'] # see /sys/class/net/<nic>/uevent
            self._channels = iw.chget(self._phy)
            self._standards = iwt.iwconfig(nic,'Standards') # iw
            self._txpwr = iwt.iwconfig(nic,'Tx-Power')
            self._driver = driver(nic)
            self._chipset = chipset(self._driver)
        except TypeError: raise RadioException("Unexpected error")
        except iwt.IWToolsException as e: raise RadioException(e)
        except iw.IWException as e:
            ecode = iw.ecode(e)
            if ecode == iw.IW_PERMISSION: raise RadioNoPermission(e)
            elif ecode == iw.IW_BUSY: raise RadioBusyDevice(e)
            elif ecode == iw.IW_NONIC: raise RadioNicNotFound(e)
            elif ecode == iw.IW_INVALIDARG: raise RadioInvalidArg(e)
            elif ecode == iw.IW_EXCEED: raise RadioExceedOpenFiles(e)
            elif ecode == iw.IW_OPERATION: raise RadioOpNotPermitted(e)
            else: raise RadioException(e)

        # create a spoofed address?
        if spoofed:
            mac = None if spoofed.lower() == 'random' else spoofed
            if mac: self.cloak(mac)

        # create in montior mode?
        if vnic: self.watch(vnic)