#!/usr/bin/env python

""" oui.py: oui/manuf related functions

Parse the 802.11 MAC Protocol Data Unit (MPDU) IAW IEEE 802.11-2012
"""

__name__ = 'oui'
__license__ = 'GPL v3.0'
__version__ = '0.0.2'
__date__ = 'January 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

def parseoui(path):
    """ parse oui.txt file at path filling in oui dict oui->manuf """
    fin = None
    ouis = {}

    try:
        fin = open(path)
        for line in fin.readlines()[1:]:
            oui,manuf = line.strip().split('\t')
            ouis[oui.lower()] = manuf[0:100]
        fin.close()
    except IOError:
        if fin and not fin.closed: fin.close()
    return ouis

def manufacturer(oui,mac):
    """ returns the manufacturer of the mac address if exists, otherwise 'unknown' """
    try:
        return oui[mac[:8]]
    except KeyError:
        return "unknown"
