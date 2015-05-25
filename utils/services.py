#!/usr/bin/env python
""" services.py - defines service start/stop functions

Defines a start/stop functions for services used by the Wraith gui and subcomponents
"""

__name__ = 'services'
__license__ = 'GPL v3.0'
__version__ = '0.0.1'
__date__ = 'May 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import time                                # for sleep
import psycopg2 as psql                    # postgresql api
import wraith                              # version info/constants
from wraith.utils import cmdline           # cmdline functions

def startpsql(pwd):
    """ start postgresl server. pwd: the sudo password """
    try:
        cmdline.service('postgresql',pwd)
        time.sleep(0.5)
        if not cmdline.runningprocess('postgres'): raise RuntimeError
    except RuntimeError:
        return False
    else:
        return True

def stoppsql(pwd):
    """ shut down posgresql. pwd: the sudo password """
    try:
        cmdline.service('postgresql',pwd,False)
        while cmdline.runningprocess('postgres'): time.sleep(0.5)
    except RuntimeError:
        return False
    else:
        return True

def startnidus(pwd):
    """ start nidus server. pwd: the sudo password """
    try:
        cmdline.service('nidusd',pwd)
        time.sleep(0.5)
        if not cmdline.nidusrunning(wraith.NIDUSPID): raise RuntimeError
    except RuntimeError:
        return False
    else:
        return True

def stopnidus(pwd):
    """ stop nidus storage manager. pwd: Sudo password """
    try:
        cmdline.service('nidusd',pwd,False)
        while cmdline.nidusrunning(wraith.NIDUSPID): time.sleep(1.0)
    except RuntimeError as e:
        return False
    else:
        return True

def startdyskt(pwd):
    """ start dyskt sensor. pwd: the sudo password """
    try:
        cmdline.service('dysktd',pwd)
        time.sleep(1.0)
        if not cmdline.dysktrunning(wraith.DYSKTPID): raise RuntimeError
    except RuntimeError:
        return False
    else:
        return True

def stopdyskt(pwd):
    """ stop dyskt sensor. pwd: Sudo password """
    try:
        cmdline.service('dysktd',pwd,False)
        while cmdline.nidusrunning(wraith.DYSKTPID): time.sleep(1.0)
    except RuntimeError as e:
        return False
    else:
        return True

def psqlconnect(c):
    """
     connect to postgresql db with connect string
     c: a dict with key->value pairs for 'host', 'port', 'db', 'user' and 'pwd'
     returns a tuple (conn,msg) where conn = None and msg = error string
     on failure otherwise conn = psql connection and msg = ''
    """
    conn = None
    curs = None
    try:
        # connect and create a cursor to set UTC time zone for connection
        conn = psql.connect(host=c['host'],port=c['port'],dbname=c['db'],
                            user=['user'],password=c['pwd'])
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