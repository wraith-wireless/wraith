#!/usr/bin/env python

""" brine: support for pickling/unpickling connection objects

This was added to send connection objects from the Collator to Threshers but
without being able to pickle Locks, is not helpful at this point

see http://stackoverflow.com/questions/1446004/python-2-6-send-connection-object-over-queue-pipe-etc
"""

__name__ = 'brine'
__license__ = 'GPL v3.0'
__version__ = '0.0.1'
__date__ = 'October 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Production'

from multiprocessing import reduction
import pickle

class BrineException(Exception): pass

def pack(conn):
    """ pickle conn for transport over connection """
    try:
        return pickle.dumps(reduction.reduce_connection(conn))
    except Exception as e:
        raise BrineException(e)

def unpack(pickled):
    """ unpacks the pickled connection """
    try:
        p = pickle.loads(pickled)
        return p[0](p[1][0],p[1][1],p[1][2])
    except Exception as e:
        raise BrineException(e)