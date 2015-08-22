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
import wraith

if __name__ == '__main__':
    req = url.Request('http://standards-oui.ieee.org/oui.txt')
    req.add_header('User-Agent',
                   "wraith-rt/%s +https://github.com/wraith-wireless/wraith/" % wraith.__version__)
    try:
        res = url.urlopen(req)
        ouis = res.readlines()
        #print os[0:7]
        gen = ouis[0].strip().split('Generated: ')[1]
        #print gen

        dpath = os.path.dirname(os.path.abspath(__file__))
        dpath = os.path.join(dpath,'../data/oui.txt')
        print dpath
    except url.URLError as e:
        print "Error fetching oui file: %s" % e
    except Exception as e:
        print "Error parsing oui file: %s" % e