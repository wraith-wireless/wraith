#!/usr/bin/env python

""" sockios_h.py: definitions for INET interface module

A port of if.h to python
/*
 * INET		An implementation of the TCP/IP protocol suite for the LINUX
 *		operating system.  INET is implemented using the  BSD Socket
 *		interface as the means of communication with the user level.
 *
 *		Global definitions for the INET interface module.
 *
 * Version:	@(#)if.h	1.0.2	04/18/93
 *
 * Authors:	Original taken from Berkeley UNIX 4.3, (c) UCB 1982-1988
 *		Ross Biro
 *		Fred N. van Kempen, <waltje@uWalt.NL.Mugnet.ORG>
 *
 *		This program is free software; you can redistribute it and/or
 *		modify it under the terms of the GNU General Public License
 *		as published by the Free Software Foundation; either version
 *		2 of the License, or (at your option) any later version.
 */
"""

__name__ = 'if_h'
__license__ = 'GPL v3.0'
__version__ = '0.0.1'
__date__ = 'February 2016'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import struct

IFNAMSIZ = 16
IFALIASZ = 256

# Standard interface flags (netdevice->flags).
IFF_UP		    = 0x1	  # interface is up
IFF_BROADCAST	= 0x2	  # broadcast address valid
IFF_DEBUG	    = 0x4	  # turn on debugging
IFF_LOOPBACK	= 0x8	  # is a loopback net
IFF_POINTOPOINT	= 0x10	  # interface is has p-p link
IFF_NOTRAILERS	= 0x20	  # avoid use of trailers
IFF_RUNNING	    = 0x40	  # interface RFC2863 OPER_UP
IFF_NOARP	    = 0x80	  # no ARP protocol
IFF_PROMISC	    = 0x100	  # receive all packets
IFF_ALLMULTI	= 0x200	  # receive all multicast packets
IFF_MASTER	    = 0x400	  # master of a load balancer
IFF_SLAVE	    = 0x800	  # slave of a load balancer
IFF_MULTICAST	= 0x1000  # Supports multicast
IFF_PORTSEL	    = 0x2000  # can set media type
IFF_AUTOMEDIA	= 0x4000  # auto media select active
IFF_DYNAMIC	    = 0x8000  # dialup device with changing addresses
IFF_LOWER_UP	= 0x10000 # driver signals L1 up
IFF_DORMANT	    = 0x20000 # driver signals dormant
IFF_ECHO	    = 0x40000 # echo sent packets

IFF_VOLATILE = IFF_LOOPBACK | IFF_POINTOPOINT | IFF_BROADCAST | IFF_ECHO | \
               IFF_MASTER | IFF_SLAVE | IFF_RUNNING | IFF_LOWER_UP | IFF_DORMANT

# Private (from user) interface flags (netdevice->priv_flags).
IFF_802_1Q_VLAN      = 0x1   # 802.1Q VLAN device.
IFF_EBRIDGE	         = 0x2	 # Ethernet bridging device.
IFF_SLAVE_INACTIVE	 = 0x4	 # bonding slave not the curr. active
IFF_MASTER_8023AD	 = 0x8	 # bonding master, 802.3ad.
IFF_MASTER_ALB	     = 0x10	 # bonding master, balance-alb.
IFF_BONDING	         = 0x20	 # bonding master or slave
IFF_SLAVE_NEEDARP    = 0x40	 # need ARPs for validation
IFF_ISATAP	         = 0x80	 # ISATAP interface (RFC4214)
IFF_MASTER_ARPMON    = 0x100 # bonding master, ARP mon in use
IFF_WAN_HDLC	     = 0x200 # WAN HDLC device
IFF_XMIT_DST_RELEASE = 0x400 # dev_hard_start_xmit() is allowed to release skb->dst

IFF_DONT_BRIDGE      = 0x800	# disallow bridging this ether dev
IFF_DISABLE_NETPOLL	 = 0x1000	# disable netpoll at run-time
IFF_MACVLAN_PORT	 = 0x2000	# device used as macvlan port
IFF_BRIDGE_PORT	     = 0x4000	# device used as bridge port
IFF_OVS_DATAPATH	 = 0x8000	# device used as Open vSwitch datapath port
IFF_TX_SKB_SHARING	 = 0x10000	# The interface supports sharing skbs on transmit
IFF_UNICAST_FLT	     = 0x20000	# Supports unicast filtering
IFF_TEAM_PORT	     = 0x40000	# device used as team port
IFF_SUPP_NOFCS	     = 0x80000	# device supports sending custom FCS
IFF_LIVE_ADDR_CHANGE = 0x100000	# device supports hardware address change when it's running
IFF_MACVLAN          = 0x200000	# Macvlan device


