#!/usr/bin/env python

""" mpdu.py: 802.11 mac frame parsing

Parse the 802.11 MAC Protocol Data Unit (MPDU) IAW IEED 802.11-2012
we use Std when referring to IEEE Std 802.11-2012
NOTE:
 It is recommended not to import * as it may cause conflicts with other modules
"""
__name__ = 'mpdu'
__license__ = 'GPL'
__version__ = '0.0.13'
__date__ = 'December 2014'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@hushmail.com'
__status__ = 'Development'

import struct
from binascii import hexlify
from wraith.radio.bits import *
from wraith.radio import infoelement as ie

class MPDUException(Exception): pass # generic mpdu exception

# SOME CONSTANTS
BROADCAST = "ff:ff:ff:ff:ff:ff" # broadcast address
MAX_MPDU = 7991 # maximum mpdu size in bytes
# index of frame types and string titles
FT_TYPES = ['mgmt','ctrl','data','rsrv']
FT_MGMT              =  0
FT_CTRL              =  1
FT_DATA              =  2
FT_RSRV              =  3

## MGMT Subtypes
ST_MGMT_TYPES = ['assoc-req','assoc-resp','reassoc-req','reassoc-resp','probe-req',
                 'probe-resp','timing-adv','rsrv','beacon','atim','disassoc','auth',
                 'deauth','action','action_noack','rsrv']
ST_MGMT_ASSOC_REQ    =  0
ST_MGMT_ASSOC_RESP   =  1
ST_MGMT_REASSOC_REQ  =  2
ST_MGMT_REASSOC_RESP =  3
ST_MGMT_PROBE_REQ    =  4
ST_MGMT_PROBE_RESP   =  5
ST_MGMT_TIMING_ADV   =  6
ST_MGMT_RSRV_7       =  7
ST_MGMT_BEACON       =  8
ST_MGMT_ATIM         =  9
ST_MGMT_DISASSOC     = 10
ST_MGMT_AUTH         = 11
ST_MGMT_DEAUTH       = 12
ST_MGMT_ACTION       = 13
ST_MGMT_ACTION_NOACK = 14
ST_MGMT_RSRV_15      = 15
## CTRL SUB TYPES
ST_CTRL_TYPES = ['rsrv','rsrv','rsrv','rsrv','rsrv','rsrv','rsrv','wrapper',
                 'block-ack-req','block-ack','pspoll','rts','cts','ack','cfend',
                 'cfend-cfack']
ST_CTRL_RSRV_0        =  0
ST_CTRL_RSRV_1        =  1
ST_CTRL_RSRV_2        =  2
ST_CTRL_RSRV_3        =  3
ST_CTRL_RSRV_4        =  4
ST_CTRL_RSRV_5        =  5
ST_CTRL_RSRV_6        =  6
ST_CTRL_WRAPPER       =  7
ST_CTRL_BLOCK_ACK_REQ =  8
ST_CTRL_BLOCK_ACK     =  9
ST_CTRL_PSPOLL        = 10
ST_CTRL_RTS           = 11
ST_CTRL_CTS           = 12
ST_CTRL_ACK           = 13
ST_CTRL_CFEND         = 14
ST_CTRL_CFEND_CFACK   = 15
## DATA SUB TYPES
ST_DATA_TYPES = ['data','cfack','cfpoll','cfack_cfpoll','null','null-cfack',
                 'null-cfpoll','null-cfack-cfpoll','qos-data','qos-data-cfack',
                 'qos-data-cfpoll','qos-data-cfack-cfpoll','qos-null','rsrv',
                 'qos-cfpoll','qos-cfack-cfpoll']
