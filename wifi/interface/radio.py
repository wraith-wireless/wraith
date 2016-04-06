#!/usr/bin/env python

""" radio.py: network interface card

Provides the Radio class, a network interface card, which consolidates network
card manipulation and attribute functionality into a single object. Also
provides several standalone functions w.r.t regulatory domain and system

At present, is a wrapper around iw.py functions which use iw and iwlist but
is now implemeting all iwconfig and ifconfig functionality through ioctl

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
__version__ = '0.0.3'
__date__ = 'February 2016'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import os                                               # filesystem
from fcntl import ioctl                                 # io control
import socket                                           # kernel comms
import struct                                           # c struct conversion
from toolbox.bits import issetf,setf,unsetf             # flag manipulation
from wraith.wifi.interface import iw                    # iw cmdline parsing
from wraith.wifi.interface.net import sockios_h as sioc # sockios constants
from wraith.wifi.interface.net import if_h as ifh       # ifreq creation

# widths currently supported
RDO_CHWS = [None,'HT20','HT40+','HT40-']

# Exception
# Defined error codes
RDO_UNDEFINED     = -1
RDO_UNINITIALIZED =  0
RDO_PERMISSION    =  1 # this and below are codes from IOError
RDO_BUSY          = 16
RDO_NONIC         = 19
RDO_INVALIDARG    = 22
RDO_EXCEED        = 23
RDO_BADIOCTL      = 25
RDO_OPERATION     = 95

class RadioException(Exception): pass # tuple t = (errcode,errmessage)

def interfaces():
    """ :returns: a list of names of current network interfaces cards """
    # read in devices from /proc/net/dev. After splitting on newlines, the first
    # 2 lines are headers and the last line is empty so we remove them
    try:
        fin = open('/proc/net/dev','r')
        ns = fin.read().split('\n')[2:-1]
        fin.close()
    except Exception as e:
        raise RadioException((RDO_UNDEFINED,e))

    # the remaining lines are <nicname>: p1 p2 ... p3, split on ':' & strip whitespace
    nics = []
    for nic in ns: nics.append(nic.split(':')[0].strip())
    return nics

def winterfaces():
    """ :returns: a list of names of current wireless network interfaces cards """
    # tried reading in devices from /proc/net/wireless but it did not always
    # include my usb interfaces. look at SIOCGIWNAME (what header is it found in)
    wics = []
    s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    for nic in interfaces():
        try:
            # send SIOCGIWNAME (from wireless.h) = 0x8B01, a non-wireless card
            # will result in an IOError 'Operation not supported' but we
            # take any error to mean non-wireless
            _ = ioctl(s.fileno(),sioc.SIOCGIWNAME,ifh.ifreq(nic))
            wics.append(nic)
        except:
            pass
    s.close()
    return wics

def setrd(rd):
    """
     set the regulatory domain
     :param rd: desired two-character domain
    """
    try:
        iw.regset(rd)
    except iw.IWException as e:
        raise RadioException((RDO_UNDEFINED,e))

def getrd():
    """ return the current regulatory domain """
    try:
        return iw.regget()
    except iw.IWException as e:
        raise RadioException((RDO_UNDEFINED,e))

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
          3) watch
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

        # these attributes are mutable but we use them to as semi-immutable
        # NOTE: the Radio will be identified by either the nic, meaning it is
        # not yet initialized or vnic meaning it is in monitor mode
        # name for calls to iw/iwtools
        self._nic = None
        self._nicmode = None
        self._vnic = None
        if nic: self._setup(nic,vnic,spoof)

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
    def isup(self): return issetf(self._ifflags(),ifh.IFF_UP)

    @property # :returns: interface index
    def ifindex(self):  return self._ifindex

    @property # :returns: the nic name (if any)
    def nic(self): return self._nic

    @property # :returns: the nic name (if any)
    def vnic(self): return self._vnic

    @property
    def ifaces(self):
        """
         current interfaces belonging to this Radio
         :returns: all (current) interfaces on this Radio
          as a list of dicts
        """
        if not self._phy: raise RadioException((RDO_UNINITIALIZED,"Uninitialized"))
        try:
            return iw.dev()[self._phy]
        except iw.IWException as e:
            raise RadioException((iw.ecode(e),e))
        except KeyError:
            raise RadioException((RDO_NONIC,"No such device (-19)"))

    @property
    def channel(self):
        """
         :returns: the channel # Radio is currently on or None
         NOTE: this will only work if Radio is associated with an AP - will
         not work if Radio is in monitor mode
        """
        nic = self._vnic if self._vnic else self._nic
        if nic is None: raise RadioException((RDO_UNINITIALIZED,"Uninitialized"))
        try:
            return iw.curchget(nic)
        except iw.IWException as e:
            raise RadioException((iw.ecode(e),e))

    @property
    def channels(self):
        """ :returns: list of all supported channels of this Radio """
        if not self._channels: raise RadioException((RDO_UNINITIALIZED,"Uninitialized"))
        return self._channels

    @property
    def standards(self):
        """ :returns: supported standards i.e. 'a', 'b' etc """
        if not self._standards: raise RadioException((RDO_UNINITIALIZED,"RUninitialized"))
        return self._standards

    @property
    def hwaddr(self):
        """ :returns: actual hardware address """
        nic = self._vnic if self._vnic else self._nic
        if nic is None: raise RadioException((RDO_UNINITIALIZED,"Uninitialized"))
        return self._hwaddr

    @property
    def spoofed(self):
        """:returns: spoofed hardware address """
        nic = self._vnic if self._vnic else self._nic
        if nic is None: raise RadioException((RDO_UNINITIALIZED,"Uninitialized"))
        return self._spoofed

    @property
    def mode(self):
        """ :returns the mode of this Radio """
        # does not work
        nic = self._vnic if self._vnic else self._nic
        if nic is None: raise RadioException((RDO_UNINITIALIZED,"Uninitialized"))
        try:
            _,ifaces = iw.dev(nic)
            for iface in ifaces:
                if iface['nic'] == nic: return iface['type']
            return None
        except iw.IWException as e:
            raise RadioException((iw.ecode(e),e))

    @property
    def txpwr(self):
        """ :returns: current transmit power (in dBm) """
        if not (self._nic or self._vnic):
            raise RadioException((RDO_UNINITIALIZED,"Uninitialized"))
        return self._iwtxpwr()

    @property
    def driver(self):
        """ :returns: driver for this Radio """
        nic = self._vnic if self._vnic else self._nic
        if nic is None: RadioException((RDO_UNINITIALIZED,"Uninitialized"))
        return self._driver

    @property
    def chipset(self):
        """:returns: chipset for this Radio """
        nic = self._vnic if self._vnic else self._nic
        if nic is None: raise RadioException((RDO_UNINITIALIZED,"Uninitialized"))
        return self._chipset

#### methods

    def up(self):
        """ turns Radio on """
        flags = self._ifflags()
        if issetf(self._ifflags(),ifh.IFF_UP): return
        self._ifflags(setf(flags,ifh.IFF_UP))

    def down(self):
        """ turns Radio off """
        flags = self._ifflags()
        if not issetf(self._ifflags(),ifh.IFF_UP): return
        self._ifflags(unsetf(flags,ifh.IFF_UP))

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
            raise RadioException((iw.ecode(e),e))

    def unwatch(self):
        """
         removes the virtual interface this Radio (and adds the original nic
         back to it's orginal state)
         NOTE: this does not restore all interfaces that were deleted by watch
        """
        if not self._vnic:
            raise RadioException((RDO_OPERATION,"Radio is not in monitor mode"))
        try:
            iw.devdel(self._vnic)
            self._vnic = None
            iw.phyadd(self._phy,self._nic,self._nicmode)
            self.up()
        except iw.IWException as e:
            raise RadioException((iw.ecode(e),e))

    def spoof(self,hwaddr):
        """
         sets spoofed hw address
         :param hwaddr: 48 bit hex mac address of form XX:XX:XX:XX:XX:XX
        """
        if hwaddr.lower() == 'random':
            raise RadioException((RDO_UNDEFINED,'Random spoof not implemented'))
        nic = self._vnic if self._vnic else self._nic
        if nic is None: raise RadioException((RDO_UNINITIALIZED,"Uninitialized"))
        self.down()
        newmac = self._ifhwaddr(hwaddr)
        self.up()
        if newmac == hwaddr: self._spoofed = newmac

    def unspoof(self):
        """ resets hw address """
        nic = self._vnic if self._vnic else self._nic
        if nic is None: raise RadioException((RDO_UNINITIALIZED,"Uninitialized"))
        self.down()
        oldmac = self._ifhwaddr(self.hwaddr)
        self.up()
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
            raise RadioException((iw.ecode(e),e))

    def setch(self,ch,chw=None):
        """
         sets channel
         :param ch: channel (number) to set card to
         :param chw: channel width to set to default is None
        """
        if not self._phy: raise RadioException((RDO_UNINITIALIZED,"Uninitialized"))
        if not chw in RDO_CHWS:
            raise RadioException((RDO_INVALIDARG,"Channel width is invalid (22)"))

        try:
            iw.chset(self._phy,ch,chw)
        except iw.IWException as e:
            raise RadioException((iw.ecode(e),e))

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
            self._hwaddr = self._ifhwaddr()
            self._ifindex = self._ififindex() # see also /sys/class/net/<nic>/ifindex
            self._channels = iw.chget(self._phy)
            self._standards = self._iwname()[1]
            self._driver = self._ifdriver()
            self._chipset = self._ifchipset()
        except TypeError: raise RadioException((RDO_UNDEFINED,"Unexpected error"))
        except RadioException: raise
        except iw.IWException as e:
            raise RadioException((iw.ecode(e),e))
        if spoof: self.spoof(spoof) # create a spoofed address?
        if vnic: self.watch(vnic)   # create in montor mode?

#### IOCTL ifconfig/iwconfig implementation

    def _ifhwaddr(self,mac=None):
        """
         get/sets this Radio's hwaddr. Setting and getting are the same operation,
         the only difference is in the sockios flag sent to the kernel
         :param mac: hwaddr to set to. If None, the current address is retrieved
         :returns: the hw addr of this Radio
        """
        # are we initialized?
        nic = self._vnic if self._vnic else self._nic
        if nic is None: raise RadioException((RDO_UNDEFINED,"Unexpected error"))

        # are setting or getting
        if mac is None:
            sflag = sioc.SIOCGIFHWADDR
            ps = []
        else:
            sflag = sioc.SIOCSIFHWADDR
            ps = [ifh.ARPHRD_ETHER,mac]

        try:
            s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            ret = ioctl(s.fileno(),sflag,ifh.ifreq(nic,sflag,ps))

            # make sure we got an ethernet address
            fam = struct.unpack_from(ifh.sa_addr,ret,ifh.IFNAMELEN)[0]
            if fam == ifh.ARPHRD_ETHER:
                # TODO: any other way then indexing the returned value
                return ":".join(['{0:02x}'.format(ord(c)) for c in ret[18:24]])
            raise RadioException((RDO_UNDEFINED,"invalid sa_family = {0}".format(fam)))
        except RadioException: raise # reraise the above
        except AttributeError as e:
            # ifh error
            raise RadioException((RDO_INVALIDARG,e))
        except IOError as e:
            raise RadioException((e.errno,e))
        except Exception as e:
            raise RadioException((RDO_UNDEFINED,e))
        finally:
            s.close()

    def _ififindex(self):
        """ :returns: the hw addr of this Radio """
        nic = self._vnic if self._vnic else self._nic
        if nic is None: raise RadioException((RDO_UNINITIALIZED,"Uninitialized"))

        try:
            sflag = sioc.SIOCGIFINDEX
            s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            ifreq = ifh.ifreq(nic,sflag)
            ret = ioctl(s.fileno(),sflag,ifreq)
            return struct.unpack_from(ifh.ifr_ifindex,ret,ifh.IFNAMELEN)[0]
        except AttributeError as e:
            # ifh error
            raise RadioException((RDO_INVALIDARG,e))
        except IOError as e:
            raise RadioException((e.errno,e))
        except struct.error as e:
            raise RadioException((RDO_UNDEFINED,"Failed to pack/unpack {0}".format(e)))
        except Exception as e:
            raise RadioException((RDO_UNDEFINED,e))
        finally:
            s.close()

    def _ifflags(self,flags=None):
        """
         get/sets this Radio's flags. Setting and getting are the same operation,
         the only difference is in the sockios flag sent to the kernel
         :param flags: flags to set to. If None, the current flags are retrieved
         :returns: the current flags
        """
        # are we initialized?
        nic = self._vnic if self._vnic else self._nic
        if nic is None: raise RadioException((RDO_UNINITIALIZED,"Uninitialized"))

        # are setting or getting
        sflag = sioc.SIOCGIFFLAGS if flags is None else sioc.SIOCSIFFLAGS
        flags = [flags] if flags else None

        try:
            s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            ret = ioctl(s.fileno(),sflag,ifh.ifreq(nic,sflag,flags))
            return struct.unpack_from(ifh.ifr_flags,ret,ifh.IFNAMELEN)[0]
        except AttributeError as e:
            raise RadioException((RDO_INVALIDARG,e))
        except IOError as e:
            raise RadioException((e.errno,e))
        except struct.error as e:
            raise RadioException((RDO_UNDEFINED,"Failed to pack/unpack {0}".format(e)))
        except Exception as e:
            raise RadioException((RDO_UNDEFINED,e))
        finally:
            s.close()

    def _iwname(self):
        """
        confirms a device by name exists and is wireless and returns the
        standards for name if present/wireless
        :returns: tuple t = (name,standards)
        """
        # are we initialized?
        nic = self._vnic if self._vnic else self._nic
        if nic is None: raise RadioException((RDO_UNINITIALIZED,"Uninitialized"))

        try:
            sflag = sioc.SIOCGIWNAME
            s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)

            # the below is a dirty hack until we can figure another
            # way to get standards
            ret = ioctl(s.fileno(),sflag,ifh.ifreq(nic,sflag))
            name = ret[:ifh.IFNAMELEN]      # get the name
            name = name[:name.find('\x00')] # remove nulls
            stds = ret[ifh.IFNAMELEN:]      # get the standards
            stds = stds[:stds.find('\x00')] # remove nulls
            stds = stds.replace('IEEE','')  # remove IEEE if present
            return name,stds
        except AttributeError as e:
            raise RadioException((RDO_INVALIDARG,e))
        except IOError as e:
            raise RadioException((e.errno,e))
        except struct.error as e:
            raise RadioException((RDO_UNDEFINED,"Failed to pack/unpack {0}".format(e)))
        except Exception as e:
            raise RadioException((RDO_UNDEFINED,e))
        finally:
            s.close()

    def _iwtxpwr(self):
        """
        gets current tx power of this Radio
        :returns: the tx power
        """
        # are we initialized?
        nic = self._vnic if self._vnic else self._nic
        if nic is None: raise RadioException((RDO_UNINITIALIZED,"Uninitialized"))

        try:
            # we ignore fixed, disabled and flags (for now)
            sflag = sioc.SIOCGIWTXPOW
            s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            ret = ioctl(s.fileno(),sflag,ifh.ifreq(nic,sflag))
            return struct.unpack_from(ifh.ifr_iwtxpwr,ret,ifh.IFNAMELEN)[0]
        except AttributeError as e:
            raise RadioException((RDO_INVALIDARG,e))
        except IOError as e:
            raise RadioException((e.errno,e))
        except struct.error as e:
            raise RadioException((RDO_UNDEFINED,"Failed to pack/unpack {0}".format(e)))
        except Exception as e:
            raise RadioException((RDO_UNDEFINED,e))
        finally:
            s.close()

#### MISC

    def _ifdriver(self):
        """ :returns: driver (or unknown if cannot be found) """
        path = '/sys/class/net/{0}/device/driver/module/drivers'.format(self._nic)
        try:
            # find the driver for nic in driver's module, split on ':' and return
            ds = os.listdir(path)
            if len(ds) > 1: return "Unknown"
            return ds[0].split(':')[1]
        except OSError:
            return "Unknown"

    def _ifchipset(self):
        """
        returns the chipset for given driver (Thanks aircrack-ng team)
        NOTE: does not fully implement the airmon-ng getChipset where identification
        requires system commands
        :returns: chipset of driver
        """
        driver = self._driver
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
