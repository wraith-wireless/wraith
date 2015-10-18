#!/usr/bin/env python

""" constants.py: defines contstants used by iyri
"""
__name__ = 'constants'
__license__ = 'GPL v3.0'
__version__ = '0.0.1'
__date__ = 'August 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

from wraith.radio.mpdu import MAX_MPDU
import re

# define the m x n array size for the cirular buffer
M = 1000     # number of rows for memory view
N = MAX_MPDU # number of cols (bytes)

# number of (initial) threshers
NTHRESH = 2

# BULK WRITE NUMBER
NWRITE = 20

# iyri states
IYRI_INVALID         = -1 # iyri is unuseable
IYRI_CREATED         =  0 # iyri is created but not yet started
IYRI_RUNNING         =  1 # iyri is currently executing
IYRI_EXITING         =  5 # iyri has finished execution loop
IYRI_DESTROYED       =  6 # iyri is destroyed

# tuner states
TUNE_DESC = ['scan','hold','pause','listen']
TUNE_SCAN   = 0
TUNE_HOLD   = 1
TUNE_PAUSE  = 2
TUNE_LISTEN = 3

# validation expressions
IPADDR = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$") # re for ip addr
MACADDR = re.compile("^([0-9A-F]{2}:){5}([0-9A-F]{2})$")    # re for mac addr (capital letters only)
GPSDID = re.compile("^[0-9A-F]{4}:[0-9A-F]{4}$")            # re for gps device id (capital leters only)