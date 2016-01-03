#!/usr/bin/env python

""" rdoctl.py: Radio Controller

An interface to an underlying radio (wireless nic). Tunes and sniffs a radio,
forwarding data to the Collator.
"""
__name__ = 'tuner'
__license__ = 'GPL v3.0'
__version__ = '0.0.1'
__date__ = 'December 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

from time import time                      # timestamps
import signal                              # handling signals
import multiprocessing as mp               # for Process
from wraith.wifi import iw                 # iw command line interface
from wraith.utils.timestamps import ts2iso # time stamp conversion
from wraith.iyri.constants import *        # tuner states & buffer dims

class Tuner(mp.Process):
    """ tune' the radio's channel and width """
    def __init__(self,q,conn,iface,scan,dwell,i,state=TUNE_SCAN):
        """
         :param q: msg queue from us to RadioController
         :param conn: token connnection from iyri
         :param iface: interface name of card
         :param scan: scan list of channel tuples (ch,chw)
         :param dwell: dwell list. for each i stay on ch in scan[i] for dwell[i]
         :param i: initial channel index
         :param state: initial state oneof {TUNE_PAUSE|TUNE_SCAN}
        """
        mp.Process.__init__(self)
        self._state = state # initial state paused or scanning
        self._qR = q        # event queue to RadioController
        self._cI = conn     # connection from Iyri to tuner
        self._vnic = iface  # this radio's vnic
        self._chs = scan    # scan list
        self._ds = dwell    # corresponding dwell times
        self._i = i         # initial/current index into scan/dwell

    def terminate(self): pass

    @property
    def channel(self):
        return '{0}:{1}'.format(self._chs[self._i][0],self._chs[self._i][1])

    def run(self):
        """ switch channels based on associted dwell times """
        # ignore signals being used by main program
        signal.signal(signal.SIGINT,signal.SIG_IGN)
        signal.signal(signal.SIGTERM,signal.SIG_IGN)

        # starting paused or scanning?
        ts = ts2iso(time())
        if self._state == TUNE_PAUSE: self._qR.put((RDO_PAUSE,ts,[-1,' ']))
        else: self._qR.put((RDO_SCAN,ts,[-1,self._chs]))

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
            if self._cI.poll(to): # we hold on the iyri connection
                tkn = self._cI.recv()
                ts = time()

                # tokens will have 2 flavor's POISON and 'cmd:cmdid:params'
                # where params is empty (for POISON) or a '-' separated list
                if tkn == POISON:
                    # for a POISON, quit and notify the RadioController
                    self._qR.put((POISON,ts2iso(ts),[-1,' ']))
                    break
                else:
                    # calculate time remaining for this channel
                    if not remaining: remaining = self._ds[self._i] - (ts-ts1)
                    else: remaining -= (ts-ts1)

                    # parse the requested command
                    try:
                        cmd,cid,ps = tkn.split(':') # force into 3 components
                        cid = int(cid)
                    except: pass
                    else:
                        if cmd == 'state':
                            state = TUNE_DESC[self._state]
                            self._qR.put((RDO_STATE,ts2iso(ts),[cid,state]))
                        elif cmd == 'scan':
                            if self._state != TUNE_SCAN:
                                self._state = TUNE_SCAN
                                self._qR.put((RDO_SCAN,ts2iso(ts),[cid,self._chs]))
                            else:
                                err = "redundant command"
                                self._qR.put((CMD_ERR,ts2iso(ts),[cid,err]))
                        elif cmd == 'txpwr':
                            err = "not currently supported"
                            self._qR.put((RDO_HOLD,ts2iso(ts),[cid,err]))
                        elif cmd == 'spoof':
                            err = "not currently supported"
                            self._qR.put((RDO_HOLD,ts2iso(ts),[cid,err]))
                        elif cmd == 'hold':
                            if self._state != TUNE_HOLD:
                                self._state = TUNE_HOLD
                                self._qR.put((RDO_HOLD,ts2iso(ts),[cid,self.channel]))
                            else:
                                err = "redundant command"
                                self._qR.put((CMD_ERR,ts2iso(ts),[cid,err]))
                        elif cmd == 'pause':
                            if self._state != TUNE_PAUSE:
                                self._state = TUNE_PAUSE
                                self._qR.put((RDO_PAUSE,ts2iso(ts),[cid,self.channel]))
                            else:
                                err = "redundant command"
                                self._qR.put((CMD_ERR,ts2iso(ts),[cid,err]))
                        elif cmd == 'listen':
                            # for listen, ignore reduandacies as some other
                            # process may have changed the channel
                            try:
                                ch,chw = ps.split('-')
                                if chw == 'None': chw = None
                                iw.chset(self._vnic,ch,chw)
                                self._state = TUNE_LISTEN
                                details = "{0}:{1}".format(ch,chw)
                                self._qR.put((RDO_LISTEN,ts2iso(ts),[cid,details]))
                            except ValueError:
                                err = "invalid param format"
                                self._qR.put((CMD_ERR,ts2iso(ts),[cid,err]))
                            except iw.IWException as e:
                                self._qR.put((CMD_ERR,ts2iso(ts),[cid,str(e)]))
                        else:
                            err = "invalid command {0}".format(cmd)
                            self._qR.put((CMD_ERR,ts2iso(ts),[cid,err]))
            else:
                try:
                    # no token, go to next channel, reset remaining
                    self._i = (self._i+1) % len(self._chs)
                    iw.chset(self._vnic,self._chs[self._i][0],self._chs[self._i][1])
                    remaining = 0 # reset remaining timeout
                except iw.IWException as e:
                    self._qR.put((RDO_FAIL,ts2iso(time()),[-1,e]))
                except Exception as e: # blanket exception
                    self._qR.put((RDO_FAIL,ts2iso(time()),[-1,e]))

