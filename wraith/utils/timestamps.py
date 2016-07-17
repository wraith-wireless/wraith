#!/usr/bin/env python
""" timestamps: timestamp conversion functions """

__name__ = 'timestamps'
__license__ = 'GPL v3.0'
__version__ = '0.0.2'
__date__ = 'February 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Production'

import datetime as dt
from time import time
from dateutil import parser as dtparser

# returns an iso formated utc timestamp
def isots(): return dt.datetime.utcfromtimestamp(time()).isoformat()

# convert unix timestamp to utc in isoformat
def ts2iso(ts): return dt.datetime.utcfromtimestamp(ts).isoformat()

# convert isoformat to unix timestamp
def iso2ts(iso): return (dtparser.parse(iso)-dt.datetime.utcfromtimestamp(0)).total_seconds()

def validdate(s): # confirm string s is of the form YYYY-MM-DD and is a valid date
    try:
        dt.datetime.strptime(s,'%Y-%m-%d')
        return True
    except:
        return False

def validtime(s): # confirm string s is a valid time of the form HH:MM[:SS]
    try:
        dt.datetime.strptime(s,'%H:%M:%S')
        return True
    except:
        return False
