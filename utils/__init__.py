#!/usr/bin/env python

""" utils: holds utility functions """
__name__ = 'utils'
__license__ = 'GPL'
__version__ = '0.0.1'
__date__ = 'February 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@hushmail.com'
__status__ = 'Production'

# singular functions with nowhere else to go

# intersection of two lists
def intersection(l1,l2): return filter(lambda x:x in l1,l2)