#!/usr/bin/env python
""" wraith
Wireless Reconnaissance And Intelligent Target Harvesting.

Requires:
 linux (preferred 3.x kernel)
 Python 2.7
 PyRIC >= 1.5
 postgresql 9.x (tested on 9.3.5)
 pyscopg 2.5.3
 mgrs 1.3.1 (works w/ 1.1)
 dateutil 2.3
 PIL (python-pil,python-imaging-tk,tk8.5-dev tcl8.5-dev) NOTE: I had to unistall
  python-pil and reinstall after installing tk8.5 and tcl8.5
 numpy 1.9.2

"""
__name__ = 'wraith'
__license__ = 'GPL v3.0'
__version__ = '0.0.7'
__date__ = 'July 2016'
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
OUIPATH    = 'data/oui.txt'             # path to oui.txt
