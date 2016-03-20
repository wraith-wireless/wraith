#!/usr/bin/env python

""" nl80211_h.py: 802.11 netlink interface public header

A port of nl80211.h to python
/*
 * 802.11 netlink interface public header
 *
 * Copyright 2006-2010 Johannes Berg <johannes@sipsolutions.net>
 * Copyright 2008 Michael Wu <flamingice@sourmilk.net>
 * Copyright 2008 Luis Carlos Cobo <luisca@cozybit.com>
 * Copyright 2008 Michael Buesch <m@bues.ch>
 * Copyright 2008, 2009 Luis R. Rodriguez <lrodriguez@atheros.com>
 * Copyright 2008 Jouni Malinen <jouni.malinen@atheros.com>
 * Copyright 2008 Colin McCabe <colin@cozybit.com>
 *
 * Permission to use, copy, modify, and/or distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 *
 * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
 * WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 * ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 * WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
 * ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
 * OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
 *
 */
Most of these constants are not used but are left for possible future use
"""

__name__ = 'nl80211_h'
__license__ = 'GPL v3.0'
__version__ = '0.0.1'
__date__ = 'February 2016'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

NL80211_GENL_NAME = 'nl80211'

# enum nl80211_commands - supported nl80211 commands
NL80211_CMD_UNSPEC                   =   0
NL80211_CMD_GET_WIPHY                =   1 		# can dump
NL80211_CMD_SET_WIPHY                =   2
NL80211_CMD_NEW_WIPHY                =   3
NL80211_CMD_DEL_WIPHY                =   4
NL80211_CMD_GET_INTERFACE            =   5 	# can dump
NL80211_CMD_SET_INTERFACE            =   6
NL80211_CMD_NEW_INTERFACE            =   7
NL80211_CMD_DEL_INTERFACE            =   8
NL80211_CMD_GET_KEY                  =   9
NL80211_CMD_SET_KEY                  =  10
NL80211_CMD_NEW_KEY                  =  11
NL80211_CMD_DEL_KEY                  =  12
NL80211_CMD_GET_BEACON               =  13
NL80211_CMD_SET_BEACON               =  14
NL80211_CMD_START_AP                 =  15
NL80211_CMD_NEW_BEACON = NL80211_CMD_START_AP
NL80211_CMD_STOP_AP                  =  16
NL80211_CMD_DEL_BEACON = NL80211_CMD_STOP_AP
NL80211_CMD_GET_STATION              =  17
NL80211_CMD_SET_STATION              =  18
NL80211_CMD_NEW_STATION              =  19
NL80211_CMD_DEL_STATION              =  20
NL80211_CMD_GET_MPATH                =  21
NL80211_CMD_SET_MPATH                =  22
NL80211_CMD_NEW_MPATH                =  23
NL80211_CMD_DEL_MPATH                =  24
NL80211_CMD_SET_BSS                  =  25
NL80211_CMD_SET_REG                  =  26
NL80211_CMD_REQ_SET_REG              =  27
NL80211_CMD_GET_MESH_CONFIG          =  28
NL80211_CMD_SET_MESH_CONFIG          =  29
NL80211_CMD_SET_MGMT_EXTRA_IE        =  30 # reserved; not used
NL80211_CMD_GET_REG                  =  31
NL80211_CMD_GET_SCAN                 =  32
NL80211_CMD_TRIGGER_SCAN             =  33
NL80211_CMD_NEW_SCAN_RESULTS         =  34
NL80211_CMD_SCAN_ABORTED             =  35
NL80211_CMD_REG_CHANGE               =  36
NL80211_CMD_AUTHENTICATE             =  37
NL80211_CMD_ASSOCIATE                =  38
NL80211_CMD_DEAUTHENTICATE           =  39
NL80211_CMD_DISASSOCIATE             =  40
NL80211_CMD_MICHAEL_MIC_FAILURE      =  41
NL80211_CMD_REG_BEACON_HINT          =  42
NL80211_CMD_JOIN_IBSS                =  43
NL80211_CMD_LEAVE_IBSS               =  44
NL80211_CMD_TESTMODE                 =  45
NL80211_CMD_CONNECT                  =  46
NL80211_CMD_ROAM                     =  47
NL80211_CMD_DISCONNECT               =  48
NL80211_CMD_SET_WIPHY_NETNS          =  49
NL80211_CMD_GET_SURVEY               =  50
NL80211_CMD_NEW_SURVEY_RESULTS       =  51
NL80211_CMD_SET_PMKSA                =  52
NL80211_CMD_DEL_PMKSA                =  53
NL80211_CMD_FLUSH_PMKSA              =  54
NL80211_CMD_REMAIN_ON_CHANNEL        =  55
NL80211_CMD_CANCEL_REMAIN_ON_CHANNEL =  56
NL80211_CMD_SET_TX_BITRATE_MASK      =  57
NL80211_CMD_REGISTER_FRAME           =  58
NL80211_CMD_REGISTER_ACTION = NL80211_CMD_REGISTER_FRAME
NL80211_CMD_FRAME                    =  59
NL80211_CMD_ACTION = NL80211_CMD_FRAME
NL80211_CMD_FRAME_TX_STATUS          =  60
NL80211_CMD_ACTION_TX_STATUS = NL80211_CMD_FRAME_TX_STATUS
NL80211_CMD_SET_POWER_SAVE           =  61
NL80211_CMD_GET_POWER_SAVE           =  62
NL80211_CMD_SET_CQM                  =  63
NL80211_CMD_NOTIFY_CQM               =  64
NL80211_CMD_SET_CHANNEL              =  65
NL80211_CMD_SET_WDS_PEER             =  66
NL80211_CMD_FRAME_WAIT_CANCEL        =  67
NL80211_CMD_JOIN_MESH                =  68
NL80211_CMD_LEAVE_MESH               =  69
NL80211_CMD_UNPROT_DEAUTHENTICATE    =  70
NL80211_CMD_UNPROT_DISASSOCIATE      =  71
NL80211_CMD_NEW_PEER_CANDIDATE       =  72
NL80211_CMD_GET_WOWLAN               =  73
NL80211_CMD_SET_WOWLAN               =  74
NL80211_CMD_START_SCHED_SCAN         =  75
NL80211_CMD_STOP_SCHED_SCAN          =  76
NL80211_CMD_SCHED_SCAN_RESULTS       =  77
NL80211_CMD_SCHED_SCAN_STOPPED       =  78
NL80211_CMD_SET_REKEY_OFFLOAD        =  79
NL80211_CMD_PMKSA_CANDIDATE          =  80
NL80211_CMD_TDLS_OPER                =  81
NL80211_CMD_TDLS_MGMT                =  82
NL80211_CMD_UNEXPECTED_FRAME         =  83
NL80211_CMD_PROBE_CLIENT             =  84
NL80211_CMD_REGISTER_BEACONS         =  85
NL80211_CMD_UNEXPECTED_4ADDR_FRAME   =  86
NL80211_CMD_SET_NOACK_MAP            =  87
NL80211_CMD_CH_SWITCH_NOTIFY         =  88
NL80211_CMD_START_P2P_DEVICE         =  89
NL80211_CMD_STOP_P2P_DEVICE          =  90
NL80211_CMD_CONN_FAILED              =  91
NL80211_CMD_SET_MCAST_RATE           =  92
NL80211_CMD_SET_MAC_ACL              =  93
NL80211_CMD_RADAR_DETECT             =  94
NL80211_CMD_GET_PROTOCOL_FEATURES    =  95
NL80211_CMD_UPDATE_FT_IES            =  96
NL80211_CMD_FT_EVENT                 =  97
NL80211_CMD_CRIT_PROTOCOL_START      =  98
NL80211_CMD_CRIT_PROTOCOL_STOP       =  99
NL80211_CMD_GET_COALESCE             = 100
NL80211_CMD_SET_COALESCE             = 101
NL80211_CMD_CHANNEL_SWITCH           = 102
# add new commands above here
# used to define NL80211_CMD_MAX below
__NL80211_CMD_AFTER_LAST             = 103
NL80211_CMD_MAX = __NL80211_CMD_AFTER_LAST - 1