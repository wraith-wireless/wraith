#!/usr/bin/env python

""" mpdu.py: 802.11 mac frame parsing

Parse the 802.11 MAC Protocol Data Unit (MPDU) IAW IEED 802.11-2012
we use Std when referring to IEEE Std 802.11-2012
NOTE:
 It is recommended not to import * as it may cause conflicts with other modules
"""
__name__ = 'mpdu'
__license__ = 'GPL'
__version__ = '0.1.0'
__date__ = 'January 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@hushmail.com'
__status__ = 'Development'

import struct
from binascii import hexlify
from wraith.radio.bits import *
from wraith.radio import infoelement as ie

class MPDUException(Exception): pass                    # generic mpdu exception
class MPDUUninstantiatedException(MPDUException): pass  # class not instantiated
class MPDUInvalidPropertyException(MPDUException): pass # no such property

class MPDU(dict):
    """
     a wrapper class for the underlying mpdu dict
    """
    def __new__(cls,d={}): return super(MPDU,cls).__new__(cls,dict({}))

    #### PROPERTIES

    # The following are the minimum required fields of a mpdu frame
    # and will raise an unistantiated error if not present

    @property
    def length(self):
        try:
            return self['sz']
        except:
            raise MPDUUninstantiatedException

    @property
    def present(self):
        try:
            return self['present']
        except:
            raise MPDUUninstantiatedException

    @property # mpdu vers
    def vers(self):
        try:
            return self['framectrl']['vers']
        except KeyError:
            raise MPDUUninstantiatedException

    @property # mpdu type
    def type(self):
        try:
            return self['framectrl']['type']
        except KeyError:
            raise MPDUUninstantiatedException

    @property # mpdu subtype
    def subtype(self):
        try:
            return self['framectrl']['subtype']
        except KeyError:
            raise MPDUUninstantiatedException

    @property
    def subtype_desc(self):
        try:
            if self.type == FT_MGMT: return ST_MGMT_TYPES[self.subtype]
            elif self.type == FT_CTRL: return ST_CTRL_TYPES[self.subtype]
            elif self.type == FT_DATA: return ST_DATA_TYPES[self.subtype]
            else: return 'rsrv'
        except KeyError:
            raise MPDUUninstantiatedException

    @property
    def flags(self): # mpdu flags
        try:
            return self['framectrl']['flags']
        except KeyError:
            raise MPDUUninstantiatedException

    @property # mpdu duration
    def duration(self):
        try:
            return self['duration']
        except KeyError:
            raise MPDUUninstantiatedException

    @property # mpdu address 1
    def addr1(self):
        try:
            return self['addr1']
        except KeyError:
            raise MPDUUninstantiatedException

    # the following may or may not be present and will return
    # None if not present

    @property
    def addr2(self): return self['addr2'] if 'addr2' in self else None
    @property
    def addr3(self): return self['addr3'] if 'addr3' in self else None
    @property
    def seqctrl(self): return self['seqctrl'] if 'seqctrl' in self else None
    @property
    def addr4(self): return self['addr4'] if 'addr4' in self else None
    @property
    def qosctrl(self): return self['qosctrl'] if 'qosctrl' in self else None
    @property
    def htc(self): return self['htc'] if 'htc' in self else None
    @property
    def fcs(self): return self['fcs'] if 'fcs' in self else None