IF_GET_IFACE = 0x0001 # for querying only
IF_GET_PROTO = 0x0002

# For definitions see hdlc.h
IF_IFACE_V35	     = 0x1000 # V.35 serial interface
IF_IFACE_V24	     = 0x1001 # V.24 serial interface
IF_IFACE_X21	     = 0x1002 # X.21 serial interface
IF_IFACE_T1	         = 0x1003 # T1 telco serial interface
IF_IFACE_E1	         = 0x1004 # E1 telco serial interface
IF_IFACE_SYNC_SERIAL = 0x1005 # can't be set by software
IF_IFACE_X21D        = 0x1006 # X.21 Dual Clocking (FarSite)

# For definitions see hdlc.h
IF_PROTO_HDLC	        = 0x2000 # raw HDLC protocol
IF_PROTO_PPP	        = 0x2001 # PPP protocol
IF_PROTO_CISCO	        = 0x2002 # Cisco HDLC protocol
IF_PROTO_FR	            = 0x2003 # Frame Relay protocol
IF_PROTO_FR_ADD_PVC     = 0x2004 # Create FR PVC
IF_PROTO_FR_DEL_PVC     = 0x2005 # Delete FR PVC
IF_PROTO_X25	        = 0x2006 # X.25
IF_PROTO_HDLC_ETH       = 0x2007 # raw HDLC, Ethernet emulation
IF_PROTO_FR_ADD_ETH_PVC = 0x2008 # Create FR Ethernet-bridged PVC
IF_PROTO_FR_DEL_ETH_PVC = 0x2009 # Delete FR Ethernet-bridged PVC
IF_PROTO_FR_PVC	        = 0x200A # for reading PVC status
IF_PROTO_FR_ETH_PVC     = 0x200B
IF_PROTO_RAW            = 0x200C # RAW Socket

# RFC 2863 operational status
IF_OPER_UNKNOWN         = 0
IF_OPER_NOTPRESENT      = 1
IF_OPER_DOWN            = 2
IF_OPER_LOWERLAYERDOWN  = 3
IF_OPER_TESTING         = 4
IF_OPER_DORMANT         = 5
IF_OPER_UP              = 6

# link modes
IF_LINK_MODE_DEFAULT = 0
IF_LINK_MODE_DORMANT = 1 # limit upward transition to dormant

"""
/*
 *	Device mapping structure. I'd just gone off and designed a
 *	beautiful scheme using only loadable modules with arguments
 *	for driver options and along come the PCMCIA people 8)
 *
 *	Ah well. The get() side of this is good for WDSETUP, and it'll
 *	be handy for debugging things. The set side is fine for now and
 *	being very small might be worth keeping for clean configuration.
 */

struct ifmap {
	unsigned long mem_start;
	unsigned long mem_end;
	unsigned short base_addr;
	unsigned char irq;
	unsigned char dma;
	unsigned char port;
	# 3 bytes spare
};
"""

"""
struct if_settings {
	unsigned int type;	# Type of physical device or protocol
	unsigned int size;	# Size of the data allocated by the caller
	union {
		# {atm/eth/dsl}_settings anyone ?
		raw_hdlc_proto		*raw_hdlc;
		cisco_proto		*cisco;
		fr_proto		*fr;
		fr_proto_pvc		*fr_pvc;
		fr_proto_pvc_info	*fr_pvc_info;

		# interface settings
		sync_serial_settings	*sync;
		te1_settings		*te1;
	} ifs_ifsu;
};
"""

"""
/*
 * Interface request structure used for socket
 * ioctl's.  All interface ioctl's must have parameter
 * definitions which begin with ifr_name.  The
 * remainder may be interface specific.
"""

