#!/usr/bin/env python

""" netlink_h.py: port of netlink.h public header

A port of netlink.h to python
"""

__name__ = 'netlink_h.py'
__license__ = 'GPL v3.0'
__version__ = '0.0.1'
__date__ = 'March 2016'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Production'

import socket
import struct

NETLINK_ROUTE		   =  0	# Routing/device hook
NETLINK_UNUSED		   =  1	# Unused number
NETLINK_USERSOCK	   =  2	# Reserved for user mode socket protocols
NETLINK_FIREWALL	   =  3	# Unused number, formerly ip_queue
NETLINK_SOCK_DIAG	   =  4	# socket monitoring
NETLINK_NFLOG		   =  5	# netfilter/iptables ULOG
NETLINK_XFRM		   =  6	# ipsec
NETLINK_SELINUX		   =  7	# SELinux event notifications
NETLINK_ISCSI		   =  8	# Open-iSCSI
NETLINK_AUDIT		   =  9	# auditing
NETLINK_FIB_LOOKUP	   = 10
NETLINK_CONNECTOR	   = 11
NETLINK_NETFILTER	   = 12	# netfilter subsystem
NETLINK_IP6_FW		   = 13
NETLINK_DNRTMSG		   = 14	# DECnet routing messages
NETLINK_KOBJECT_UEVENT = 15	# Kernel messages to userspace
NETLINK_GENERIC		   = 16
#leave room for NETLINK_DM (DM Events)
NETLINK_SCSITRANSPORT  = 18	# SCSI Transports
NETLINK_ECRYPTFS	   = 19
NETLINK_RDMA		   = 20
NETLINK_CRYPTO		   = 21	# Crypto layer

NETLINK_INET_DIAG = NETLINK_SOCK_DIAG

MAX_LINKS = 32

"""
struct sockaddr_nl {
	__kernel_sa_family_t	nl_family;	/* AF_NETLINK	*/
	unsigned short	nl_pad;		/* zero		*/
	__u32		nl_pid;		/* port ID	*/
       	__u32		nl_groups;	/* multicast groups mask */
};
"""
#def sockaddr_nl(pid,groups):
#    """
#     create a netlink sockaddr
#     :param pid:
#     :param groups:
#     :returns: packed netlink sockaddr
#    """
#    # sa_family = socket.AF_NETLINK
#    pass

"""
struct nlmsghdr {
	__u32		nlmsg_len;	/* Length of message including header */
	__u16		nlmsg_type;	/* Message content */
	__u16		nlmsg_flags;	/* Additional flags */
	__u32		nlmsg_seq;	/* Sequence number */
	__u32		nlmsg_pid;	/* Sending process port ID */
};
"""
nl_nlmsghdr = "IHHII"
NLMSGHDRLEN = struct.calcsize(nl_nlmsghdr)
def nlmsghdr(mlen,nltype,flags,seq,pid):
    """
     create a nlmsghdr
     :param mlen: length of message
     :param nltype: message content
     :param flags: additional flags
     :param seq: sequence number
     :param pid: process port id
     :returns: packed netlink msg header
    """
    return struct.pack(nl_nlmsghdr,NLMSGHDRLEN+mlen,nltype,flags,seq,pid)

# Flags values
NLM_F_REQUEST	=  1 # It is request message.
NLM_F_MULTI		=  2 # Multipart message, terminated by NLMSG_DONE
NLM_F_ACK		=  4 # Reply with ack, with zero or error code
NLM_F_ECHO		=  8 # Echo this request
NLM_F_DUMP_INTR = 16 # Dump was inconsistent due to sequence change

# Modifiers to GET request
NLM_F_ROOT	 = 0x100 # specify tree	root
NLM_F_MATCH	 = 0x200 # return all matching
NLM_F_ATOMIC = 0x400 # atomic GET
NLM_F_DUMP = (NLM_F_ROOT|NLM_F_MATCH)

# Modifiers to NEW request
NLM_F_REPLACE = 0x100 # Override existing
NLM_F_EXCL	  = 0x200 # Do not touch, if it exists
NLM_F_CREATE  = 0x400 # Create, if it does not exist
NLM_F_APPEND  = 0x800 # Add to end of list

"""
/*
   4.4BSD ADD		NLM_F_CREATE|NLM_F_EXCL
   4.4BSD CHANGE	NLM_F_REPLACE

   True CHANGE		NLM_F_CREATE|NLM_F_REPLACE
   Append		NLM_F_CREATE
   Check		NLM_F_EXCL
 */
"""