# SOME CONSTANTS
BROADCAST = "ff:ff:ff:ff:ff:ff" # broadcast address
MAX_MPDU = 7991 # maximum mpdu size in bytes
# index of frame types and string titles
FT_TYPES = ['mgmt','ctrl','data','rsrv']
FT_MGMT              =  0
FT_CTRL              =  1
FT_DATA              =  2
FT_RSRV              =  3
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
        mac = MPDU({'framectrl':{'vers':leastx(2,vs[0]),
                                 'type':midx(2,2,vs[0]),
                                 'subtype':mostx(4,vs[0]),
                                 'flags':fcflags_all(vs[1])},
                    'present':['framectrl'],
                    'sz':offset})

        # unpack duration, address 1
        vs,mac['sz'] = _unpack_from_(_S2F_['duration'] + _S2F_['addr'],frame,mac['sz'])
        mac['present'].extend(['duration','addr1'])
        mac['duration'] = vs[0]
        mac['addr1'] = _macaddr_(vs[1:])

        # remove fcs if present (as some functions will eat all remaining bytes
        if hasFCS:
            mac['fcs'],_ = struct.unpack("=L", frame[-4:])
            frame = frame[:-4]
    except struct.error as e:
        raise MPDUException("Error unpacking minimum: %s" % e)

    # handle frame types separately
    if mac.type == FT_MGMT: _parsemgmt_(frame,mac)
    elif mac.type == FT_CTRL: _parsectrl_(frame,mac)
    elif mac.type == FT_DATA: _parsedata_(frame,mac)
    else:
        raise MPDUException("unresolved type")

    # append the fcs to present if necessar
    if hasFCS: mac['present'].append('fcs')

    # return
    return mac

# Frame Control Flags Std 8.2.4.1.1
# td -> to ds fd -> from ds mf -> more fragments r  -> retry pm -> power mgmt
# md -> more data pf -> protected frame o  -> order
_FC_FLAGS_NAME_ = ['td','fd','mf','r','pm','md','pf','o']
_FC_FLAGS_ = {'td':(1 << 0),'fd':(1 << 1),'mf':(1 << 2),'r':(1 << 3),
               'pm':(1 << 4),'md':(1 << 5),'pf':(1 << 6),'o':(1 << 7)}
def fcflags(mn): return bitmask(_FC_FLAGS_,mn)
def fcflags_all(mn): return bitmask_list(_FC_FLAGS_,mn)
def fcflags_get(mn,f):
    try:
        return bitmask_get(_FC_FLAGS_,mn,f)
    except KeyError:
        raise MPDUException("invalid frame control flag '%s'" % f)

# Std 8.2.4.1.3
# each subtype field bit position indicates a specfic modification of the base data frame

_DATA_SUBTYPE_FIELDS_ = {'cf-ack':(1 << 0),'cf-poll':(1 << 1),
                         'no-body':(1 << 2),'qos':(1 << 3)}
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

## FRAME TYPE PARSING