ST_DATA_DATA                  =  0
ST_DATA_CFACK                 =  1
ST_DATA_CFPOLL                =  2
ST_DATA_CFACK_CFPOLL          =  3
ST_DATA_NULL                  =  4
ST_DATA_NULL_CFACK            =  5
ST_DATA_NULL_CFPOLL           =  6
ST_DATA_NULL_CFACK_CFPOLL     =  7
ST_DATA_QOS_DATA              =  8
ST_DATA_QOS_DATA_CFACK        =  9
ST_DATA_QOS_DATA_CFPOLL       = 10
ST_DATA_QOS_DATA_CFACK_CFPOLL = 11
ST_DATA_QOS_NULL              = 12
ST_DATA_RSRV_13               = 13
ST_DATA_QOS_CFPOLL            = 14
ST_DATA_QOS_CFACK_CFPOLL      = 15

def parse(frame,hasFCS=False):
    """
     parses the mpdu in frame (where frame is stripped of any layer 1 header)
     and returns a dict d where d will always have key->value pairs for:
      vers: mpdu version (always 0)
      sz: offset of last bytes read from mpdu (not including fcs).
      present: an ordered list of fields present in the frame
      and key->value pairs for each field in present
    """
    # at a minimum, frames will be FRAMECTRL|DURATION|ADDR1 (and fcs if not
    # stripped by the firmware) see Std 8.3.1.3
    try:
        ### 802.11 MAC Frame Control
        #  Protocol Vers 2 bits: always '00'
        #  Type 2 bits: '00' Management, '01' Control,'10' Data,'11' Reserved
        #  Subtype 4 bits
        #  This comes down the wire as:
        #   ST|FT|PV|
        #    4| 2| 2|
        # Flags
        vs,offset = _unpack_from_(_S2F_['framectrl'],frame,0)
        pfs = ['framectrl']
        mac = {'framectrl':{'vers':leastx(2,vs[0]),
                            'type':leastx(2,(212 >> 2)),
                            'subtype':mostx(4,vs[0]),
                            'flags':vs[1]}}

        # unpack duration, address 1
        vs,offset = _unpack_from_(_S2F_['duration'] + _S2F_['addr'],frame,offset)
        pfs.extend(['duration','addr1'])
        mac['duration'] = vs[0]
        mac['addr1'] = _macaddr_(vs[1:])

        # remove fcs if present (as some functions will eat all remaining bytes
        if hasFCS:
            mac['fcs'],_ = struct.unpack("=L", frame[-4:])
            frame = frame[:-4]
    except struct.error as e:
        raise MPDUException("Error unpacking minimum: %s" % e)

    # handle frame types separately
    if mac['framectrl']['type'] == FT_CTRL:
        offset = _parsectrl_(mac['framectrl']['subtype'],frame,pfs,mac,offset)
    elif mac['framectrl']['type'] == FT_MGMT:
        offset = _parsemgmt_(mac['framectrl']['subtype'],frame,pfs,mac,offset)
    elif mac['framectrl']['type'] == FT_DATA:
        offset = _parsedata_(mac['framectrl']['subtype'],frame,pfs,mac,offset)
    else:
        raise MPDUException("unresolved")

    # append the fcs to present if necessar
    if hasFCS: pfs.append('fcs')

    # return
    mac['sz'] = offset
    mac['present'] = pfs
    return mac

def subtypes(ft,st):
    """ returns the subtype description given the values ft and st """
    if ft == FT_MGMT: return ST_MGMT_TYPES[st]
    elif ft == FT_CTRL: return ST_CTRL_TYPES[st]
    elif ft == FT_DATA: return ST_DATA_TYPES[st]
    else: return 'rsrv'

# Frame Control Fields
# td -> to ds fd -> from ds mf -> more fragments r  -> retry pm -> power mgmt
# md -> more data pf -> protected frame o  -> order
_FC_FIELDS_ = {'td':(1 << 0),'fd':(1 << 1),'mf':(1 << 2),'r':(1 << 3),
               'pm':(1 << 4),'md':(1 << 5),'pf':(1 << 6),'o':(1 << 7)}
