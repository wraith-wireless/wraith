#!/usr/bin/env python

""" tuner.py: Radio scanner

Handles switching channels on the radio as specified by parameters in the
config file. Will additionally process any user-specified commands.
"""
__name__ = 'tuner'
__license__ = 'GPL v3.0'
__version__ = '0.0.1'
__date__ = 'December 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

from time import time                              # timestamps/timing metrics
import signal                                      # handling signals
import multiprocessing as mp                       # for Process
import pyric                                       # pyric error
from pyric import pyw                              # and nic functions
from wraith.utils.timestamps import isots, ts2iso # time stamp conversion
from wraith.iyri.constants import *               # tuner states & buffer dims

class Tuner(mp.Process):
    """ tune' the radio's channel and width """
    def __init__(self,q,conn,rdo,scan,dwell,i,state=TUNE_SCAN):
        """
         :param q: msg queue from us to RadioController
         :param conn: token connnection from iyri
         :param rdo: the radio
         :param scan: scan list of channel tuples (ch,chw)
         :param dwell: dwell list. for each i stay on ch in scan[i] for dwell[i]
         :param i: initial channel index
         :param state: initial state oneof {TUNE_PAUSE|TUNE_SCAN}
        """
        mp.Process.__init__(self)
        self._state = state # initial state paused or scanning
        self._qR = q        # event queue to RadioController
        self._cI = conn     # connection from Iyri to tuner
        self._rdo = rdo     # the radio
        self._chs = scan    # scan list
        self._ds = dwell    # corresponding dwell times
        self._i = i         # initial/current index into scan/dwell

    def terminate(self): pass

    @property # current channel
    def channel(self):
        return '{0}:{1}'.format(self._chs[self._i][0],self._chs[self._i][1])

    @property # current state information
    def meta(self):
        # need channel, txpwr, current state
        return "{0} ch {1} txpwr {2}".format(TUNE_DESC[self._state],
                                             self.channel,
                                             self._rdo.txpwr)

    def run(self):
        """ switch channels based on associted dwell times """
        # ignore signals being used by main program
        signal.signal(signal.SIGINT,signal.SIG_IGN)
        signal.signal(signal.SIGTERM,signal.SIG_IGN)

        # starting paused or scanning?
        if self._state == TUNE_PAUSE: self._qR.put((RDO_PAUSE,isots(),[-1,' ']))
        else: self._qR.put((RDO_SCAN,isots(),[-1,self._chs]))

        # execution loop - wait on the internal connection for each channels
        # dwell time. IOT avoid a state where we would continue to scan the same
        # channel, i.e. 'state' commands, use a remaining time counter
        remaining = 0       # remaining dwell time counter
        dwell = self._ds[0] # save original dwell time
        while True:
            # set the poll timeout to remaining if we need to finish this scan
            # or to None if we are in a static state
            if self._state in [TUNE_PAUSE,TUNE_HOLD,TUNE_LISTEN]: to = None
            else: to = self._ds[self._i] if not remaining else remaining

            ts1 = time() # get timestamp
            if self._cI.poll(to): # we hold on the iyri connection during poll time
                tkn = self._cI.recv()
                ts = time()

                # tokens will have 2 flavor's POISON and 'cmd:cmdid:params'
                # where params is empty (for POISON) or a '-' separated list
                if tkn == POISON:
                    # for a POISON, quit and notify the RadioController
                    self._qR.put((POISON,ts2iso(ts),[-1,' ']))
                    break

                # calculate time remaining for this channel
                if not remaining: remaining = self._ds[self._i] - (ts-ts1)
                else: remaining -= (ts-ts1)

                # parse the requested command
                cmd,cid,ps = tkn.split(':') # force into 3 components
                cid = int(cid)              # & convert id to int
                if cmd == 'state':
                    self._qR.put((RDO_STATE,ts2iso(ts),[cid,self.meta]))
                elif cmd == 'scan':
                    if self._state != TUNE_SCAN:
                        self._state = TUNE_SCAN
                        self._qR.put((RDO_SCAN,ts2iso(ts),[cid,self._chs]))
                    else:
                        self._qR.put((CMD_ERR,ts2iso(ts),[cid,"redundant cmd"]))
                elif cmd == 'txpwr':
                    err = "txpwr not currently supported"
                    self._qR.put((CMD_ERR,ts2iso(ts),[cid,err]))
                elif cmd == 'spoof':
                    err = "spoof not currently supported"
                    self._qR.put((CMD_ERR,ts2iso(ts),[cid,err]))
                elif cmd == 'hold':
                    if self._state != TUNE_HOLD:
                        self._state = TUNE_HOLD
                        self._qR.put((RDO_HOLD,ts2iso(ts),[cid,self.channel]))
                    else:
                        self._qR.put((CMD_ERR,ts2iso(ts),[cid,"redundant cmd"]))
                elif cmd == 'pause':
                    if self._state != TUNE_PAUSE:
                        self._state = TUNE_PAUSE
                        self._qR.put((RDO_PAUSE,ts2iso(ts),[cid,self.channel]))
                    else:
                        self._qR.put((CMD_ERR,ts2iso(ts),[cid,"redundant cmd"]))
                elif cmd == 'listen':
                    if self._state != TUNE_LISTEN:
                        try:
                            ch,chw = ps.split('-')
                            if chw == 'None': chw = None
                            self._rdo.setch(ch,chw)
                            self._state = TUNE_LISTEN
                            details = "{0}:{1}".format(ch,chw)
                            self._qR.put((RDO_LISTEN,ts2iso(ts),[cid,details]))
                        except ValueError:
                            err = "invalid param format"
                            self._qR.put((CMD_ERR,ts2iso(ts),[cid,err]))
                        except radio.RadioException as e:
                            self._qR.put((CMD_ERR,ts2iso(ts),[cid,str(e)]))
                    else:
                        self._qR.put((CMD_ERR,ts2iso(ts),[cid,"redundant cmd"]))
                else:
                    err = "invalid command {0}".format(cmd)
                    self._qR.put((CMD_ERR,ts2iso(ts),[cid,err]))
            else:
                try:
                    # no token, go to next channel, reset remaining
                    self._i = (self._i+1) % len(self._chs)
                    self._rdo.setch(self._chs[self._i][0],self._chs[self._i][1])
                    remaining = 0 # reset remaining timeout
                except radio.RadioException as e:
                    self._qR.put((RDO_FAIL,isots(),[-1,e]))
                except Exception as e: # blanket exception
                    self._qR.put((RDO_FAIL,isots(),[-1,e]))