#!/usr/bin/env python

""" constants.py: defines contstants used by iyri
"""
__name__ = 'constants'
__license__ = 'GPL v3.0'
__version__ = '0.0.1'
__date__ = 'August 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

from wraith.wifi.standards.mpdu import MAX_MPDU

# define the m x n array size for the cirular buffer
DIM_M = 1000     # number of rows for memory view
DIM_N = MAX_MPDU # number of cols (bytes)

# iyri states
IYRI_INVALID   = -1 # iyri is unuseable
IYRI_CREATED   =  0 # iyri is created but not yet started
IYRI_RUNNING   =  1 # iyri is currently executing
IYRI_EXITING   =  5 # iyri has finished execution loop
IYRI_DESTROYED =  6 # iyri is destroyed

# tuner states
TUNE_DESC = ['scan','hold','pause','listen']
TUNE_SCAN   = 0
TUNE_HOLD   = 1
TUNE_PAUSE  = 2
TUNE_LISTEN = 3

# numeric constants for internal communications
# IYRI
POISON        =  0 # poison pill
IYRI_INFO     =  1 # info message
IYRI_WARN     =  2 # warning message
IYRI_ERR      =  3 # error message
IYRI_DONE     =  4 # done message - child is exiting
# C2C
CMD_CMD       =  5 # command from user
CMD_ERR       =  6 # command failed
CMD_ACK       =  7 # command succeeded
# internal comms (to collator)
GPS_GPSD      =  8 # gps device details
GPS_FLT       =  9 # frontline trace
THRESH_THRESH = 10 # thresher up/down
THRESH_WARN   = 11 # thresher warning
THRESH_ERR    = 12 # thresher failed
THRESH_DQ     = 13 # thresher popped frame from buffer
THRESH_DONE   = 14 # thresher has finished a frame
RDO_RADIO     = 15 # radio up/down
RDO_FAIL      = 16 # radio failed
RDO_SCAN      = 17 # radio is scanning
RDO_LISTEN    = 18 # radio is listening
RDO_HOLD      = 19 # radio is holding
RDO_PAUSE     = 20 # radio is paused
RDO_SPOOF     = 21 # radio has sppofed mac
RDO_TXPWR     = 22 # radio is transmitting at tx pwr
RDO_STATE     = 23 # radio state requested
RDO_FRAME     = 24 # radio sent frame
# commands to threshers
COL_SID       = 25 # pass the sid
COL_RDO       = 26 # pass radio
COL_WRITE     = 27 # pass write/don't write
COL_FRAME     = 28 # pass frame

# RADIO CONSTANTS string desc corresponds with nidus RADIOSTATE -> these are
# set here to provide a string message for the states
RDO_DESC = {RDO_RADIO:'up/down',RDO_FAIL:'fail',RDO_SCAN:'scan',RDO_LISTEN:'listen',
            RDO_HOLD:'hold',RDO_PAUSE:'pause',RDO_SPOOF:'spoof',RDO_TXPWR:'txpwr',
            RDO_STATE:'state'}