def fcfields(mn): return bitmask(_FC_FIELDS_,mn)
def fcfields_all(mn): return bitmask_list(_FC_FIELDS_,mn)
def fcfields_get(mn,f):
    try:
        return bitmask_get(_FC_FIELDS_,mn,f)
    except KeyError:
        raise MPDUException("invalid frame control flag '%s'" % f)

# Std 8.2.4.1.3
# each subtype field bit position indicates a specfic modification of the base data frame
_DATA_SUBTYPE_FIELDS_ = {'cf-ack':(1 << 0),'cf-poll':(1 << 1),'no-body':(1 << 2),'qos':(1 << 3)}
def datasubtype(mn): return bitmask(_DATA_SUBTYPE_FIELDS_,mn)
def datasubtype_all(mn): return bitmask_list(_DATA_SUBTYPE_FIELDS_,mn)
def datasubtype_get(mn,f):
    try:
        return bitmask_get(_DATA_SUBTYPE_FIELDS_,mn,f)
    except KeyError:
        raise MPDUException("invalid data subtype flag '%s'" % f)

## PRIVATE AREA ##

# unpack formats
_S2F_ = {'framectrl':'BB',
         'duration':'H',
         'addr':'6B',
         'seqctrl':'H',
         'bactrl':'H',
         'barctrl':'H',
         'qos':"BB",
         'htc':'L',
         'capability':'H',
         'listen-int':'H',
         'status-code':'H',
         'aid':'H',
         'timestamp':'Q',
         'beacon-int':'H',
         'reason-code':'H',
         'algorithm-no':'H',
         'auth-seq':'H',
         'category':'B',
         'action':'B'}

def _unpack_from_(fmt,b,o):
    """
     unpack data from the buffer b given the format specifier fmt starting at o &
     returns the unpacked data and the new offset
    """
    try:
        vs = struct.unpack_from("="+fmt,b,o)
        if len(vs) == 1: vs = vs[0]
        return vs,o+struct.calcsize(fmt)
    except struct.error as e:
        raise MPDUException('Error unpacking: %s' % e)

def _macaddr_(l):
    """ converts a list/tuple of unpacked integers to a string mac address """
    if len(l) != 6: raise RuntimeError('mac address has length 6')
    return ":".join(['{0:02X}'.format(a) for a in l])

