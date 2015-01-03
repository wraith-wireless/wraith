#!/usr/bin/env python

""" infoelement 802.11 information element ids

Fixed Parameter and Information Element constants for 802.11 MGMT Frames, listed here
to avoid cluttering up mpdu.py

See Std Table 8-54

TODO:
 1) parse out "interesting" info element fields, status, reason codes (look at http://w1.fi/wpa_supplicant/devel
   /ieee802__11__defs_8h_source.html for)
  o RSN 48
  o Neighbor Report 52
"""
__name__ = 'infoelement'
__license__ = 'GPL'
__version__ = '0.0.1'
__date__ = 'December 2014'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@hushmail.com'
__status__ = 'Production'

from wraith.radio.bits import leastx

# CONSTANTS for element ids
# reserved 17 to 31, 47, 49, 128, 129, 133-136, 143-173, 175-220, 222-255
# undefined 77,103
EID_SSID                    =   0
EID_SUPPORTED_RATES         =   1
EID_FH                      =   2
EID_DSSS                    =   3
EID_CF                      =   4
EID_TIM                     =   5
EID_IBSS                    =   6
EID_COUNTRY                 =   7
EID_HOP_PARAMS              =   8
EID_HOP_TABLE               =   9
EID_REQUEST                 =  10
EID_BSS_LOAD                =  11
EID_EDCA                    =  12
EID_TSPEC                   =  13
EID_TCLAS                   =  14
EID_SCHED                   =  15
EID_CHALLENGE               =  16
EID_PWR_CONSTRAINT          =  32
EID_PWR_CAPABILITY          =  33
EID_TPC_REQ                 =  34
EID_TPC_RPT                 =  35
EID_CHANNELS                =  36
EID_CH_SWITCH               =  37
EID_MEAS_REQ                =  38
EID_MEAS_RPT                =  39
EID_QUIET                   =  40
EID_IBSS_DFS                =  41
EID_ERP                     =  42
EID_TS_DELAY                =  43
EID_TCLAS_PRO               =  44
EID_HT_CAP                  =  45
EID_QOS_CAP                 =  46
EID_RSN                     =  48
EID_EXT_RATES               =  50
EID_AP_CH_RPT               =  51
EID_NEIGHBOR_RPT            =  52
EID_RCPI                    =  53
EID_MDE                     =  54
EID_FAST_BSS                =  55
EID_TO_INT                  =  56
EID_RDE                     =  57
EID_DSE                     =  58
EID_OP_CLASSES              =  59
EID_EXT_CH_SWITCH           =  60
EID_HT_OP                   =  61
EID_SEC_CH_OFFSET           =  62
EID_BSS_AVG_DELAY           =  63
EID_ANTENNA                 =  64
EID_RSNI                    =  65
EID_MEAS_PILOT              =  66
EID_BSS_AVAIL               =  67
EID_BSS_AC_DELAY            =  68
EID_TIME_ADV                =  69
EID_RM_ENABLED              =  70
EID_MUL_BSSID               =  71
EID_20_40_COEXIST           =  72
EID_20_40_INTOLERANT        =  73
EID_OVERLAPPING_BSS         =  74
EID_RIC_DESC                =  75
EID_MGMT_MIC                =  76
EID_EVENT_REQ               =  78
EID_EVENT_RPT               =  79
EID_DIAG_REQ                =  80
EID_DIAG_RPT                =  81
EID_LOCATION                =  82
EID_NONTRANS_BSS            =  83
EID_SSID_LIST               =  84
EID_MULT_BSSID_INDEX        =  85
EID_FMS_DESC                =  86
EID_FMS_REQ                 =  87
EID_FMS_RPT                 =  88
EID_QOS_TRAFFIC_CAP         =  89
EID_BSS_MAX_IDLE            =  90
EID_TFS_REQ                 =  91
EID_TFS_RESP                =  92
EID_WNM_SLEEP               =  93
EID_TIM_REQ                 =  94
EID_TIM_RESP                =  95
EID_COLLOCATED_INTERFERENCE =  96
EID_CH_USAGE                =  97
EID_TIME_ZONE               =  98
EID_DMS_REQ                 =  99
EID_DMS_RESP                = 100
EID_LINK_ID                 = 101
EID_WAKEUP_SCHED            = 102
EID_CH_SWITCH_TIMING        = 104
EID_PTI_CTRL                = 105
EID_TPU_BUFF_STATUS         = 106
EID_INTERNETWORKING         = 107
EID_ADV_PROTOCOL            = 108
EID_EXPEDITED_BW_REQ        = 109
EID_QOS_MAP_SET             = 110
EID_ROAMING_CONS            = 111
EID_EMERGENCY_ALERT_ID      = 112
EID_MESH_CONFIG             = 113
EID_MESH_ID                 = 114
EID_MESH_LINK_METRIC_RPT    = 115
EID_CONGESTION              = 116
EID_MESH_PEERING_MGMT       = 117
EID_MESH_CH_SWITCH_PARAM    = 118
EID_MESH_AWAKE_WIN          = 119
EID_BEACON_TIMING           = 120
EID_MCCAOP_SETUP_REQ        = 121
EID_MCCOAP_SETUP_REP        = 122
EID_MCCAOP_ADV              = 123
EID_MCCAOP_TEARDOWN         = 124
EID_GANN                    = 125
EID_RANN                    = 126
EID_EXT_CAP                 = 127
EID_PREQ                    = 130
EID_PREP                    = 131
EID_PERR                    = 132
EID_PXU                     = 137
EID_PXUC                    = 138
EID_AUTH_MESH_PEER_EXC      = 139
EID_MIC                     = 140
EID_DEST_URI                = 141
EID_UAPSD_COEXIST           = 142
EID_MCCAOP_ADV_OVERVIEW     = 174
EID_VEND_SPEC               = 221

