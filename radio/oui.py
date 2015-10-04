#!/usr/bin/env python

""" oui.py: oui/manuf related functions
"""

__name__ = 'oui'
__license__ = 'GPL v3.0'
__version__ = '0.0.3'
__date__ = 'September 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import urllib2
import os
import re
import sys
import time
from wraith import OUI, __version__ as v
from wraith.utils.timestamps import ts2iso

def parseoui(path = None):
    """ parse oui.txt file at path filling in oui dict oui->manuf """
    fin = None
    ouis = {}

    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            os.path.abspath('../'+OUI))

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

def fetch():
    """retrieves oui.txt from IEEE and write to data file """
    ouiurl = 'http://standards-oui.ieee.org/oui.txt'
    ouipath = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           os.path.abspath('../'+OUI))
    if not os.path.isdir(os.path.dirname(ouipath)):
        print 'Path to data is incorrect %s' % ouipath
        sys.exit(1)

    # fetch oui file from ieee
    fout = None
    pattern = r'^([-|\w]*)   \(hex\)\t\t(.*)\r'
    req = urllib2.Request(ouiurl)
    req.add_header('User-Agent',"wraith-rt/%s +https://github.com/wraith-wireless/wraith/" % v)
    try:
        # retrieve the oui file and parse out generated date
        print 'Fetching ', ouiurl
        res = urllib2.urlopen(req)
        print "Parsing OUI file"

        gen = ts2iso(time.time())
        # open oui file
        fout = open(ouipath,'w')
        fout.write(gen+'\n')

        # pull out ouis
        t = time.time()
        cnt = 0
        for l in res.readlines():
            if '(hex)' in l:
                # extract oui and manufacturer
                oui,manuf = l.split('(hex)')
                oui = oui.strip().replace('-',':')
                manuf = manuf.strip()
                if manuf.startswith("IEEE REGISTRATION AUTHORITY"):
                    manuf = "IEEE REGISTRATION AUTHORITY"

                # write to file & update count
                fout.write('%s\t%s\n' % (oui,manuf))
                cnt += 1
        t1 = time.time()
        print "Wrote %d OUIs in %.3f secs" % (cnt,t1-t)
    except urllib2.URLError as e:
        print "Error fetching oui file: %s" % e
    except IOError as e:
        print "Error opening output file :%s" % e
    #except Exception as e:
    #    print "Error parsing oui file: %s" % e
    finally:
        if fout: fout.close()

if __name__ == '__main__': fetch()