def _parsectrl_(st,f,pfs,d,o):
    """
     parse the control frame f of subtype st starting at offset o into the dict d
     adding elements to pfs, and returning the new offset
    """
    if st == ST_CTRL_CTS or st == ST_CTRL_ACK: pass # do nothing
    elif st in [ST_CTRL_RTS,ST_CTRL_PSPOLL,ST_CTRL_CFEND,ST_CTRL_CFEND_CFACK]:
        # append addr2 and process macaddress
        pfs.append('addr2')
        v,o = _unpack_from_(_S2F_['addr'],f,o)
        d['addr2'] = _macaddr_(v)
    elif st == ST_CTRL_BLOCK_ACK_REQ:
        # append addr2, barctrl then process macaddr
        pfs.extend(['addr2','barctrl'])
        v,o = _unpack_from_(_S2F_['addr'],f,o)
        d['addr2'] = _macaddr_(v)

        # & bar control
        v,o = _unpack_from_(_S2F_['barctrl'],f,o)
        d['barctrl'] = _bactrl_(v)

        # & bar info field
        if not d['barctrl']['multi-tid']:
            # for 0 0 Basic BlockAckReq and 0 1 Compressed BlockAckReq the
            # bar info field appears to be the same 8.3.1.8.2 and 8.3.1.8.3, a
            # sequence control
            if not d['barctrl']['compressed-bm']: d['barctrl']['type'] = 'basic'
            else: d['barctrl']['type'] = 'compressed'
            v,o = _unpack_from_(_S2F_['seqctrl'],f,o)
            d['barinfo'] = _seqctrl_(v)
        else:
            if not d['barctrl']['compressed-bm']:
                # 1 0 -> Reserved
                d['barctrl']['type'] = 'reserved'
                d['barinfo'] = {'unparsed':hexlify(f[o:])}
                o += len(f[o:])
            else:
                # 1 1 -> Multi-tid BlockAckReq Std 8.3.1.8.4 See Figures Std 8-22, 8-23
                d['barctrl']['type'] = 'multi-tid'
                d['barinfo'] = {'tids':[]}
                for i in xrange(d['barctrl']['tid-info'] + 1):
                    v,o = _unpack_from_("HH",f,o)
                    d['barinfo']['tids'].append(_pertid_(v))
    elif st == ST_CTRL_BLOCK_ACK:
        # add addr2 and ba control, process addr2
        pfs.extend(['addr2','bactrl'])
        v,o = _unpack_from_(_S2F_['addr'],f,o)
        d['addr2'] = _macaddr_(v)

        # & ba control
        v,o = _unpack_from_(_S2F_['bactrl'],f,o)
        d['bactrl'] = _bactrl_(v)

        # & ba info field
        if not d['bactrl']['multi-tid']:
            v,o = _unpack_from_(_S2F_['seqctrl'],f,o)
            d['bainfo'] = _seqctrl_(v)
            if not d['bactrl']['compressed-bm']:
                # 0 0 -> Basic BlockAck 8.3.1.9.2
                d['bactrl']['type'] = 'basic'
                d['bainfo']['babitmap'] = hexlify(f[o:o+128])
                o += 128
            else:
                # 0 1 -> Compressed BlockAck Std 8.3.1.9.3
                d['bactrl']['type'] = 'compressed'
                d['bainfo']['babitmap'] = hexlify(f[o:o+8])
                o += 8
        else:
            if not d['bactrl']['compressed-bm']:
                # 1 0 -> Reserved
                d['bactrl']['type'] = 'reserved'
                d['bainfo'] = {'unparsed':hexlify(f[o:])}
            else:
                # 1 1 -> Multi-tid BlockAck Std 8.3.1.9.4 see Std Figure 8-28, 8-23
                d['bactrl']['type'] = 'multi-tid'
                d['bainfo'] = {'tids':[]}
                for i in xrange(d['bactrl']['tid-info'] + 1):
                    v,o = _unpack_from_("HH",f,o)
                    pt = _pertid_(v)
                    pt['babitmap'] = hexlify(f[o:o+8])
                    d['bainfo']['tids'].append(pt)
                    o += 8
    elif st == ST_CTRL_WRAPPER:
        # Std 8.3.1.10, carriedframectrl is a Frame Control
        pfs.extend(['carriedframectrl','htc','carriedframe'])
        v,o = _unpack_from_(_S2F_['framectrl'],f,o)
        d['carriedframectrl'] = v
        v,o = _unpack_from_(_S2F_['htc'],f,o)
        d['htc'] = v
        d['carriedframe'] = hexlify(f[o:])
        o += len(f[o:])
    else:
        raise MPDUException("Unknown subtype in CTRL frame %d" % st)
    return o

def _parsedata_(st,f,pfs,d,o):
    """
     parse the data frame f of subtype st with fields fs starting at offset o into the
     dict d adding elements to pfs, and returning the new offset
    """
    # addr2, addr3 and seq. ctrl are always present in data Std Figure 8-30, unpack together
    # (have to remove additional '=' in the individual format strings)
    pfs.extend(['addr2','addr3','seqctrl'])
    fmt = _S2F_['addr'] + _S2F_['addr'] + _S2F_['seqctrl']
    v,o = _unpack_from_(fmt,f,o)
    d['addr2'] = _macaddr_(v[0:6])
    d['addr3'] = _macaddr_(v[6:12])
    d['seqctrl'] = _seqctrl_(v[-1])

    # get frame ctrl fields
    flags = fcfields_all(d['framectrl']['flags'])

    # fourth address?
    if flags['td'] and flags['fd']:
        pfs.append('addr4')
        v,o = _unpack_from_(_S2F_['addr'],f,o)
        d['addr4'] = _macaddr_(v)

    # QoS field?
    if ST_DATA_QOS_DATA <= st <= ST_DATA_QOS_CFACK_CFPOLL:
        pfs.append('qos')
        v,o = _unpack_from_(_S2F_['qos'],f,o)
        d['qos'] = _qosctrl_(v)

        # HTC fields?
        #if flags['o']:
        #    pfs.append('htc')
        #    v,o = _unpack_from_(_S2F_['htc'],f,o)
        #    d['htc'] = _htctrl_(v)

    return o