# constants for status codes Std Table 8-37 (see also ieee80211.h)
STATUS_SUCCESS                                =   0
STATUS_UNSPECIFIED_FAILURE                    =   1
STATUS_TLDS_WAKEUP_REJECTED_ALT               =   2
STATUS_TLDS_WAKEUP_REJECTED                   =   3
STATUS_SECURITY_DISABLED                      =   5
STATUS_UNACCEPTABLE_LIFETIME                  =   6
STATUS_NOT_IN_SAME_BSSECTED                   =   7
STATUS_CAPS_MISMATCH                          =  10
STATUS_REASSOC_NO_ASSOC_EXISTS                =  11
STATUS_ASSOC_DENIED_UNSPEC                    =  12
STATUS_AUTH_ALG_NOT_SUPPORTED                 =  13
STATUS_TRANS_SEQ_UNEXPECTED                   =  14
STATUS_CHALLENGE_FAIL                         =  15
STATUS_AUTH_TIMEOUT                           =  16
STATUS_NO_ADDITIONAL_STAS                     =  17
STATUS_BASIC_RATES_MISMATCH                   =  18
STATUS_ASSOC_DENIED_NOSHORTPREAMBLE           =  19
STATUS_ASSOC_DENIED_NOPBCC                    =  20
STATUS_ASSOC_DENIED_NOAGILITY                 =  21
STATUS_ASSOC_DENIED_NOSPECTRUM                =  22
STATUS_ASSOC_REJECTED_BAD_POWER               =  23
STATUS_ASSOC_REJECTED_BAD_SUPP_CHAN           =  24
STATUS_ASSOC_DENIED_NOSHORTTIME               =  25
STATUS_ASSOC_DENIED_NODSSSOFDM                =  26
STATUS_ASSOC_DENIED_NOHTSUPPORT               =  27
STATUS_ROKH_UNREACHABLE                       =  28
STATUS_ASSOC_DENIED_NOPCO                     =  29
STATUS_REFUSED_TEMPORARILY                    =  30
STATUS_ROBUST_MGMT_FRAME_POLICY_VIOLATION     =  31
STATUS_UNSPECIFIED_QOS                        =  32
STATUS_ASSOC_DENIED_NOBANDWIDTH               =  33
STATUS_ASSOC_DENIED_POOR_CONDITIONS           =  34
STATUS_ASSOC_DENIED_UNSUPP_QOS                =  35
STATUS_REQUEST_DECLINED                       =  37
STATUS_INVALID_PARAMETERS                     =  38
STATUS_REJECTED_WITH_SUGGESTED_CHANGES        =  39
STATUS_INVALID_ELEMENT                        =  40
STATUS_INVALID_GROUP_CIPHER                   =  41
STATUS_INVALID_PAIRWISE_CIPHER                =  42
STATUS_INVALID_AKMP                           =  43
STATUS_UNSUPP_RSNE_VERSION                    =  44
STATUS_INVALID_RSNe_CAP                       =  45
STATUS_CIPHER_SUITE_REJECTED                  =  46
STATUS_REJECTED_FOR_DELAY_PERIOD              =  47
STATUS_DLS_NOT_ALLOWED                        =  48
STATUS_NOT_PRESENT                            =  49
STATUS_NOT_QOS_STA                            =  50
STATUS_ASSOC_DENIED_LISTEN_INT                =  51
STATUS_INVALID_FT_SPEC_MGMT_CNT            =  52
STATUS_INVALID_PMKID                          =  53
STATUS_INVALID_MDE                            =  54
STATUS_INVALID_FTE                            =  55
STATUS_TCLAS_NOT_SUPPORTED                    =  56
STATUS_INSUFFICIENT_TCLAS                     =  57
STATUS_SUGGEST_TRANSISTION                    =  58
STATUS_GAS_ADV_PROTOCOL_NOT_SUPPORTED         =  59
STATUS_NO_OUTSTANDING_GAS_REQUEST             =  60
STATUS_GAS_RESPONSE_NOT_RECEIVED_FROM_SERVER  =  61
STATUS_GAS_QUERY_TIMEOUT                      =  62
STATUS_GAS_QUERY_RESPONSE_TOO_LARGE           =  63
STATUS_REJECTED_HOME_WITH_SUGGESTED_CHANGES   =  64
STATUS_SERVER_UNREACHABLE                     =  65
STATUS_REJECTED_FOR_SSP_PERMISSIONS           =  67
STATUS_NO_UNAUTHENTICATED_ACCESS              =  68
STATUS_INVALID_RSNE_CONTENTS                  =  72
STATUS_UAPSD_COEXIST_NOTSUPPORTED             =  73
STATUS_REQUESTED_UAPSD_COEXIST_NOTSUPPORTED   =  74
STATUS_REQUESTED_UAPSD_INTERVAL_NOTSUPPORTED  =  75
STATUS_ANTI_CLOG_TOKEN_REQUIRED               =  76
STATUS_FCG_NOT_SUPP                           =  77
STATUS_CANNOT_FIND_ALTERNATIVE_TBTT           =  78
STATUS_TRANSMISSION_FAILURE                   =  79
STATUS_REQUESTED_TCLAS_NOT_SUPPORTED          =  80
STATUS_TCLAS_RESOURCES_EXHAUSTED              =  81
STATUS_REJECTED_WITH_SUGGESTED_BSS_TRANSITION =  82
STATUS_REFUSED_EXTERNAL_REASON                =  92
STATUS_REFUSED_AP_OUT_OF_MEMORY               =  93
STATUS_REJECTED_EMER_SERVICES_NOT_SUPPORTED   =  94
STATUS_QUERY_RESPONSE_OUTSTANDING             =  95
STATUS_MCCAOP_RESERVATION_CONFLICT            = 100
STATUS_MAF_LIMIT_EXCEEDED                     = 101
STATUS_MCCA_TRACK_LIMIT_EXCEEDED              = 102