# IFREQ DEFINITION
IFR_IFRU_HWADDR = 0
IFR_IFRU_FLAGS = 1
ifrn_name_fmt = '{0}s'.format(IFNAMSIZ)
ifru_addr_fmt = '6B'
ifru_flags_fmt = 'h'
IFHWADDRLEN	= 6
IFNAMELEN = struct.calcsize(ifrn_name_fmt)
IFFLAGLEN = struct.calcsize(ifru_flags_fmt)
def ifreq(ifrn,ifru,param=None):
    """
     creates a 'packed' struct cooresponding loosely to the ifreq struct
     :param ifrn: name of interface/nic
     :param ifru: ifr flag oneof {IFR_IFRU_HWADDR|IFR_IFRU_FLAG} defines
      what type of ifreq struct to pack
     :param param: either a hwaddr or flag depending on ifr_ifru, if None,
      pad bytes will be added having the size of the appropriate param
      if a hwaddr, must be string of form "XX:XX:XX:XX:XX:XX", if flags,
      must be an integer
     :returns: packed ifreq
    """
    # pack the nic
    try:
        ifr = struct.pack(ifrn_name_fmt,ifrn[:IFNAMSIZ-1])
    except (struct.error,IndexError) as e:
        raise AttributeError("ifr_ifrn: {0}".format(e))

    # pack the parameter
    if ifru == IFR_IFRU_HWADDR:
        try:
            if param is None: ifr += struct.pack('{0}x'.format(IFHWADDRLEN))
            else:
                ifr += struct.pack(ifru_addr_fmt,*[int(x,16) for x in param.split(':')])
        except Exception as e:
            raise AttributeError("ifr_ifru hwaddr {0} is invalid: {1}".format(param,e))
    elif ifru == IFR_IFRU_FLAGS:
        try:
            if param is None: ifr += struct.pack('{0}x'.format(IFFLAGLEN))
            else:
                ifr += struct.pack(ifru_flags_fmt,param)
        except Exception as e:
            raise AttributeError("ifr_ifru flags {0} is invalid: {1}".format(param,e))
    else:
        raise AttributeError("ifr_ifru {0} not supported".format(ifru))

    return ifr

"""
struct ifreq {

	union
	{
		char	ifrn_name[IFNAMSIZ];		# if name, e.g. "en0"
	} ifr_ifrn;

	union {
		struct	sockaddr ifru_addr;
		struct	sockaddr ifru_dstaddr;
		struct	sockaddr ifru_broadaddr;
		struct	sockaddr ifru_netmask;
		struct  sockaddr ifru_hwaddr;
		short	ifru_flags;
		int	ifru_ivalue;
		int	ifru_mtu;
		struct  ifmap ifru_map;
		char	ifru_slave[IFNAMSIZ];	# Just fits the size
		char	ifru_newname[IFNAMSIZ];
		void *	ifru_data;
		struct	if_settings ifru_settings;
	} ifr_ifru;
};
ifr_name	ifr_ifrn.ifrn_name	# interface name
ifr_hwaddr	ifr_ifru.ifru_hwaddr	# MAC address
ifr_addr	ifr_ifru.ifru_addr	# address
ifr_dstaddr	ifr_ifru.ifru_dstaddr	# other end of p-p lnk
ifr_broadaddr	ifr_ifru.ifru_broadaddr	# broadcast address
ifr_netmask	ifr_ifru.ifru_netmask	# interface net mask
ifr_flags	ifr_ifru.ifru_flags	# flags
ifr_metric	ifr_ifru.ifru_ivalue	# metric
ifr_mtu		ifr_ifru.ifru_mtu	# mtu
ifr_map		ifr_ifru.ifru_map	# device map
ifr_slave	ifr_ifru.ifru_slave	# slave device
ifr_data	ifr_ifru.ifru_data	# for use by interface
ifr_ifindex	ifr_ifru.ifru_ivalue	# interface index
ifr_bandwidth	ifr_ifru.ifru_ivalue    # link bandwidth
ifr_qlen	ifr_ifru.ifru_ivalue	# Queue length
ifr_newname	ifr_ifru.ifru_newname	# New name
ifr_settings	ifr_ifru.ifru_settings	# Device/proto settings
"""

"""
/*
 * Structure used in SIOCGIFCONF request.
 * Used to retrieve interface configuration
 * for machine (useful for programs which
 * must know all networks accessible).
 */

struct ifconf  {
	int	ifc_len;			# size of buffer
	union {
		char *ifcu_buf;
		struct ifreq *ifcu_req;
	} ifc_ifcu;
};
ifc_buf	ifc_ifcu.ifcu_buf		# buffer address
ifc_req	ifc_ifcu.ifcu_req		# array of structures
"""