def _parsemgmt_(st,f,pfs,d,o):
    """
     parse the mgmt frame f of subtype st with fields fs starting at offset o into the
     dict d adding elements to pfs, and returning the new offset
    """
    pfs.extend(['addr2','addr3','seqctrl'])
    fmt = _S2F_['addr'] + _S2F_['addr'] + _S2F_['seqctrl']
    v,o = _unpack_from_(fmt,f,o)
    d['addr2'] = _macaddr_(v[0:6])
    d['addr3'] = _macaddr_(v[6:12])
    d['seqctrl'] = _seqctrl_(v[-1])

    # HTC fields?
    #flags = fcfields_all(d['framectrl']['flags'])
    #if flags['o']:
    #    pfs.append('htc')
    #    v,o = _unpack_from_(_S2F_['htc'],f,o)
    #    d['htc'] = _htctrl_(v)

    # parse out subtype fixed parameters
    if st == ST_MGMT_ASSOC_REQ:
        pfs.append('fixed-params')
        # cability info, listen interval
        fmt = _S2F_['capability'] + _S2F_['listen-int']
        v,o = _unpack_from_(fmt,f,o)
        d['fixed-params'] = {'capability':v[0],
                             'listen-int':v[1]}
    elif st == ST_MGMT_ASSOC_RESP or st == ST_MGMT_REASSOC_RESP:
        # capability info, status code and association id (only uses 14 lsb)
        pfs.append('fixed-params')
        fmt = _S2F_['capability'] + _S2F_['status-code'] + _S2F_['aid']
        v,o = _unpack_from_(fmt,f,o)
        d['fixed-params'] = {'capability':v[0],
                             'status-code':v[1],
                             'aid':leastx(14,v[2])}
    elif st == ST_MGMT_REASSOC_REQ:
        # TODO: test this
        pfs.append('fixed-params')
        fmt = _S2F_['capability'] + _S2F_['listen-int'] + _S2F_['addr']
        v,o = _unpack_from_(fmt,f,o)
        d['fixed-params'] = {'capability':v[0],
                             'listen-int':v[1],
                             'current-ap':_macaddr_(v[2:])}
    elif st == ST_MGMT_PROBE_REQ:
        pass # all fields are information elements
    elif st == ST_MGMT_TIMING_ADV:
        pfs.append('fixed-params')
        fmt = _S2F_['timestamp'] + _S2F_['capability']
        v,o = _unpack_from_(fmt,f,o)
        d['fixed-params'] = {'timestamp':v[0],'capability':v[1]}
    elif st == ST_MGMT_PROBE_RESP or st == ST_MGMT_BEACON:
        pfs.append('fixed-params')
        fmt = _S2F_['timestamp'] + _S2F_['beacon-int'] + _S2F_['capability']
        v,o = _unpack_from_(fmt,f,o)
        d['fixed-params'] = {'timestamp':v[0],
                             'beacon-int':v[1]*1024, # return in microseconds
                             'capability':v[2]}
    elif st == ST_MGMT_DISASSOC or st == ST_MGMT_DEAUTH:
        pfs.append('fixed-params')
        v,o = _unpack_from_(_S2F_['reason-code'],f,o)
        d['fixed-params'] = {'reason-code':v}
    elif st == ST_MGMT_AUTH:
        pfs.append('fixed-params')
        fmt = _S2F_['algorithm-no'] + _S2F_['auth-seq'] + _S2F_['status-code']
        v,o = _unpack_from_(fmt,f,o)
        d['fixed-params'] = {'algorithm-no':v[0],
                             'auth-seq':v[1],
                             'status-code':v[2]}
    elif st == ST_MGMT_ACTION or st == ST_MGMT_ACTION_NOACK:
        # TODO: parse out elements, verifynoack is the same
        pfs.append('fixed-params')
        fmt = _S2F_['category'] + _S2F_['action']
        v,o = _unpack_from_(fmt,f,o)
        d['fixed-params'] = {'category':v[0],'action':v[1]}

        # store the action element(s)
        if o < len(f):
            pfs.append('action-els')
            d['action-el'] = f[o:]
            o = len(f)
    else:
        # ST_MGMT_ATIM, RSRV_7, RSRV_8 or RSRV_15
        return o

    # get information elements if any
    if o < len(f):
        pfs.append('info-elements')
        d['info-elements'] = []
        while o < len(f):
            # info elements may contain tags with the same id, so these are
            # appended as a tuple t = (id,val)
            v,o = _unpack_from_("BB",f,o)
            info = (v[0],f[o:o+v[1]])
            o+= v[1]

            # for certain tags, further parse
            if info[0] == ie.EID_VEND_SPEC:
                # split into tuple (tag,(out,value))
                oui = "-".join(['{0:02X}'.format(a) for a in struct.unpack("=3B",info[1][:3])])
                d['info-elements'].append((info[0],(oui,info[1][3:])))
            elif info[0] == ie.EID_SUPPORTED_RATES or info[0] == ie.EID_EXT_RATES:
                # split into tuple (tag,listofrates) each rate is Mbps
                rates = []
                for rate in info[1]:
                    rates.append(ie.getrate(struct.unpack("=B",rate)[0]))
                d['info-elements'].append((info[0],rates))
            else:
                d['info-elements'].append(info)
    return o