# authentication algorithm numbers Std Table 8-36 (see also ieee80211.h)
AUTH_ALGORITHM_OPEN   =     0
AUTH_ALGORITHM_SHARED =     1
AUTH_ALGORITHM_FAST   =     2
AUTH_ALGORITHM_SAE    =     3
AUTH_ALGORITHM_VENDOR = 63535

# action category codes Std Table 8-38
CATEGORY_SPECTRUM_MGMT             =   0
CATEGORY_QOS                       =   1
CATEGORY_DLS                       =   2
CATEGORY_BLOCK_ACK                 =   3
CATEGORY_PUBLIC                    =   4
CATEGORY_HT                        =   7
CATEGORY_SA_QUERY                  =   8
CATEGORY_PROTECTED_DUAL_OF_ACTION  =   9
CATEGORY_TDLS                      =  12
CATEGORY_MESH_ACTION               =  13
CATEGORY_MULTIHOP_ACTION           =  14
CATEGORY_SELF_PROTECTED            =  15
CATEGORY_DMG                       =  16
CATEGORY_WMM                       =  17
CATEGORY_FST                       =  18
CATEGORY_UNPROT_DMG                =  20
CATEGORY_VHT                       =  21
CATEGORY_VENDOR_SPECIFIC_PROTECTED = 126
CATEGORY_VENDOR_SPECIFIC           = 127

