#!/usr/bin/env python
""" cmdline: command line similar functions """

__name__ = 'cmdline'
__license__ = 'GPL v3.0'
__version__ = '0.0.1'
__date__ = 'February 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Production'

import os                         # popen and path functions
import psycopg2 as psql           # postgres API
from subprocess import Popen,PIPE # execute process

def runningprocess(process):
    """ returns the pid(s) of process if running or the empty list """
    pids = []
    for proc in os.popen("ps -ef"):
        fields = proc.split()
        if os.path.split(fields[7])[1] == process: pids.append(int(fields[1]))
    return pids

def nidusrunning(pidfile):
    """
     the following checks if nidus is running. Because it runs under python,
     we cannot use ps easily, rather check the pidfile for a valid pid. Assumes
     that nidus was executed using the service start
    """
    try:
        # open the pid file and check running status with signal = 0
        with open(pidfile) as fin: os.kill(int(fin.read()),0)
        return True
    except (TypeError,IOError,OSError):
        return False

def dysktrunning(pidfile):
    """ see nidusrunning """
    try:
        # open the pid file and check running status with signal = 0
        with open(pidfile) as fin: os.kill(int(fin.read()),0)
        return True
    except (TypeError,IOError,OSError):
        return False

def service(process,pwd,start=True):
    """
     executes 'service process arg1' as sudo if pwd with arg1 =
    'start' if start is True otherwise 'stop'
    """
    state = 'start' if start else 'stop'
    cmd = ['sudo','-S','service',process,state]
    p = Popen(cmd,stdout=PIPE,stdin=PIPE,stderr=PIPE,universal_newlines=True)
    _,err = p.communicate(pwd+'\n')
    if err: raise RuntimeError(err)

def testsudopwd(pwd):
    """ tests the pwd for sudo rights using a simple sudo ls -l """
    p = Popen(['sudo','-S','ls','-l'],stdout=PIPE,stdin=PIPE,stderr=PIPE,universal_newlines=True)
    out,err = p.communicate(pwd+'\n')
    if out: return True
    return False

def psqlconnect(c):
    """
     connect to postgresql db with connect string returning connection obj
     c: a dict with key->values for keys: 'host','port','db','user','pwd'
     returns a tuple (conn,msg) where conn = None and msg = error string
     on failure otherwise conn = psql connection and msg = ''
    """
    conn = None
    curs = None
    try:
        conn = psql.connect(host=c['host'],port=c['port'],dbname=c['db'],
                            user=c['user'],password=c['pwd'])

        # set to use UTC
        curs = conn.cursor()
        curs.execute("set time zone 'UTC';")
    except psql.OperationalError as e:
        if e.__str__().find('connect') > 0:
            err = "PostgreSQL is not running"
        elif e.__str__().find('authentication') > 0:
            err = "Authentication string is invalid"
        else:
            err = "Unspecified DB error occurred"
            conn.rollback()
        return None,err
    else:
        conn.commit()
        return conn,''
    finally:
        if curs: curs.close()