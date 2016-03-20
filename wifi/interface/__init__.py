#!/usr/bin/env python

""" interface: 802.11 wireless network interface functionality

Objects/functions to manipulate and query wireless nics

REVISIONS:
interface 0.0.2
 desc: provides tools to manipulate wireless nics 
 includes: radio 0.0.3 iw 0.1.0 oui 0.0.4
 changes:
  - added Radio class to consolidate iw.py and iwtools.py
  - added sockios_h for sock ioctl constants
   o added two iwconfig related constants
  - added nl80211_h for nl80211 constants
  - added if_h for inet definitions
  - removed iwtools and all dependence on iwtools (parsing output from
    ifconfig/iwconfig)
    o implements getting/setting hwaddr, getting ifindex, getting flags, getting
     txpower, getting standards and listing nics & wireless nics using ioctl
  - added random hw addr generator to oui.py
"""
__name__ = 'interface'
__license__ = 'GPL v3.0'
__version__ = '0.0.2'
__date__ = 'February 2016'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'