# reason code Std Table 8-36 (not an info element but kept here anyway)
REASON_UNSPECIFIED                    =  1
REASON_PREV_AUTH_NOT_VALID            =  2
REASON_DEAUTH_LEAVING                 =  3
REASON_DISASSOC_DUE_TO_INACTIVITY     =  4
REASON_DISASSOC_AP_BUSY               =  5
REASON_CLASS2_FRAME_FROM_NONAUTH_STA  =  6
REASON_CLASS3_FRAME_FROM_NONASSOC_STA =  7
REASON_DISASSOC_STA_HAS_LEFT          =  8
REASON_STA_REQ_ASSOC_WITHOUT_AUTH     =  9
REASON_DISASSOC_BAD_POWER             = 10
REASON_DISASSOC_BAD_SUPP_CHAN         = 11
REASON_INVALID_IE                     = 13
REASON_MIC_FAILURE                    = 14
REASON_4WAY_HANDSHAKE_TIMEOUT         = 15
REASON_GROUP_KEY_HANDSHAKE_TIMEOUT    = 16
REASON_IE_DIFFERENT                   = 17
REASON_INVALID_GROUP_CIPHER           = 18
REASON_INVALID_PAIRWISE_CIPHER        = 19
REASON_INVALID_AKMP                   = 20
REASON_UNSUPP_RSN_VERSION             = 21
REASON_INVALID_RSN_IE_CAP             = 22
REASON_IEEE8021X_FAILED               = 23
REASON_CIPHER_SUITE_REJECTED          = 24
REASON_TDLS_Dl_TEARDOWN_UNREACHABLE   = 25
REASON_TDLS_DL_TEARDOWN_UNSPECIFIED   = 26
REASON_SSP_REQUEST                    = 27
REASON_NO_SSP_ROAMING_AGREEMENT       = 28
REASON_SSP_CIPHER_SUITE               = 29
REASON_NOT_AUTHORIZED_LOCATION        = 30
REASON_SERVICE_CHANGE_PRECLUDES_TS    = 31
REASON_DISASSOC_UNSPECIFIED_QOS       = 32
REASON_DISASSOC_QAP_NO_BANDWIDTH      = 33
REASON_DISASSOC_LOW_ACK               = 34
REASON_DISASSOC_QAP_EXCEED_TXOP       = 35
REASON_STA_LEAVING                    = 36
REASON_STA_NOT_USING_MECH             = 37
REASON_QSTA_REQUIRE_SETUP             = 38
REASON_QSTA_TIMEOUT                   = 39
REASON_QSTA_CIPHER_NOT_SUPP           = 45
REASON_MESH_PEER_CANCELED             = 52
REASON_MESH_MAX_PEERS                 = 53
REASON_MESH_CONFIG                    = 54
REASON_MESH_CLOSE                     = 55
REASON_MESH_MAX_RETRIES               = 56
REASON_MESH_CONFIRM_TIMEOUT           = 57
REASON_MESH_INVALID_GTK               = 58
REASON_MESH_INCONSISTENT_PARAM        = 59
REASON_MESH_INVALID_SECURITY          = 60
REASON_MESH_PATH_ERROR                = 61
REASON_MESH_PATH_NOFORWARD            = 62
REASON_MESH_PATH_DEST_UNREACHABLE     = 63
REASON_MAC_EXISTS_IN_MBSS             = 64
REASON_MESH_CHAN_REGULATORY           = 65
REASON_MESH_CHAN                      = 66