#--> sequence Control Std 8.2.4.4
_SEQCTRL_DIVIDER_ = 4
def _seqctrl_(v): return {'fragno':leastx(_SEQCTRL_DIVIDER_,v),'seqno':mostx(_SEQCTRL_DIVIDER_,v)}

#--> QoS Control field Std 8.2.4.5
# least signficant 8 bits
_QOS_FIELDS_ = {'eosp':(1 << 4),'a-msdu':(1 << 7)}
_QOS_TID_END_          = 4 # BITS 0 - 3
_QOS_ACK_POLICY_START_ = 5 # BITS 5-6
_QOS_ACK_POLICY_LEN_   = 2

# most signficant 8 bits
#                                 |Sent by HC          |Non-AP STA EOSP=0  |Non-AP STA EOSP=1
# --------------------------------|----------------------------------------|----------------
# ST_DATA_QOS_CFPOLL              |TXOP Limit          |                   |
# ST_DATA_QOS_CFACK_CFPOLL        |TXOP Limit          |                   |
# ST_DATA_QOS_DATA_CFACK          |TXOP Limit          |                   |
# ST_DATA_QOS_DATA_CFACK_CFPOLL   |TXOP Limit          |                   |
# ST_DATA_QOS_DATA                |AP PS Buffer State  |TXOP Duration Req  |Queue Size
# ST_DATA_QOS_DATA_CFACK          |AP PS Buffer State  |TXOP Duration Req  |Queue Size
# ST_DATA_QOS_NULL                |AP PS Buffer State  |TXOP Duration Req  |Queue Size
# In Mesh BSS: Mesh Field -> (Mesh Control,Mesh Power Save, RSPI, Reserved
# Othewise Reserved
#
# TXOP Limit:
# TXOP Duration Requested: EOSP bit not set
# AP PS Buffer State:
# Queue Size: sent by non-AP STA with EOSP bit set

