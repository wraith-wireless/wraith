#!/usr/bin/env python

""" bits: bit related functions

defines
 o bitmask related functions operating on bitmasks defined as dicts of the form
 name->mask where name (string) is represented by mask (integer) i.e
 {'flag1':(1 << 0),...,'flag2':(1 << 4)} or {'flag1':1,...,'flag2':16}
 o bit extraction functions on same
 o set/unset numeric flags defined by constants
"""

__name__ = 'bits'
__license__ = 'GPL v3.0'
__version__ = '0.0.5'
__date__ = 'November 2014'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Production'

def issetf(flags,flag):
    """
     determines if flag is set
    :param flags: current flag value
    :param flag: flag to check
    :return: True if flag is set
    """
    return (flags & flag) == flag

def setf(flags,flag):
    """
     sets flag, adding to flags
    :param flags: current flag value
    :param flag: flag to set
    :return: new flag value
    """
    return flags | flag

def unsetf(flags,flag):
    """
     unsets flag, adding to flags
    :param flags: current flag value
    :param flag: flag to unset
    :return: new flag value
    """
    return flags & ~flag

def bitmask(bm,mn):
    """
     returns a list of names defined in bitmask bm that are present in mn

     :param bm: bitmask
     :param mn: magic number
     :returns: defined names
    """
    if mn == 0: return []
    return [name for name,mask in bm.items() if mn & mask == mask]

def bitmask_list(bm,mn):
    """
     returns a dict d = {name:is_set} for each name in bm and value in mn

     :param bm: bitmask
     :param mn: magic number
     :returns: dict d = {name:is_set}
    """
    d = {}
    for name in bm: d[name] = int(bm[name] & mn == bm[name])
    return d

def bitmask_get(bm,mn,f):
    """
     returns True if flag f in bitmask bm is set in magic number mn
     throws KeyError if f is not defined in bitmask

     :param bm: bitmask
     :param mn: magic number
     :param f: flag to retrieve
     :returns: defined names
    """
    return int(bm[f] & mn == bm[f])

def bitmask_set(bm,mn,f):
    """
     sets the flag f in mn as defined by the bitmask bm to True (or 1)
     throws KeyError if f is not defined

     :param bm: bitmask
     :param mn: magic number
     :param f: flag
    """
    return mn | bm[f]

def bitmask_unset(bm,mn,f):
    """
     unsets the flag f as defined in the bitmask bm to False (or 0)
     throws KeyError if f is not defined

     :param bm: bitmask
     :param mn: magic number
     :param f: flag
    """
    return mn & ~bm[f]

def leastx(x,v):
    """
     :param x: x number of bits
     :param v: value
     :returns: the (unsigned int) value of the x least most significant bits in v
    """
    return v & ((1 << x) - 1)

def midx(s,x,v):
    """
     :param s: start bit
     :param x: x number of bits
     :param v: value
     :returns: the (unsigned int) value of x bits starting at s from v
    """
    return leastx(x,(v >> s))

def mostx(s,v):
    """
     :param s: start bit
     :param v: value
     :returns: the (unsigned int) value of the most significant bits in v
      starting at s
    """
    return v >> s

"""
def mask(a,b):
    r = 0
    for i in range(a,b+1): r |= 1 << i
    return r
mask(2,2) & n
have to shift over after this
"""