# venue group codes type assignments Std Table 8-52 and Table 8-53 802.11u
# these are included because they may offer interesting information
VENUE_UNSPECIFIED   =  0
VENUE_ASSEMBLY      =  1
VENUE_BUSINESS      =  2
VENUE_EDUCATION     =  3
VENUE_INDUSTRIAL    =  4
VENUE_INSTITUTIONAL =  5
VENUE_MERCANTILE    =  6
VENUE_RESIDENTIAL   =  7
VENUE_STORAGE       =  8
VENUE_UTILITY       =  9
VENUE_VEHICLULAR    = 10
VENUE_OUTDOOR       = 11
VENUE_TYPE_ASSIGN = {VENUE_UNSPECIFIED:{0,"UNSPECIFIED"},
                     VENUE_ASSEMBLY:{0:"UNSPECIFIED",
                                     1:"ARENA",
                                     2:"STADIUM",
                                     3:"TERMINAL",
                                     4:"AMPITHEATER",
                                     5:"AMUSEMENT",
                                     6:"WORSHIP",
                                     7:"CONVENTION",
                                     8:"LIBRARY",
                                     9:"MUSEUM",
                                     10:"RESTAUARANT",
                                     11:"THEATER",
                                     12:"BAR",
                                     13:"COFFEE SHOP",
                                     14:"ZOO/AQUARIUM",
                                     15:"ECC"},
                     VENUE_BUSINESS:{0:"UNSPECIFIED",
                                     1:"DOCTOR",
                                     2:"BANK",
                                     3:"FIRE",
                                     4:"POLICE",
                                     6:"USPS",
                                     7:"PROFESSIONAL",
                                     8:"RD FACILITY",
                                     9:"ATTORNEY"},
                     VENUE_EDUCATION:{0:"UNSPECIFIED",
                                      1:"PRIMARY",
                                      2:"SECONDARY",
                                      3:"UNIVERSITY"},
                     VENUE_INDUSTRIAL:{0:"UNSPECIFIED",
                                       1:"FACTORY"},
                     VENUE_INSTITUTIONAL:{0:"UNSPECIFIED",
                                          1:"HOSPITAL",
                                          2:"LONG-TERM CARE",
                                          3:"REHAB",
                                          4:"GROUP HOME",
                                          5:"CORRECTIONS"},
                     VENUE_MERCANTILE:{0:"UNSPECIFIED",
                                       1:"RETAIL",
                                       2:"GROCERY",
                                       3:"AUTOMOTIVE",
                                       4:"MALL",
                                       5:"GAS STATION"},
                     VENUE_RESIDENTIAL:{0:"UNSPECIFIED",
                                        1:"PRIVATE",
                                        2:"HOTEL",
                                        3:"DORM",
                                        4:"BOARDING"},
                     VENUE_STORAGE:{0:"UNSPECIFIED"},
                     VENUE_UTILITY:{1:"UNSPECIFIED"},
                     VENUE_VEHICLULAR:{0:"UNSPECIFIED",
                                       1:"AUTOMOBILE",
                                       2:"AIRPLANE",
                                       3:"BUS",
                                       4:"FERRY",
                                       5:"SHIP",
                                       6:"TRAIN",
                                       7:"MOTORCYCLE"},
                     VENUE_OUTDOOR:{0:"UNSPECIFIED",
                                    1:"MUNI-MESH",
                                    2:"PARK",
                                    3:"REST AREA",
                                    4:"TRAFFIC CONTROL",
                                    5:"BUS STOP",
                                    6:"KIOSK"}}


# action frames Std 8.5.1
SPEC_MGMT_MEAS_REQ  = 0
SPEC_MGMT_MEAS_REP  = 1
SPEC_MGMT_TPC_REQ   = 2
SPEC_MGMT_TPC_REP   = 3
SPEC_MGMT_CH_SWITCH = 4

# SUUPORTED RATES/EXTENDED RATES Std 8.4.2.3 and 8.4.2.15

# Std 6.5.5.2 table of rates not contained in the BSSBasicRateSet
# TODO: make sure this confirms to Std 8.4.2.3/8.4.2.15
# Reading 8.4.2.3 directs to the table in 6.5.5.2 which (see below) relates
# the number in bits 0-6 to 0.5 * times that number which is the same thing
# that happens if MSB is set to 1 ????
_RATE_DIVIDER_ = 7
#_DATA_RATE_ = {2:1,3:1.5,4:2,5:2.5,6:3,9:4.5,11:5.5,12:6,18:9,22:11,24:12,
#               27:13.5,36:18,44:22,48:24,54:27,66:33,72:36,96:48,108:54}
def getrate(val): return leastx(_RATE_DIVIDER_,val) * 0.5
    #r = leastx(_RATE_DIVIDER_,val)
    #if mostx(_RATE_DIVIDER_,val):
    #    print 'True', r, r*0.5
    #    return r * 0.5
    #else:
    #    print 'False', r, _DATA_RATE_[r]
    #    return _DATA_RATE_[r]