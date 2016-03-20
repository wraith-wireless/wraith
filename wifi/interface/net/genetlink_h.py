#!/usr/bin/env python

""" genetlink_h.py: port of netlink.h public header

A port of genetlink.h to python
"""

__name__ = 'genetlink_h.py'
__license__ = 'GPL v3.0'
__version__ = '0.0.1'
__date__ = 'March 2016'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Production'

import struct

GENL_NAMSIZ	= 16 # length of family name

GENL_MIN_ID	= 0x10 # hardcoded from netlink_h
GENL_MAX_ID	= 1023

"""
struct genlmsghdr {
	__u8	cmd;
	__u8	version;
	__u16	reserved;
};
"""
genl_genlmsghdr = "BBH"
GENLMSGHDRLEN = struct.calcsize(genl_genlmsghdr)
def genlmsghdr(cmd,vers=1):
    """
     create a generic netlink header
     :param cmd: message type of genetlink service
     :param vers: revision value for backward compatability
     :returns: packed generic netlink header
    """
    return struct.pack(genl_genlmsghdr,cmd,vers,0)

#GENL_HDRLEN	NLMSG_ALIGN(sizeof(struct genlmsghdr))

GENL_ADMIN_PERM		= 0x01
GENL_CMD_CAP_DO		= 0x02
GENL_CMD_CAP_DUMP	= 0x04
GENL_CMD_CAP_HASPOL	= 0x08

# List of reserved static generic netlink identifiers:
GENL_ID_GENERATE  = 0
GENL_ID_CTRL	  = 0x10 # hardcoded from netlink_h
GENL_ID_VFS_DQUOT = GENL_ID_CTRL + 1
GENL_ID_PMCRAID	  = GENL_ID_CTRL + 2


#Controller
CTRL_CMD_UNSPEC       =  0
CTRL_CMD_NEWFAMILY    =  1
CTRL_CMD_DELFAMILY    =  2
CTRL_CMD_GETFAMILY    =  3
CTRL_CMD_NEWOPS       =  4
CTRL_CMD_DELOPS       =  5
CTRL_CMD_GETOPS       =  6
CTRL_CMD_NEWMCAST_GR  =  7
CTRL_CMD_DELMCAST_GRP =  8
CTRL_CMD_GETMCAST_GRP =  9 # unused
__CTRL_CMD_MAX        = 10
CTRL_CMD_MAX         = __CTRL_CMD_MAX - 1


CTRL_ATTR_UNSPEC       = 0
CTRL_ATTR_FAMILY_ID    = 1
CTRL_ATTR_FAMILY_NAME  = 2
CTRL_ATTR_VERSION      = 3
CTRL_ATTR_HDRSIZE      = 4
CTRL_ATTR_MAXATTR      = 5
CTRL_ATTR_OPS          = 6
CTRL_ATTR_MCAST_GROUPS = 7
__CTRL_ATTR_MAX        = 9
CTRL_ATTR_MAX          = __CTRL_ATTR_MAX - 1

CTRL_ATTR_OP_UNSPEC = 0
CTRL_ATTR_OP_ID     = 1
CTRL_ATTR_OP_FLAGS  = 2
__CTRL_ATTR_OP_MAX  = 3
CTRL_ATTR_OP_MAX    = __CTRL_ATTR_OP_MAX - 1

CTRL_ATTR_MCAST_GRP_UNSPEC = 0
CTRL_ATTR_MCAST_GRP_NAME   = 1
CTRL_ATTR_MCAST_GRP_ID     = 2
__CTRL_ATTR_MCAST_GRP_MAX  = 3
CTRL_ATTR_MCAST_GRP_MAX    = __CTRL_ATTR_MCAST_GRP_MAX - 1