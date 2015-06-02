#!/usr/bin/env python
""" wraith
Wireless assault, reconnaissance, collection and exploitation toolkit.

Requires:
 linux (preferred 3.x kernel)
 Python 2.7
 iw 3.17 (can be made to work w/ 3.2
 postgresql 9.x (tested on 9.3.5)
 pyscopg 2.5.3
 mgrs 1.3.1 (works w/ 1.1)
 dateutil 2.3
 PIL (python-pil,python-imaging-tk,tk8.5-dev tcl8.5-dev) NOTE: I had to unistall
  python-pil and reinstall after installing tk8.5 and tcl8.5

wraith 0.0.2
 desc: dyskt,nidus are developmentally sound, begin work on gui
 includes: wraith-rt. py,subpanels.py and wraith.conf (also all subdirectories etc)
 changes:
  GUI:
   - added multiple panels for non-data related functionality
     o start/stop services
     o log viewing
     o conversion/calculation panels
     o interfaces panel
   - started work on the query panel

wraith 0.0.3
 desc: non-data panels are completed (excluding Help)
 includes:  wraith-rt. py,subpanels.py and wraith.conf (also all subdirectories etc)
 changes:
  GUI:
   - migrated from Tix to ttk
   - implemented command line argument to fully start wraith if desired
   - added a splash panel that initiates services

wraith 0.0.4
 desc: developmental cycle
 includes:  wraith-rt.py, subpanels.py and wraith.conf (also all subdirectories etc)
 changes:
  - added TLS support for encrypted comms betw/ Nidus & DySKT
  - added bulk frame submission
  - added Sessions panel
   o able to view a list of sessions
   o able delete session(s)
  - added polling to check if service states have changed and updates menus
    accordingly
  - added context menu to right-click on databin buttons (option do nothing as of
    yet
"""
__name__ = 'wraith'
__license__ = 'GPL v3.0'
__version__ = '0.0.4'
__date__ = 'March 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import os

#### CONSTANTS

BINS = "ABCDEFG"                         # data bin ids
NIDUSLOG   = '/var/log/wraith/nidus.log' # path to nidus log
DYSKTLOG   = '/var/log/wraith/dyskt.log' # path to dyskt log
NIDUSPID   = '/var/run/nidusd.pid'       # path to nidus pidfile
DYSKTPID   = '/var/run/dysktd.pid'       # path to dyskt pidfile
WRAITHCONF = 'wraith.conf'               # path to wraith config file
NIDUSCONF  = 'nidus/nidus.conf'          # path to nidus config file
DYSKTCONF  = 'dyskt/dyskt.conf'          # path to dyskt config file
# path to tls cert,key
NIDUSCERT  = os.path.join(os.path.dirname(os.path.abspath(__file__)),'nidus.cert')
NIDUSKEY   = os.path.join(os.path.dirname(os.path.abspath(__file__)),'nidus.key')