#!/usr/bin/env python

""" valrep: validation and reporting functions

"""
__name__ = 'valrep'
__license__ = 'GPL v3.0'
__version__ = '0.0.1'
__date__ = 'December 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Production'

import re                           # reg exp matching
from socket import gethostbyname    # hostname resolution
from wraith.wifi import iw,channels # channel list specification
import sys,traceback                # traceback/error reporting

# validation expressions
IPADDR = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$") # re for ip addr
MACADDR = re.compile("^([0-9A-F]{2}:){5}([0-9A-F]{2})$")    # re for mac addr (capital letters only)
GPSDID = re.compile("^[0-9A-F]{4}:[0-9A-F]{4}$")            # re for gps device id (capital letters only)

def validaddr(addr):
    """
     determines validity of address
     :param addr: address to check
     :returns: True if addr is valid ip, localhost or can be resolved as a hostname,
     False otherwise
    """
    if addr.lower() == 'localhost': return True
    if validip(addr): return True
    try:
       gethostbyname(addr) # assumes connected interface
       return True
    except:
        return False

def validip(addr):
    """
     determines validity of ip address
     :param addr: ip addr to check
     :returns: True if addr is valid ip, False otherwise
    """
    if re.match(IPADDR,addr): return True
    return False

def validgpsdid(gid):
    """
     determines validity (having the form XXXX:XXXX where X is hexidecimal
     character) of gps device id
     :param gid:
     :returns: True if gid is valid device id, False otherwise
    """
    if re.match(GPSDID,gid.upper()): return True
    return False

def validhwaddr(addr):
    """
     determienes validity of hw addr
     :param addr: address to check
     :returns: True if addr is valid hw address, False otherwise
    """
    if re.match(MACADDR,addr): return True
    return False

def channellist(pattern,ptype='scan'):
    """
      parses a channel list pattern
      :param pattern: see below for channel list definition
      :param ptype: oneof {'scan'|'pass'}
      :returns: all channels as a list of tuples t = (channel,chwidth) specified
       in pattern

      Channel List definition:
        channel lists are defined by channels:widths
        where channels can be defined as:
         1. a single channel or empty for all NOTE: in the case of pass empty
            designates that no channels will be skipped
         2. list of ',' separated channels
         3. a range defined as lower-upper i.e 1-14
         4. a band preceded by a 'B' i.e. B2.4 or B5
        and widths can be defined as:
         HT, NONHT, ALL or empty
    """
    # parse channel portion
    if not pattern: chs,ws = [],[]
    else:
        chs,ws = pattern.split(':') # split the pattern by ch,width separator

        if not chs: chs = []
        else:
            if chs.lower().startswith('b'): # band specification
                band = chs[1:]
                if band == '2.4': chs = sorted(channels.ISM_24_C2F.keys())
                elif band == '5': chs = sorted(channels.UNII_5_C2F.keys())
                else:
                    err = "Band spec: %s for %s not supported".format(chs,ptype)
                    raise ValueError(err)
            elif '-' in chs: # range specification
                [l,u] = chs.split('-')
                chs = [c for c in xrange(int(l),int(u)+1) if c in channels.channels()]
            else: # list or single specification
                try:
                    chs = [int(c) for c in chs.split(',')]
                except ValueError:
                    err = "Invalid channel list spec: {0} for {1}".format(chs,ptype)
                    raise ValueError(err)

            # parse width portion
            if not ws or ws.lower() == 'all': ws = []
            else:
                if ws.lower() == "noht": ws = [None,'HT20']
                elif ws.lower() == "ht": ws = ['HT40+','HT40-']
                else:
                    err = "Invalid spec for width {0} for {1}".format(ws,ptype)
                    raise ValueError(err)

    # compile all possible combinations
    if (chs,ws) == ([],[]):
        if ptype == 'scan':
            return [(ch,chw) for chw in iw.IW_CHWS for ch in channels.channels()]
    elif not chs: return [(ch,chw) for chw in ws for ch in channels.channels()]
    elif not ws: return [(ch,chw) for chw in iw.IW_CHWS for ch in chs]
    else: return [(ch,chw) for chw in ws for ch in chs]

def tb():
    """
     ugly print traceback
     :returns: string representation of the traceback
    """
    return repr(traceback.format_tb(sys.exc_info()[2]))