# AP PS Buffer State
_QOS_AP_PS_BUFFER_FIELDS = {'rsrv':(1 << 0),'buffer-state-indicated':(1 << 1)}
_QOS_AP_PS_BUFFER_HIGH_PRI_START_ = 2 # BITS 2-3 (corresponds to 10 thru 11)
_QOS_AP_PS_BUFFER_HIGH_PRI_LEN_   = 2
_QOS_AP_PS_BUFFER_AP_BUFF_START_  = 4 # BITS 4-7 (corresponds to 12 thru 15

# Mesh Fields
_QOS_MESH_FIELDS_ = {'mesh-control':(1 << 0),'pwr-save-lvl':(1 << 1),'rspi':(1 << 2)}
_QOS_MESH_RSRV_START_  = 3

def _qosctrl_(v):
    """ parse the qos field from the unpacked values v """
    lsb = v[0] # bits 0-7
    msb = v[1] # bits 8-15

    # bits 0-7 are TID (3 bits), EOSP (1 bit), ACK Policy (2 bits and A-MSDU-present(1 bit)
    qos = bitmask_list(_QOS_FIELDS_,lsb)
    qos['tid'] = leastx(_QOS_TID_END_,lsb)
    qos['ack-policy'] = midx(_QOS_ACK_POLICY_START_,_QOS_ACK_POLICY_LEN_,lsb)

    # bits 8-15 can vary Std Table 8-4
    # TODO: fully parse out the most signficant bits
    qos['txop'] = msb
    return qos

def _qosapbufferstate_(v):
    """ parse the qos ap ps buffer state """
    apps = bitmask_list(_QOS_FIELDS_,v)
    apps['high-pri'] = midx(_QOS_AP_PS_BUFFER_HIGH_PRI_START_,_QOS_AP_PS_BUFFER_HIGH_PRI_LEN_,v)
    apps['ap-buffered'] = mostx(_QOS_AP_PS_BUFFER_AP_BUFF_START_,v)
    return apps

def _qosmesh_(v):
    """ parse the qos mesh fields """
    mf = bitmask_list(_QOS_MESH_FIELDS_,v)
    mf['high-pri'] = mostx(_QOS_MESH_RSRV_START_,v)
    return mf
#--> HT Control field Std 8.2.4.6
_HTC_FIELDS_ = {'lac-rsrv':(1 << 0),
                'lac-trq':(1 << 1),
                'lac-mai-mrq':(1 << 2),
                'ndp-annoucement':(1 << 24),
                'ac-constraint':(1 << 30),
                'rdg-more-ppdu':(1 << 31)}
_HTC_LAC_MAI_MSI_START_      =  3
_HTC_LAC_MAI_MSI_LEN_        =  3
_HTC_LAC_MFSI_START_         =  6
_HTC_LAC_MFSI_LEN_           =  3
_HTC_LAC_MFBASEL_CMD_START_  =  9
_HTC_LAC_MFBASEL_CMD_LEN_    =  3
_HTC_LAC_MFBASEL_DATA_START_ = 12
_HTC_LAC_MFBASEL_DATA_LEN_   =  4
_HTC_CALIBRATION_POS_START_  = 16
_HTC_CALIBRATION_POS_LEN_    =  2
_HTC_CALIBRATION_SEQ_START_  = 18
_HTC_CALIBRATION_SEQ_LEN_    =  2
_HTC_RSRV1_START_            = 20
_HTC_RSRV1_LEN_              =  2
_HTC_CSI_STEERING_START_     = 22
_HTC_CSI_STEERING_LEN_       =  2
_HTC_RSRV2_START_            = 25
_HTC_RSRV2_LEN_              =  5