#NLMSG_ALIGNTO	4U
#NLMSG_ALIGN(len) ( ((len)+NLMSG_ALIGNTO-1) & ~(NLMSG_ALIGNTO-1) )
#NLMSG_HDRLEN	 ((int) NLMSG_ALIGN(sizeof(struct nlmsghdr)))
#NLMSG_LENGTH(len) ((len) + NLMSG_HDRLEN)
#NLMSG_SPACE(len) NLMSG_ALIGN(NLMSG_LENGTH(len))
#NLMSG_DATA(nlh)  ((void*)(((char*)nlh) + NLMSG_LENGTH(0)))
#NLMSG_NEXT(nlh,len)	 ((len) -= NLMSG_ALIGN((nlh)->nlmsg_len), \
#				  (struct nlmsghdr*)(((char*)(nlh)) + NLMSG_ALIGN((nlh)->nlmsg_len)))
#NLMSG_OK(nlh,len) ((len) >= (int)sizeof(struct nlmsghdr) && \
#			   (nlh)->nlmsg_len >= sizeof(struct nlmsghdr) && \
#			   (nlh)->nlmsg_len <= (len))
#NLMSG_PAYLOAD(nlh,len) ((nlh)->nlmsg_len - NLMSG_SPACE((len)))

NLMSG_NOOP	   = 0x1 # Nothing.
NLMSG_ERROR	   = 0x2 # Error
NLMSG_DONE	   = 0x3 # End of a dump
NLMSG_OVERRUN  = 0x4 # Data lost

NLMSG_MIN_TYPE = 0x10 # < 0x10: reserved control messages

"""
struct nlmsgerr {
	int		error;
	struct nlmsghdr msg;
};
"""

NETLINK_ADD_MEMBERSHIP	= 1
NETLINK_DROP_MEMBERSHIP	= 2
NETLINK_PKTINFO		    = 3
NETLINK_BROADCAST_ERROR	= 4
NETLINK_NO_ENOBUFS	    = 5
NETLINK_RX_RING		    = 6
NETLINK_TX_RING		    = 7

"""
struct nl_pktinfo {
	__u32	group;
};
"""

"""
struct nl_mmap_req {
	unsigned int	nm_block_size;
	unsigned int	nm_block_nr;
	unsigned int	nm_frame_size;
	unsigned int	nm_frame_nr;
};
"""

"""
struct nl_mmap_hdr {
	unsigned int	nm_status;
	unsigned int	nm_len;
	__u32		nm_group;
	/* credentials */
	__u32		nm_pid;
	__u32		nm_uid;
	__u32		nm_gid;
};
"""

# nume nl_nmap_status
NL_MMAP_STATUS_UNUSED = 0
NL_MMAP_STATUS_RESERVED = 1
NL_MMAP_STATUS_VALID = 2
NL_MMAP_STATUS_COPY = 3
NL_MMAP_STATUS_SKIP = 4

#NL_MMAP_MSG_ALIGNMENT		NLMSG_ALIGNTO
#NL_MMAP_MSG_ALIGN(sz)		__ALIGN_KERNEL(sz, NL_MMAP_MSG_ALIGNMENT)
#NL_MMAP_HDRLEN			NL_MMAP_MSG_ALIGN(sizeof(struct nl_mmap_hdr))

NET_MAJOR = 36 # Major 36 is reserved for networking

NETLINK_UNCONNECTED = 0
NETLINK_CONNECTED   = 1

"""
/*
 *  <------- NLA_HDRLEN ------> <-- NLA_ALIGN(payload)-->
 * +---------------------+- - -+- - - - - - - - - -+- - -+
 * |        Header       | Pad |     Payload       | Pad |
 * |   (struct nlattr)   | ing |                   | ing |
 * +---------------------+- - -+- - - - - - - - - -+- - -+
 *  <-------------- nlattr->nla_len -------------->
 */
"""

"""
struct nlattr {
	__u16           nla_len;
	__u16           nla_type;
};
"""

"""
/*
 * nla_type (16 bits)
 * +---+---+-------------------------------+
 * | N | O | Attribute Type                |
 * +---+---+-------------------------------+
 * N := Carries nested attributes
 * O := Payload stored in network byte order
 *
 * Note: The N and O flag are mutually exclusive.
 */
"""
NLA_F_NESTED		= (1 << 15)
NLA_F_NET_BYTEORDER	= (1 << 14)
NLA_TYPE_MASK		= ~(NLA_F_NESTED | NLA_F_NET_BYTEORDER)

#NLA_ALIGNTO		= 4
#NLA_ALIGN(len)	= (((len) + NLA_ALIGNTO - 1) & ~(NLA_ALIGNTO - 1))
#NLA_HDRLEN		= ((int) NLA_ALIGN(sizeof(struct nlattr)))