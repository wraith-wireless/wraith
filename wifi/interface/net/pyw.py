#!/usr/bin/env python

""" pyw.py: python iw

Provides a pythonic subset of the iw command.
"""

__name__ = 'pyw'
__license__ = 'GPL v3.0'
__version__ = '0.0.1'
__date__ = 'March 2016'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import os
import time
import struct
import socket
import multiprocessing as mp
# get the below when trying
# import wraith.wifi.interface.net.genetlink_h as genl
#RuntimeWarning: Parent module 'genetlink_h' not found while handling absolute import
#  import struct
#
import netlink_h as nl
import genetlink_h as genl
import nl80211_h as nl80211

BUFSZ = 8192 # value from iw

class PYWError(Exception): pass
class PYW(object):
    """ defines an OO version of iw """
    def __init__(self,seq=None):
        """
         initializes PYW, instantiating netlink socket and getting the family
         id for nl80211
         :param seq: starting sequence number
        """
        self._s = None                             # our netlink socket
        self._l = mp.Lock()                        # lock for netlink socket
        self._fid = None                           # nl80211 family id
        self._pid = None                           # our port id
        self._gs = None                            # groups id
        self._seq = seq if seq and seq >= 1 else 1 # cmd seq #

        # create the socket
        try:
            self._s = socket.socket(socket.AF_NETLINK,socket.SOCK_RAW,nl.NETLINK_GENERIC)
            self._s.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,BUFSZ)  # value from iw
            self._s.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,BUFSZ)
            self._s.bind((os.getpid(),0))
            self._pid,self._gs = self._s.getsockname()
        except socket.error as e:
            raise PYWError("Failed to create netlink socket: {0}".format(e))

        # get the family id
        try:
            self._familyid()
        except (struct.error,socket.error) as e:
            self._s.close()
            raise PYWError("Failed to retrieve nl80211 family id: {0}".format(e))
        except Exception as e:
            self._s.close()
            raise PYWError("Unknown error: {0}".format(e))

    #def __del__(self):
    #    """ destructor """
    #    print 'pyw.__del__'
    #    try:
    #        self._s.close()
    #    except:
    #        pass

    def close(self):
        """ clean up """
        try:
            self._s.close()
        except:
            pass

#### PRIVATE HELPER FCTS

    def _familyid(self):
        """ gets the nl80211 family id """
        # TODO: don't hardcode unpack format for attributes
        """
         In addition to the family id, we get:
         CTRL_ATTR_FAMILY_NAME = nl80211\x00
         CTRL_ATTR_VERSION = \x01\x00\x00\x00 = 1
         CTRL_ATTR_HDRSIZE = \x00\x00\x00\x00
         CTRL_ATTR_MAXATTR = \xbf\x00\x00\x00 = 191
         CTRL_ATTR_OPS
         CTRL_ATTR_MCAST_GROUPS
        """
        try:
            nm = nla_put(nlstring(nl80211.NL80211_GENL_NAME),
                         genl.CTRL_ATTR_FAMILY_NAME)
            stream = nl_transfer(self._s,genl.GENL_ID_CTRL,genl.CTRL_CMD_GETFAMILY,
                                 self._pid,nl.NLM_F_REQUEST,attrs=[nm])
            attrs = nl_data(stream)
            self._fid = struct.unpack("H",attrs[genl.CTRL_ATTR_FAMILY_ID])[0]
        except NLError as e:
            raise PYWError(e)

#### LIBNL(ISH) FUNCTIONS
# NOTE: I have taken liberties with the below as these functions only handle
# nl80211 netlink messages

class NLError(Exception): pass

def nl_transfer(sock,fam,cmd,pid,seq=None,flags=None,attrs=None):
    """
     creates, sends and receives a netlink message
     :param sock: netlink socket
     :param fam: message content (nlmsghdr->nlmsg_type)
     :param cmd: generic netlink message type (genlmsghdr->cmd)
     :param seq: sequence number
     :param pid: port id
     :param flags: message flags
     :param attrs: list of preprocessed attributes to send
     :returns: the netlink data
    """
    # initialize params
    seq = seq or int(time.time())
    flags = flags or nl.NLM_F_REQUEST
    attrs = attrs or []

    # send the message
    sock.send(nlmsg(fam,cmd,seq,pid,flags,attrs))
    msg = sock.recv(BUFSZ)

    # parse netlink/generic netlink headers and return attribute stream
    offset = nl.NLMSGHDRLEN
    l,t,f,s,p = struct.unpack_from(nl.nl_nlmsghdr,msg,0)
    if t == nl.NLMSG_ERROR: raise NLError("{0".format(nle_parse(msg)))
    if s != seq: raise NLError("Seq # out of order")
    if l != len(msg): raise NLError("Received {0} != actual {1}".format(l,len(msg)))
    c,_,_ = struct.unpack_from(genl.genl_genlmsghdr,msg,offset)
    offset += genl.GENLMSGHDRLEN

    return msg[offset:]

