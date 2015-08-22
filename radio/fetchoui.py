#!/usr/bin/env python

""" fetchoui.py: oui/manuf related functions

Retrieves the http://standards-oui.ieee.org/oui.txt oui file and parses for
later use
"""

#__name__ = 'fetchoui'
__license__ = 'GPL v3.0'
__version__ = '0.0.1'
__date__ = 'January 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import urllib2 as url
import os
import re
import wraith

if __name__ == '__main__':
    req = url.Request('http://standards-oui.ieee.org/oui.txt')
    req.add_header('User-Agent',
                   "wraith-rt/%s +https://github.com/wraith-wireless/wraith/" % wraith.__version__)
    fout = None
    pattern = r'^([-|\w]*)   \(hex\)\t\t(.*)\r'
    try:
        # retrieve the oui file and parse out gen date
        res = url.urlopen(req)
        ls = res.readlines()
        gen = ls[0].strip().split('Generated: ')[1]

        # open oui file
        dpath = os.path.abspath('../data/oui.txt')
        fout = open(dpath,'w')
        fout.write(gen+'\n')

        # pull out ouis
        cnt = 0
        for l in ls[7:]:
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
        print "Wrote %d ouis generated %s" % (cnt,gen)
    except url.URLError as e:
        print "Error fetching oui file: %s" % e
    except IOError as e:
        print "Error opening output file :%s" % e
    except Exception as e:
        print "Error parsing oui file: %s" % e
    finally:
        if fout: fout.close()