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
 includes: wraith-rt.py and wraith.conf (also all subdirectories etc)
 changes:
  - added extraction of all management frames (excluding timing adv)
  - added nidusd daemon file to start nidus server

 TODO:
  1) tried --remove-pid/--remove-pidfile to remove pids of dysktd and nidusd
     from /var/run but does not work - figure out how to delete the pidfile
     on daemon exit
"""
__name__ = 'wraith'
__license__ = 'GPL v3.0'
__version__ = '0.0.2'
__date__ = 'February 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'
