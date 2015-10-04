#!/usr/bin/env python

""" thresh.py: frame and metadata extraction

Saves frames to file (if desired) and frame data/metadata to db.
"""
__name__ = 'thresh'
__license__ = 'GPL v3.0'
__version__ = '0.0.3'
__date__ = 'October 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import os                                   # path/file functions
import signal                               # handle signals
import time                                 # timestamps
import multiprocessing as mp                # multiprocessing
import psycopg2 as psql                     # postgresql api
from wraith.utils.timestamps import ts2iso  # timestamp conversion
from dateutil import parser as dtparser     # parse out timestamps
import wraith.radio.radiotap as rtap        # 802.11 layer 1 parsing
from wraith.radio import mpdu               # 802.11 layer 2 parsing
from wraith.radio import mcs                # mcs functions
from wraith.radio import channels           # 802.11 channels/RFs
from wraith.radio.oui import manufacturer   # oui functions
from wraith.iyri.constants import N        # buffer length

class Thresher(mp.Process):
    """ inserts frames (and saves if specified) in db """
    def __init__(self,comms,q,dbconn,ouis,abad,shama,conf):
        """
         comms - internal communication (to Collator)
         q - task queue from Collator
         dbconn - db connection
         ouis - oui dict
         abad - tuple t = (buffer,writerconn) for the abad radio
         shama - see above
         conf - configuration
        """
        mp.Process.__init__(self)
        self._icomms = comms # communications queue
        self._tasks = q      # connection from Collator
        self._conn = dbconn  # db connection
        self._curs = None    # our cursor
        self._ouis = ouis    # oui dict
        self._a = abad       # abad tuple
        self._s = shama      # shama tuple
        self._stop = False   # stop flag
        self._setup(conf)

    def terminate(self): pass

    def run(self):
        """ execute frame process loop """
        # ignore signals used by main program
        signal.signal(signal.SIGINT,signal.SIG_IGN)   # CTRL-C and kill -INT stop
        signal.signal(signal.SIGTERM,signal.SIG_IGN)  # kill -TERM stop
        signal.signal(signal.SIGUSR1,self.stop)       # kill signal from Collator

        # local variables
        cs = 'thresh-%d' % self.pid # our callsign
        rdos = {}                   # radio map

        # notify collator we're up
        self._icomms.put((cs,ts2iso(time.time()),'!THRESH!',self.pid))

        while not self._stop:
            try:
                # get data and our timestamp
                tkn,ts,d = self._tasks.get()
                ts1 = ts2iso(time.time())

                # process
                if tkn == '!STOP!': self._stop = True
                elif tkn == '!RADIO!':
                    if d[0] == 'abad':
                        rdos[d[1]] = {'buffer':self._a[0],'writer':self._a[1]}
                    elif d[0] == 'shama':
                        rdos[d[1]] = {'buffer':self._s[0],'writer':self._s[1]}
                    else:
                        self._icomms.put((cs,ts1,'!THRESH_WARN!','invalid role %s' % d[0]))
                elif tkn == '!FRAME!':
                    src,ix,l = d
                    print src,ix,l
            except (IndexError,ValueError):
                self._icomms.put((cs,ts1,'!THRESH_WARN!',"invalid arguments for %s" % tkn))
            except KeyError as e:
                self._icomms.put((cs,ts1,'!THRESH_WARN!',"invalid radio mac: %s" % cs))
            except psql.OperationalError as e: # unrecoverable
                self._icomms.put((cs,ts1,'!THRESH_ERR!',"DB. %s: %s" % (e.pgcode,e.pgerror)))
            except psql.Error as e: # possible incorrect semantics/syntax
                self._conn.rollback()
                self._icomms.put((cs,ts1,'!THRESH_WARN!',"SQL. %s: %s" % (e.pgcode,e.pgerror)))

        # notify collector we're down
        self._icomms.put((cs,ts2iso(time.time()),'!THRESH!',None))

    def stop(self,signum=None,stack=None): self._stop = True

    def _setup(self,conf):
        """ initialize """
        try:
            self._curs = self._conn.cursor()
        except psql.Error as e:
            raise RuntimeError(e)