#--> MGMT Frames Std 8.3.3
def _parsemgmt_(f,mac):
    """ parse the mgmt frame f into the mac dict """
    fmt = _S2F_['addr'] + _S2F_['addr'] + _S2F_['seqctrl']
    v,mac['sz'] = _unpack_from_(fmt,f,mac['sz'])
    mac['addr2'] = _macaddr_(v[0:6])
    mac['addr3'] = _macaddr_(v[6:12])
    mac['seqctrl'] = _seqctrl_(v[-1])
    mac['present'].extend(['addr2','addr3','seqctrl'])

    # HTC fields?
    #if mac.flags['o']:
    #    v,o = _unpack_from_(_S2F_['htc'],f,o)
    #    d['htc'] = _htctrl_(v)
    #    mac['present'].append('htc')

    # parse out subtype fixed parameters
    if mac.subtype == ST_MGMT_ASSOC_REQ:
        # cability info, listen interval
        fmt = _S2F_['capability'] + _S2F_['listen-int']
        v,mac['sz'] = _unpack_from_(fmt,f,mac['sz'])
        mac['fixed-params'] = {'capability':capinfo_all(v[0]),
                               'listen-int':v[1]}
        mac['present'].append('fixed-params')
    elif mac.subtype == ST_MGMT_ASSOC_RESP or mac.subtype == ST_MGMT_REASSOC_RESP:
        # capability info, status code and association id (only uses 14 lsb)
        fmt = _S2F_['capability'] + _S2F_['status-code'] + _S2F_['aid']
        v,mac['sz'] = _unpack_from_(fmt,f,mac['sz'])
        mac['fixed-params'] = {'capability':capinfo_all(v[0]),
                               'status-code':v[1],
                               'aid':leastx(14,v[2])}
        mac['present'].append('fixed-params')
    elif mac.subtype == ST_MGMT_REASSOC_REQ:
        # TODO: test this
        fmt = _S2F_['capability'] + _S2F_['listen-int'] + _S2F_['addr']
        v,mac['sz'] = _unpack_from_(fmt,f,mac['sz'])
        mac['fixed-params'] = {'capability':capinfo_all(v[0]),
                               'listen-int':v[1],
                               'current-ap':_macaddr_(v[2:])}
        mac['present'].append('fixed-params')
    elif mac.subtype == ST_MGMT_PROBE_REQ: pass # all fields are info-elements
    elif mac.subtype == ST_MGMT_TIMING_ADV:
        fmt = _S2F_['timestamp'] + _S2F_['capability']
        v,mac['sz'] = _unpack_from_(fmt,f,mac['sz'])
        mac['fixed-params'] = {'timestamp':v[0],'capability':capinfo_all(v[1])}
        mac['present'].append('fixed-params')
    elif mac.subtype == ST_MGMT_PROBE_RESP or mac.subtype == ST_MGMT_BEACON:
        fmt = _S2F_['timestamp'] + _S2F_['beacon-int'] + _S2F_['capability']
        v,mac['sz'] = _unpack_from_(fmt,f,mac['sz'])
        mac['fixed-params'] = {'timestamp':v[0],
                               'beacon-int':v[1]*1024, # return in microseconds
                               'capability':capinfo_all(v[2])}
        mac['present'].append('fixed-params')
    elif mac.subtype == ST_MGMT_DISASSOC or mac.subtype == ST_MGMT_DEAUTH:
        v,mac['sz'] = _unpack_from_(_S2F_['reason-code'],f,mac['sz'])
        mac['fixed-params'] = {'reason-code':v}
        mac['present'].append('fixed-params')
    elif mac.subtype == ST_MGMT_AUTH:
        fmt = _S2F_['algorithm-no'] + _S2F_['auth-seq'] + _S2F_['status-code']
        v,mac['sz'] = _unpack_from_(fmt,f,mac['sz'])
        mac['fixed-params'] = {'algorithm-no':v[0],
                             'auth-seq':v[1],
                             'status-code':v[2]}
        mac['present'].append('fixed-params')
    elif mac.subtype == ST_MGMT_ACTION or mac.subtype == ST_MGMT_ACTION_NOACK:
        # TODO: parse out elements, verifynoack is the same
        fmt = _S2F_['category'] + _S2F_['action']
        v,mac['sz'] = _unpack_from_(fmt,f,mac['sz'])
        mac['fixed-params'] = {'category':v[0],'action':v[1]}
        mac['present'].append('fixed-params')

        # store the action element(s)
        if mac['sz'] < len(f):
            mac['action-el'] = f[mac['sz']:]
            mac['present'].append('action-els')
            mac['sz'] = len(f)
    else:
        # ST_MGMT_ATIM, RSRV_7, RSRV_8 or RSRV_15
        return

    # get information elements if any
    if mac['sz'] < len(f):
        mac['info-elements'] = []
        mac['present'].append('info-elements')
        while mac['sz'] < len(f):
            # info elements have the structure (see Std 8.4.2.1)
            # Element ID|Length|Information
            #          1      1    variable
            # They may contain tags with the same id, so these are appended
            # as a tuple t = (id,val)
            v,mac['sz'] = _unpack_from_("BB",f,mac['sz'])
            info = (v[0],f[mac['sz']:mac['sz']+v[1]])
            mac['sz'] += v[1]

            # for certain tags, further parse
            if info[0] == ie.EID_VEND_SPEC:
                # split into tuple (tag,(oui,value))
                oui = "-".join(['{0:02X}'.format(a) for a in struct.unpack("=3B",info[1][:3])])
                mac['info-elements'].append((info[0],(oui,info[1][3:])))
            elif info[0] == ie.EID_SUPPORTED_RATES or info[0] == ie.EID_EXT_RATES:
                # split into tuple (tag,listofrates) each rate is Mbps
                rates = []
                for rate in info[1]:
                    rates.append(ie.getrate(struct.unpack("=B",rate)[0]))
                mac['info-elements'].append((info[0],rates))
            else:
                mac['info-elements'].append(info)

