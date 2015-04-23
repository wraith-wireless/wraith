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
from dateutil import parser as dtparser

# convert unix timestamp to utc in isoformat
def ts2iso(ts): return dt.datetime.utcfromtimestamp(ts).isoformat()

# convert isoformat to unix timestamp
def iso2ts(iso): return (dtparser.parse(iso)-dt.datetime.utcfromtimestamp(0)).total_seconds()

# confirm string s is of the form YYYY-MM-DD and is a valid date
def validdate(s):
    try:
        dt.datetime.strptime(s,'%Y-%m-%d')
        return True
    except:
        return False

# confirm string s is of the form HH:MM[:SS] and is a valid time
def validtime(s):
    try:
        dt.datetime.strptime(s,'%H:%M:%S')
        return True
    except:
        return False