"""
generic netlink data exchanged between user and kernel space is a netlink message
of type NETLINK_GENERIC using the netlink attributes interface. Messages are in
the format:

  <------- NLMSG_ALIGN(hlen) ------> <---- NLMSG_ALIGN(len) --->
 +----------------------------+- - -+- - - - - - - - - - -+- - -+
 |           Header           | Pad |       Payload       | Pad |
 |      struct nlmsghdr       |     |                     |     |
 +----------------------------+- - -+- - - - - - - - - - -+- - -+

  <-------- GENL_HDRLEN -------> <--- hdrlen -->
                                 <------- genlmsg_len(ghdr) ------>
 +------------------------+- - -+---------------+- - -+------------+
 | Generic Netlink Header | Pad | Family Header | Pad | Attributes |
 |    struct genlmsghdr   |     |               |     |            |
 +------------------------+- - -+---------------+- - -+------------+

netlink messages are aligned on boundaries of 4
"""

def nlmsg(fam,cmd,seq,pid,flags=nl.NLM_F_REQUEST,attrs=None):
    """
     create netlink message
     :param fam: message content (nlmsghdr->nlmsg_type)
     :param cmd: generic netlink message type (genlmsghdr->cmd)
     :param seq: sequence number
     :param pid: port id
     :param flags: message flags
     :param attrs: list of preprocessed attributes to send
    """
    attrs = attrs or []

    # have to align each section on four bytes
    payload = genl.genlmsghdr(cmd)            # together nlmsghdr and genlmsghdr
    idx = nl.NLMSGHDRLEN + genl.GENLMSGHDRLEN # will end at a boundary of 4
    for attr in attrs:
        pad = nl.NLMSG_ALIGNBY(idx+len(attr))
        payload += attr + nlpad(pad)
        idx += pad
    return nl.nlmsghdr(len(payload),fam,flags,seq,pid) + payload

def nla_put(attr,atype):
    """
     create a netlink attribute w/ value
     :param attr: pre-packed attribute
     :param atype: the type of attribute
     :returns: a netlink attribute structure appended by the attribute
    """
    return nl.nlattr(len(attr),atype) + attr

def nlstring(s):
    """
     :param s: string
     :returns: a null terminated netlink string
    """
    return struct.pack("{0}sB".format(len(s)),s,0)

def nlpad(b):
    """
     :param b: # bytes to pad
     :returns: padded bytes of length b
    """
    return struct.pack("{0}x".format(b))

def nl_data(stream):
    """
     parses attribute stream
     :param stream: data portion of netlink message
     :reurns: attribute dict attr->value
    """
    attrs = {}
    attrlen = nl.NLATTRLEN
    l = len(stream)
    offset = 0
    while offset < l:
        # get the next attribute length and type, pull it off and
        # append to attrs, then adjust offset to fall on next boundary
        alen, atype = struct.unpack_from(nl.nl_nlattr,stream,offset)
        offset += attrlen
        alen -= attrlen
        attrs[atype] = stream[offset:offset + alen]
        offset = nl.NLMSG_ALIGN(offset + alen)
    return attrs

def nlm_parse(msg):
    """
     parse a netlink message
     :param msg: returned result from netlink
     :returns: attribute dict attr->value
    """
    # unpack the netlink message header
    offset = 0
    (l,t,f,s,p) = struct.unpack_from(nl.nl_nlmsghdr,msg,offset)
    offset += nl.NLMSGHDRLEN
    if t == nl.NLMSG_ERROR:
        raise PYWError("Netlink error: {0}".format(nle_parse(msg)))
    assert t == nl.NETLINK_GENERIC

    # unpack the generic message header
    (cmd,_,_) = struct.unpack_from(genl.genl_genlmsghdr,msg,offset)
    offset += genl.GENLMSGHDRLEN

    # remainder of msg should be netlink attr stream
    attrs = {}
    attrlen = nl.NLATTRLEN
    while offset < l:
        # get the next attribute length and type, pull it off and
        # append to attrs, then adjust offset to fall on next boundary
        alen,atype = struct.unpack_from(nl.nl_nlattr,msg,offset)
        offset += attrlen
        alen -= attrlen
        attrs[atype] = msg[offset:offset+alen]
        offset = nl.NLMSG_ALIGN(offset+alen)
    return attrs

def nle_parse(msg):
    """
     parse a netlink error
     :param msg: returned result from netlink
     :returns: string representation of error code
    """
    (ecode,_,_,_,_,_) = struct.unpack_from(nl.nl_nlmsgerr,msg,nl.NLMSGHDRLEN)
    return nl.nlerror(ecode)