#--> CTRL Frames Std 8.3.1
def _parsectrl_(f,mac):
    """ parse the control frame f into the mac dict """
    if mac.subtype == ST_CTRL_CTS or mac.subtype == ST_CTRL_ACK: pass # do nothing
    elif mac.subtype in [ST_CTRL_RTS,ST_CTRL_PSPOLL,ST_CTRL_CFEND,ST_CTRL_CFEND_CFACK]:
        # append addr2 and process macaddress
        v,mac['sz'] = _unpack_from_(_S2F_['addr'],f,mac['sz'])
        mac['addr2'] = _macaddr_(v)
        mac['present'].append('addr2')
    elif mac.subtype == ST_CTRL_BLOCK_ACK_REQ:
        # append addr2,
        v,mac['sz'] = _unpack_from_(_S2F_['addr'],f,mac['sz'])
        mac['addr2'] = _macaddr_(v)
        # & bar control
        v,mac['sz'] = _unpack_from_(_S2F_['barctrl'],f,mac['sz'])
        mac['barctrl'] = _bactrl_(v)
        mac['present'].extend(['addr2','barctrl'])

        # & bar info field
        if not mac['barctrl']['multi-tid']:
            # for 0 0 Basic BlockAckReq and 0 1 Compressed BlockAckReq the
            # bar info field appears to be the same 8.3.1.8.2 and 8.3.1.8.3, a
            # sequence control
            if not mac['barctrl']['compressed-bm']: mac['barctrl']['type'] = 'basic'
            else: mac['barctrl']['type'] = 'compressed'
            v,mac['sz'] = _unpack_from_(_S2F_['seqctrl'],f,mac['sz'])
            mac['barinfo'] = _seqctrl_(v)
        else:
            if not mac['barctrl']['compressed-bm']:
                # 1 0 -> Reserved
                mac['barctrl']['type'] = 'reserved'
                mac['barinfo'] = {'unparsed':hexlify(f[mac['sz']:])}
                mac['sz'] += len(f[mac['sz']:])
            else:
                # 1 1 -> Multi-tid BlockAckReq Std 8.3.1.8.4 See Figures Std 8-22, 8-23
                mac['barctrl']['type'] = 'multi-tid'
                mac['barinfo'] = {'tids':[]}
                for i in xrange(mac['barctrl']['tid-info'] + 1):
                    v,mac['sz'] = _unpack_from_("HH",f,mac['sz'])
                    mac['barinfo']['tids'].append(_pertid_(v))
    elif mac.subtype == ST_CTRL_BLOCK_ACK:
        # add addr2,
        v,mac['sz'] = _unpack_from_(_S2F_['addr'],f,mac['sz'])
        mac['addr2'] = _macaddr_(v)
        # & ba control
        v,mac['sz'] = _unpack_from_(_S2F_['bactrl'],f,mac['sz'])
        mac['bactrl'] = _bactrl_(v)
        mac['present'].extend(['addr2','bactrl'])

        # & ba info field
        if not mac['bactrl']['multi-tid']:
            v,mac['sz'] = _unpack_from_(_S2F_['seqctrl'],f,mac['sz'])
            mac['bainfo'] = _seqctrl_(v)
            if not mac['bactrl']['compressed-bm']:
                # 0 0 -> Basic BlockAck 8.3.1.9.2
                mac['bactrl']['type'] = 'basic'
                mac['bainfo']['babitmap'] = hexlify(f[mac['sz']:mac['sz']+128])
                mac['sz'] += 128
            else:
                # 0 1 -> Compressed BlockAck Std 8.3.1.9.3
                mac['bactrl']['type'] = 'compressed'
                mac['bainfo']['babitmap'] = hexlify(f[mac['sz']:mac['sz']+8])
                mac['sz'] += 8
        else:
            if not mac['bactrl']['compressed-bm']:
                # 1 0 -> Reserved
                mac['bactrl']['type'] = 'reserved'
                mac['bainfo'] = {'unparsed':hexlify(f[mac['sz']:])}
            else:
                # 1 1 -> Multi-tid BlockAck Std 8.3.1.9.4 see Std Figure 8-28, 8-23
                mac['bactrl']['type'] = 'multi-tid'
                mac['bainfo'] = {'tids':[]}
                for i in xrange(mac['bactrl']['tid-info'] + 1):
                    v,mac['sz'] = _unpack_from_("HH",f,mac['sz'])
                    pt = _pertid_(v)
                    pt['babitmap'] = hexlify(f[mac['sz']:mac['sz']+8])
                    mac['bainfo']['tids'].append(pt)
                    mac['sz'] += 8
    elif mac.subtype == ST_CTRL_WRAPPER:
        # Std 8.3.1.10, carriedframectrl is a Frame Control
        v,mac['sz'] = _unpack_from_(_S2F_['framectrl'],f,mac['sz'])
        mac['carriedframectrl'] = v
        v,mac['sz'] = _unpack_from_(_S2F_['htc'],f,mac['sz'])
        mac['htc'] = v
        mac['carriedframe'] = hexlify(f[mac['sz']:])
        mac['sz'] += len(f[mac['sz']:])
        mac['present'].extend(['carriedframectrl','htc','carriedframe'])
    else:
        raise MPDUException("Unknown subtype in CTRL frame %d" % mac.subtype)