def _htctrl_(v):
    """
     parse out the htc field from f at offset o, placing values in dict d and
     returning the new offset
    """
    # unpack the 4 octets as a whole and parse out individual components
    htc = bitmask_list(_HTC_FIELDS_,v)
    htc['lac-mai-msi'] = midx(_HTC_LAC_MAI_MSI_START_,_HTC_LAC_MAI_MSI_LEN_,v)
    htc['lac-mfsi'] = midx(_HTC_LAC_MFSI_START_,_HTC_LAC_MFSI_LEN_,v)
    htc['lac-mfbasel-cmd'] = midx(_HTC_LAC_MFBASEL_CMD_START_,_HTC_LAC_MFBASEL_CMD_LEN_,v)
    htc['lac-mfbasel-data'] = midx(_HTC_LAC_MFBASEL_DATA_START_,_HTC_LAC_MFBASEL_DATA_LEN_,v)
    htc['calibration-pos'] = midx(_HTC_CALIBRATION_POS_START_,_HTC_CALIBRATION_POS_LEN_,v)
    htc['calibration-seq'] = midx(_HTC_CALIBRATION_SEQ_START_,_HTC_CALIBRATION_SEQ_LEN_,v)
    htc['rsrv1'] = midx(_HTC_RSRV1_START_,_HTC_RSRV1_LEN_,v)
    htc['csi-steering'] = midx(_HTC_CSI_STEERING_START_,_HTC_CSI_STEERING_LEN_,v)
    htc['rsrv2'] = midx(_HTC_RSRV2_START_,_HTC_RSRV2_LEN_,v)
    return htc

#### Control Frame subfields

#--> Block Ack request Std 8.3.1.8
# BA and BAR Ack Policy|Multi-TID|Compressed BM|Reserved|TID_INFO
#                    B0|       B1|           B2|  B3-B11| B12-B15
# for the ba nad bar information see Std Table 8.16
_BACTRL_ = {'ackpolicy':(1 << 0),'multi-tid':(1 << 1),'compressed-bm':(1 << 2)}
_BACTRL_RSRV_START_     =  3
_BACTRL_RSRV_LEN_       =  9
_BACTRL_TID_INFO_START_ = 12
def _bactrl_(v):
    """ parses the ba/bar control """
    bc = bitmask_list(_BACTRL_,v)
    bc['rsrv'] = midx(_BACTRL_RSRV_START_,_BACTRL_RSRV_LEN_,v)
    bc['tid-info'] = mostx(_BACTRL_TID_INFO_START_,v)
    return bc

#--> Per TID info subfield Std Fig 8-22 and 8-23
_BACTRL_PERTID_DIVIDER_ = 12
_BACTRL_MULTITID_DIVIDER_ = 12
def _pertid_(v):
    """ parses the per tid info and seq control """
    pti = _seqctrl_(v[1])
    pti['pertid-rsrv'] = leastx(_BACTRL_PERTID_DIVIDER_,v[0])
    pti['pertid-tid'] = mostx(_BACTRL_PERTID_DIVIDER_,v[0])
    return pti

#### MGMT Frame subfields

_CAP_INFO_ = {'ess':(1 << 0),
              'ibss':(1 << 1),
              'cfpollable':(1 << 2),
              'cf-poll req':(1 << 3),
              'privacy':(1 << 4),
              'short-pre':(1 << 5),
              'pbcc':(1 << 6),
              'ch-agility':(1 << 7),
              'spec-mgmt':(1 << 8),
              'qos':(1 << 9),
              'time-slot':(1 << 10),
              'apsd':(1 << 11),
              'rdo-meas':(1 << 12),
              'dfss-ofdm':(1 << 13),
              'delayed-ba':(1 << 14),
              'immediate-ba':(1 << 15)}
def cap_info(mn): return bitmask(_CAP_INFO_,mn)
def cap_info_all(mn): return bitmask_list(_CAP_INFO_,mn)
def cap_info_get(mn,f):
    try:
        return bitmask_get(_CAP_INFO_,mn,f)
    except KeyError:
        raise MPDUException("invalid data subtype flag '%s'" % f)