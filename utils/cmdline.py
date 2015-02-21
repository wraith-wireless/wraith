#!/usr/bin/env python

""" cmdline: command line similar functions

defines
 bitmask related functions operating on bitmasks defined as dicts of the form
 name->mask where name (string) is represented by mask (integer) i.e
 {'flag1':(1 << 0),...,'flag2':(1 << 4)} or {'flag1':1,...,'flag2':16}
 bit extraction functions
"""

__name__ = 'cmdline'
__license__ = 'GPL v3.0'
__version__ = '0.0.1'
__date__ = 'February 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Production'