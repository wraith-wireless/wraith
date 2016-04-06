#!/usr/bin/env python

""" utils: utility functions

Module for utility functionality

REVISIONS:
 0.0.2
  desc:
  includes: cmdline 0.0.2 landnav 0.3.2 simplepcap 0.0.1 timestamps 0.0.2 valrep 0.0.1
  changes:
"""
__name__ = 'utils'
__license__ = 'GPL v3.0'
__version__ = '0.0.2'
__date__ = 'February 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Production'

# intersection of two lists
def intersection(l1,l2): return filter(lambda x:x in l1,l2)