#--> DATA Frames Std 8.3.2
def _parsedata_(f,mac):
    """ parse the data frame f into the mac dict """
    # addr2, addr3 and seq. ctrl are always present in data Std Figure 8-30, unpack together
    # (have to remove additional '=' in the individual format strings)
    fmt = _S2F_['addr'] + _S2F_['addr'] + _S2F_['seqctrl']
    v,mac['sz'] = _unpack_from_(fmt,f,mac['sz'])
    mac['addr2'] = _macaddr_(v[0:6])
    mac['addr3'] = _macaddr_(v[6:12])
    mac['seqctrl'] = _seqctrl_(v[-1])
    mac['present'].extend(['addr2','addr3','seqctrl'])

    # fourth address?
    if mac.flags['td'] and mac.flags['fd']:
        v,mac['sz'] = _unpack_from_(_S2F_['addr'],f,mac['sz'])
        mac['addr4'] = _macaddr_(v)
        mac['present'].append('addr4')

    # QoS field?
    if ST_DATA_QOS_DATA <= mac.subtype <= ST_DATA_QOS_CFACK_CFPOLL:
        v,mac['sz'] = _unpack_from_(_S2F_['qos'],f,mac['sz'])
        mac['qos'] = _qosctrl_(v)
        mac['present'].append('qos')

        # HTC fields?
        #if mac.flags['o']:
        #    v,mac['sz'] = _unpack_from_(_S2F_['htc'],f,mac['sz'])
        #    mac['htc'] = _htctrl_(v)
        #    mac['present'].append('htc')

## FRAME FIELDS

#--> sequence Control Std 8.2.4.4
_SEQCTRL_DIVIDER_ = 4
def _seqctrl_(v): return {'fragno':leastx(_SEQCTRL_DIVIDER_,v),
                          'seqno':mostx(_SEQCTRL_DIVIDER_,v)}

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
def capinfo(mn): return bitmask(_CAP_INFO_,mn)
def capinfo_all(mn): return bitmask_list(_CAP_INFO_,mn)
def capinfo_get(mn,f):
    try:
        return bitmask_get(_CAP_INFO_,mn,f)
    except KeyError:
        raise MPDUException("invalid data subtype flag '%s'" % f)