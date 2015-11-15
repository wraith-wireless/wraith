#!/usr/bin/env python
""" wraith
Wireless Reconnaissance And Intelligent Target Harvesting.

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
 numpy 1.9.2

wraith 0.0.2
 desc: iyri,nidus are developmentally sound, begin work on gui
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
 includes:  wraith-rt.py,subpanels.py and wraith.conf (also all subdirectories etc)
 changes:
  GUI:
   - migrated from Tix to ttk
   - implemented command line argument to fully start wraith if desired
   - added a splash panel that initiates services

wraith 0.0.4
 desc: developmental cycle: with two main components, iyri the sensor and nidus
  the storage manager
 includes:  wraith-rt.py, subpanels.py and wraith.conf (also all subdirectories etc)
 changes:
  - added TLS support for encrypted comms betw/ Nidus & DySKT
  - added bulk frame submission
  - added Sessions panel
   o able to view a list of sessions
   o able delete session(s)
  - added polling to check if service's states have changed and updates menus
    accordingly
  - added context menu to right-click on databin buttons (option do nothing as of
    yet)
  - semantic change: made geo flt (front-line trace) as it better describes the data
  - added a manual remove (with rm) of pidfile in iyrid and nidusd to handle
    ubuntu's lack of --remove-pidfile and modified wraith.py (and utilities) as necessary
  - added c2c functionality to iyri

 wraith 0.0.5
  desc: concentration on single-platform system. Remove nidus and allow sensor
  to communicate directly with postgresql.
 includes:  wraith-rt.py, subpanels.py iyri 0.2.0
 changes:
  - added fetchoui to use our own oui file
  - removed nidus service
  - renamed iyri to iyri
  - moved db writes to iyri
  - tried commenting code (specifically functions) better
"""
__name__ = 'wraith'
__license__ = 'GPL v3.0'
__version__ = '0.0.4'
__date__ = 'March 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

#### CONSTANTS

BINS       = "ABCDEFG"                  # data bin ids
IYRILOG    = '/var/log/wraith/iyri.log' # path to iyri log
IYRIPID    = '/var/run/iyrid.pid'       # path to iyri pidfile
WRAITHCONF = 'wraith.conf'              # path to wraith config file
IYRICONF   = 'iyri/iyri.conf'           # path to iyri config file
OUI        = 'data/oui.txt'             # path to oui.txt