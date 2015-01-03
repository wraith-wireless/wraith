#!/usr/bin/env python
""" wraith
Wireless assault, reconnaissance, collection and exploitation toolkit.

Requires:
 Python 2.7
 iw 3.17
 mgrs 1.1

wraith package hierarchy
wraith/                Top-level package
    __init__.py          this file - initialize the top-level (includes misc functions)
    wraith-rt.py         the gui
    LICENSE              software license
    README.txt           configuration/setup details
    widgets              gui subpackage
        icons            icons folder
        __init__.py      initialize widgets subpackage
        panel.py         defines Panel and subclasses for gui
    radio                subpackage for radio/radiotap
        __init__.py      initialize radio subpackage
        bits.py          bitmask related funcs, bit extraction functions
        iwtools.py       iwconfig, ifconfig interface and nic utilities
        iw.py            iw 3.17 interface
        radiotap.py      radiotap frames parsing
        mpdu.py          IEEE 802.11 MAC (MPDU) frames parsing
        infoelement.py   contstants for mgmt frames
        channels.py      802.11 channel, freq utilities
        mcs.py           mcs index functions
    suckt                subpackage for wraith sensor
        __init__.py      initialize suckt package
        suckt.conf       configuration file for wasp
        suckt.log.conf   configuration file for wasp logging
        suckt.py         primary module
        rdoctl.py        radio controler with tuner, sniffer
        collate.py       data collation and forwarding
        sucktd           sucktd daemon
    nidus                subpackage for datamanager
        __init__.py      initialize nidus package
        nidus.conf       nidus configuration
        nidus.log.conf   nidus logging configuration
        nidus.py         nidus server
        nidusd           nidus daemon
        nmp.py           nidus protocol definition
        nidusdb.py       interface to storage system
        simplepcap.py    pcap writer
        nidus.sql        sql table definition

TODO:
      2) look into dis package
"""
__name__ = 'wraith'
__license__ = 'GPL'
__version__ = '0.0.2'
__date__ = 'December 2014'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@hushmail.com'
__status__ = 'Development'
import datetime as dt
from dateutil import parser as dtparser

# intersection of two lists
def intersection(l1,l2): return filter(lambda x:x in l1,l2)

# convert unix timestamp to utc in isoformat
def ts2iso(ts): return dt.datetime.utcfromtimestamp(ts).isoformat()

# convert isoformat to unix timestamp
def iso2ts(iso): return (dtparser.parse(iso)-dt.datetime.utcfromtimestamp(0)).total_seconds()
