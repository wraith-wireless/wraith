#!/usr/bin/env python

""" radio: 802.11 network interface objects and functions

Objects/functions to manipulate wireless nics and parse 802.11 captures.
Partial support of 802.11-2012
Currently Supported
802.11a\b\g

Partially Supported
802.11n

Not Supported
802.11s\y\ac\ad\af

REVISIONS:
radio 0.0.4
 desc: provides tools to manipulate wireless nics and parse raw wireless traffic
 includes: bits 0.0.4 channels 0.0.1, mcs 0.0.1, iw 0.1.0 iwtools 0.0.11,
 radiotap 0.0.4, mpdu 0.0.13, infoelement 0.0.1, oui 0.0.1
 changes:
  - adding support for iw 3.15+
    o no longer supporting versions less than 15
  - supports toplevel parsing of all frames (excluding control wrapper)

TODO:
 1) Should we add support for AVS, Prism headers ?
 2) radiotap: ensure data pad is handled
 3) mpdu: fully parse
    o control wrapper
    o fully parse qos
    o +htc
 4) look into parsing
   0 RSN Std 8.4.2.27
   o 802.11u
"""
__name__ = 'radio'
__license__ = 'GPL'
__version__ = '0.0.4'
__date__ = 'November 2014'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@hushmail.com'
__status__ = 'Development'