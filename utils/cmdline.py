#!/usr/bin/env python
""" cmdline: command line similar functions """

__name__ = 'cmdline'
__license__ = 'GPL v3.0'
__version__ = '0.0.2'
__date__ = 'August 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Production'

import os                         # popen and path functions
import psycopg2 as psql           # postgres API
import subprocess as sp           # subprcess stuff

def runningprocess(process):
    """
     :param process: nme of process
     :returns: the pid(s) of process if running or the empty list
    """
    pids = []
    for proc in os.popen("ps -ef"):
        fields = proc.split()
        if os.path.split(fields[7])[1] == process: pids.append(int(fields[1]))
    return pids

def runningservice(pidfile):
    """
     determines if the service referenced by pidfile is running.
     :param pidfile: path of pid in file
     :returns: process is running
    """
    try:
        with open(pidfile): return True
    except:
        return False

## deprecated
def iyrirunning(pidfile):
    """
     :param pidfile: pidfile of iyri process
     :returns: True if iyri is running otherwise False
    """
    try:
        # open the pid file and check running status with signal = 0
        with open(pidfile) as fin: os.kill(int(fin.read()),0)
        return True
    except (TypeError,IOError,OSError):
        return False

def service(process,pwd=None,start=True):
    """
     starts/stops service

     :param process: process name to start/stop
     :param pwd: sudo pwd (must be supplied if not running as root)
     :param start: start or stop
    """
    state = 'start' if start else 'stop'
    if os.getuid() != 0:
        if pwd is None: raise RuntimeError("service requires pwd to execute")
        cmd = ['sudo','-S','service',process,state]
        p = sp.Popen(cmd,stdout=sp.PIPE,stdin=sp.PIPE,
                     stderr=sp.PIPE,universal_newlines=True)
        _,err = p.communicate(pwd+'\n')
        if err: raise RuntimeError(err)
    else:
        cmd = ['service',process,state]
        p = sp.Popen(cmd,stdout=sp.PIPE,stdin=sp.PIPE,
                     stderr=sp.PIPE,universal_newlines=True)
        _,err = p.communicate()
        if err: raise RuntimeError(err)

def testsudopwd(pwd):
    """
     tests the pwd for sudo rights using a simple sudo ls -l

     :param pwd: pwd to test
    """
    p = sp.Popen(['sudo','-S','ls','-l'],stdout=sp.PIPE,stdin=sp.PIPE,stderr=sp.PIPE,universal_newlines=True)
    out,err = p.communicate(pwd+'\n')
    if out: return True
    return False

def ipaddr():
    """ :returns: local ip address """
    # TODO: not tested on machine w/ multiple connected interfaces
    p = sp.Popen(['hostname','-I'],stdin=sp.PIPE,stdout=sp.PIPE,stderr=sp.PIPE)
    out,err = p.communicate()
    if err: return '127.0.0.1'
    else: return out.strip()

def psqlconnect(c):
    """
     connect to postgresql db with connect string returning connection obj

     :param c: connection string = dict with key->values for keys = 'host',
     'port','db','user','pwd'
     :returns: tuple t = (conn,msg) where conn = None and msg = error string
     on failure otherwise conn = psql connection and msg = ''
    """
    conn = None
    curs = None
    try:
        conn = psql.connect(host=c['host'],port=c['port'],dbname=c['db'],
                            user=c['user'],password=c['pwd'])

        # set to use UTC (side effect of testing the conn string
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