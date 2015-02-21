#!/usr/bin/env python

""" cmdline: command line similar functions

"""

__name__ = 'cmdline'
__license__ = 'GPL v3.0'
__version__ = '0.0.1'
__date__ = 'February 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Production'

import os               # popen and path functions
import subprocess as sp # Popen

# returns the pid(s) of process if running or the empty list
def runningprocess(process):
    pids = []
    for proc in os.popen("ps -ef"):
        fields = proc.split()
        if os.path.split(fields[7])[1] == process: pids.append(int(fields[1]))
    return pids

# the following checks if nidus/dyskt are running. Because they run under python,
# we cannot use the above, rather check their pid file for a valid pid and just
# in case a pid file was left lying around, verify the pid is still running
# this assumes that a) nidus/dyskt were executed using the service start and
def nidusrunning(pidfile=None):
    if not pidfile: pidfile = '/var/run/nidusd.pid'
    try:
        # open the pid file and check running status with signal = 0
        with open(pidfile) as fin: os.kill(int(fin.read()),0)
        return True
    except (TypeError,IOError,OSError):
        return False

def dysktrunning(pidfile=None):
    if not pidfile: pidfile = '/var/run/dysktd.pid'
    try:
        # open the pid file and check running status with signal = 0
        with open(pidfile) as fin: os.kill(int(fin.read()),0)
        return True
    except (TypeError,IOError,OSError):
        return False

# test sudo password for rights
def testsudopwd(pwd):
    p = sp.Popen(['sudo','-S','ls','-l'],stdout=sp.PIPE,
                                         stdin=sp.PIPE,
                                         stderr=sp.PIPE,
                                         universal_newlines=True)
    out,err=p.communicate(pwd+'\n')
    if out: return True
    return False