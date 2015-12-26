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

from wraith.wifi.mpdu import MAX_MPDU

# define the m x n array size for the cirular buffer
DIM_M = 1000     # number of rows for memory view
DIM_N = MAX_MPDU # number of cols (bytes)

# thresher constants
#MIN_THRESH =  5 # minimum (and initial) number of threshers
#MAX_THRESH = 15 # maximum number of threshers
#WRK_THRESH = 50 # no more the WRK_THRESH outstanding frames per thresher

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

# path for oui text file
#OUIPATH = '../data/oui.txt'

# numeric constants for internal communications
# IYRI
POISON        =  0 # poison pill
IYRI_INFO     =  1 # info message
IYRI_WARN     =  2 # warning message
IYRI_ERR      =  3 # error message
# C2C
CMD_CMD       =  4 # command from user
CMD_ERR       =  5 # command failed
CMD_ACK       =  6 # command succeeded
# internal comms (to collator)
GPS_GPSD      =  7 # gps device details
GPS_FLT       =  8 # frontline trace
THRESH_THRESH =  9 # thresher up/down
THRESH_WARN   = 10 # thresher warning
THRESH_ERR    = 11 # thresher failed
THRESH_DONE   = 12 # thresher has finiahed a frame
RDO_RADIO     = 13 # radio up/down
RDO_FAIL      = 14 # radio failed
RDO_SCAN      = 15 # radio is scanning
RDO_LISTEN    = 16 # radio is listening
RDO_HOLD      = 17 # radio is holding
RDO_PAUSE     = 18 # radio is paused
RDO_SPOOF     = 19 # radio has sppofed mac
RDO_TXPWR     = 20 # radio is transmitting at tx pwr
RDO_STATE     = 21 # radio state requested
RDO_FRAME     = 22 # radio sent frame
# commands to threshers
COL_SID       = 23 # pass the sid
COL_RDO       = 24 # pass radio info
COL_WRITE     = 25 # pass write/don't write
COL_FRAME     = 26 # pass frame

# RADIO CONSTANTS string desc corresponds with nidus RADIOSTATE
RDO_DESC = {RDO_RADIO:'up/down',RDO_FAIL:'fail',RDO_SCAN:'scan',RDO_LISTEN:'listen',
            RDO_HOLD:'hold',RDO_PAUSE:'pause',RDO_SPOOF:'spoof',RDO_TXPWR:'txpwr',
            RDO_STATE:'state'}