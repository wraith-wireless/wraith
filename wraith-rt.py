#!/usr/bin/env python
""" wraith-rt.py - defines the wraith gui

 TODO:
  1) make tkMessageBox,tkFileDialog and tkSimpleDialog derive match
    main color scheme
  2) Disable menu options as necessary
  3) should we add a Database submenu for options like fix database?
  4) move display of log panel to after intializiation() so that
     wraith panel is 'first', leftmost panel - will have to figure out
     how to save messages from init to later
"""

__name__ = 'wraith-rt'
__license__ = 'GPL'
__version__ = '0.0.3'
__revdate__ = 'February 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@hushmail.com'
__status__ = 'Development'

import os                                  # popen and path functions
import time                                # timestamps
import psycopg2 as psql                    # postgresql api
import Tix                                 # Tix gui stuff
from PIL import Image,ImageTk              # image input & support
import ConfigParser                        # config file parsing
import wraith                              # helpful functions/version etc
import wraith.widgets.panel as gui         # graphics suite
from wraith.utils import bits              # bitmask functions
from wraith.utils.timestamps import ts2iso # timestamp conversions

#### CONSTANTS

_BINS_ = "ABCDEFG" # data bin ids

#### HELPER FUNCTIONS

# returns the pid(s) of process if running or the empty list
def runningprocess(process):
    pids = []
    for proc in os.popen("ps -ef"):
        fields = proc.split()
        if os.path.split(fields[7])[1] == process: pids.append(int(fields[1]))
    return pids

# the following check if nidus/dyskt are running. Because they run under python,
# we cannot use the above, rather check their pid file for a valid pid and just
# in case a pid file was left lying around, verify the pid is still running
# this assumes that a) nidus/dyskt were executed using the service start and
# b) the pid file is stored in /var/run/<name>.pid
def nidusrunning():
    try:
        # open the pid file and check running status with signal = 0
        with open('/var/run/nidusd.pid') as fin: os.kill(int(fin.read()),0)
        return True
    except (TypeError,IOError,OSError):
        return False

def dysktrunning():
    try:
        # open the pid file and check running status with signal = 0
        with open('/var/run/dysktd.pid') as fin: os.kill(int(fin.read()),0)
        return True
    except (TypeError,IOError,OSError):
        return False

##### THE GUI(s)

class SimplePanel(gui.SlavePanel):
    """
     Defines a simple panel with body
     Derived class must implement _body()
    """
    def __init__(self,toplevel,chief,title,iconpath=None):
        gui.SlavePanel.__init__(self,toplevel,chief,iconpath)
        self.master.title(title)
        self.pack(expand=True,fill=Tix.BOTH,side=Tix.TOP)
        self._body()
    def _body(self): raise NotImplementedError("SimplePanel::_body")

class DataBinPanel(SimplePanel):
    """ DataBinPanel - displays a set of data bins for retrieved data storage """
    def __init__(self,toplevel,chief):
        SimplePanel.__init__(self,toplevel,chief,"Databin","widgets/icons/databin.png")

    def donothing(self): pass

    def _body(self):
        """ creates the body """
        self._bins = {}
        frm = Tix.Frame(self)
        frm.pack(side=Tix.TOP,expand=False)

        # add the bin buttons

        for b in _BINS_:
            try:
                self._bins[b] = {'img':ImageTk.PhotoImage(Image.open('widgets/icons/bin%s.png'%b))}
            except:
                self._bins[b] = {'img':None}
                self._bins[b]['btn'] = Tix.Button(frm,text=b,command=self.donothing)
            else:
                self._bins[b]['btn'] = Tix.Button(frm,image=self._bins[b]['img'],command=self.donothing)
            self._bins[b]['btn'].grid(row=0,column=_BINS_.index(b),sticky=Tix.W)

class AboutPanel(SimplePanel):
    """ AboutPanel - displays a simple About Panel """
    def __init__(self,toplevel,chief):
        SimplePanel.__init__(self,toplevel,chief,"About Wraith",None)
    def _body(self):
        frm = Tix.Frame(self)
        frm.pack(side=Tix.TOP,fill=Tix.BOTH,expand=True)
        self.logo = ImageTk.PhotoImage(Image.open("widgets/icons/wraith-banner.png"))
        Tix.Label(frm,bg="white",image=self.logo).grid(row=0,column=0,sticky=Tix.N)
        Tix.Label(frm,
                  text="wraith-rt %s" % wraith.__version__,
                  fg="white",
                  font=("Roman",16,'bold')).grid(row=1,column=0,sticky=Tix.N)
        Tix.Label(frm,
                  text="Wireless assault, reconnaissance, collection and exploitation toolkit").grid(row=2,column=0,sticky=Tix.N)

#### STATE DEFINITIONS
_STATE_INIT_   = 0
_STATE_STORE_  = 1
_STATE_CONN_   = 2
_STATE_NIDUS_  = 3
_STATE_DYSKT_  = 4
_STATE_EXIT_   = 5
_STATE_FLAGS_NAME_ = ['init','store','conn','nidus','dyskt','exit']
_STATE_FLAGS_ = {'init':(1 << 0),   # initialized properly
                 'store':(1 << 1),  # storage instance is running (i.e. postgresql)
                 'conn':(1 << 2),   # connected to storage instance
                 'nidus':(1 << 3),  # nidus storage manager running
                 'dyskt':(1 << 4),  # at least one sensor is collecting data
                 'exit':(1 << 5)}   # exiting/shutting down

class WraithPanel(gui.MasterPanel):
    """ WraithPanel - master panel for wraith gui """
    def __init__(self,toplevel):
        # our variables
        self._conf = None # configuration
        self._state = 0   # bitmask state
        self._conn = None # connection to data storage
        self._pwd = None  # sudo password (should we not save it?)

        # set up super
        gui.MasterPanel.__init__(self,toplevel,"Wraith  v%s" % wraith.__version__,
                                 [],True,"widgets/icons/wraith2.png")

        print self._state

#### OVERRIDES

    @property
    def getstate(self): return self._state

    def _initialize(self):
        """ attempts connect to datastorage server """
        # configure panel & write initial message
        self.tk.wm_geometry("350x3+0+0")
        self.tk.resizable(0,0)
        self.logwrite("Wraith v%s" % wraith.__version__)

        # read in conf file, exit on error
        confMsg = self._readconf()
        if confMsg:
            self.logwrite(confMsg,gui.LOG_ERROR)
            return

        # nidus running?
        if nidusrunning(): self._setstate(_STATE_NIDUS_)

        if dysktrunning(): self._setstate(_STATE_DYSKT_)

        # determine if postgresql is running
        if runningprocess('postgres'):
            # update state
            self._setstate(_STATE_STORE_)

            curs = None
            try:
                # attempt to connect and set state accordingly
                self._conn = psql.connect(host=self._conf['store']['host'],
                                          dbname=self._conf['store']['db'],
                                          user=self._conf['store']['user'],
                                          password=self._conf['store']['pwd'],)

                # set to use UTC and enable CONN flag
                curs = self._conn.cursor()
                curs.execute("set time zone 'UTC';")
                self._conn.commit()

                self.logwrite("Connected to database")
                self._setstate(_STATE_CONN_)
            except psql.OperationalError as e:
                if e.__str__().find('connect') > 0:
                    self.logwrite("PostgreSQL is not running",gui.LOG_WARNING)
                    self._setstate(_STATE_STORE_,False)
                elif e.__str__().find('authentication') > 0:
                    self.logwrite("Authentication string is invalid",gui.LOG_ERROR)
                else:
                    self.logwrite("Unspecified DB error occurred",gui.LOG_ERROR)
                    self._conn.rollback()
            finally:
                if curs: curs.close()
        else:
            self.logwrite("PostgreSQL is not running",gui.LOG_WARNING)

        # set initial state to initialized
        self._setstate(_STATE_INIT_)

        # adjust menu options accordingly
        self._menuenable()

    def _shutdown(self):
        """ if connected to datastorage, closes connection """
        self._setstate(_STATE_EXIT_)
        if self._conn: self._conn.close()

    def _makemenu(self):
        """ make the menu """
        self.menubar = Tix.Menu(self)

        # File Menu
        # all options will always be enabled
        self.mnuWraith = Tix.Menu(self.menubar,tearoff=0)
        self.mnuWraithGui = Tix.Menu(self.mnuWraith,tearoff=0)
        self.mnuWraithGui.add_command(label='Save',command=self.guisave)
        self.mnuWraithGui.add_command(label='Load',command=self.guiload)
        self.mnuWraith.add_cascade(label='Gui',menu=self.mnuWraithGui)
        self.mnuWraith.add_separator()
        self.mnuWraithEdit = Tix.Menu(self.mnuWraith,tearoff=0)
        self.mnuWraithEdit.add_command(label='Preferences',command=self.editprefs)
        self.mnuWraithEdit.add_command(label='Nidus Preferences',
                                       command=self.editdysktprefs)
        self.mnuWraithEdit.add_command(label='DySKT Preferences',
                                       command=self.editnidusprefs)
        self.mnuWraith.add_cascade(label='Edit',menu=self.mnuWraithEdit)
        self.mnuWraith.add_separator()
        self.mnuWraith.add_command(label='Exit',command=self.panelquit)

        # Tools Menu
        # all options will always be enabled
        self.mnuTools = Tix.Menu(self.menubar,tearoff=0)
        self.mnuToolsCalcs = Tix.Menu(self.mnuTools,tearoff=0)
        self.mnuTools.add_cascade(label="Calcuators",menu=self.mnuToolsCalcs)

        # View Menu
        # all options will always be enabled
        self.mnuView = Tix.Menu(self.menubar,tearoff=0)
        self.mnuView.add_command(label='Data Bins',command=self.viewdatabins)
        self.mnuView.add_separator()
        self.mnuView.add_command(label='Data',command=self.viewdata)
        self.mnuView.add_separator()
        self.mnuViewLogs = Tix.Menu(self.mnuView,tearoff=0)
        self.mnuViewLogs.add_command(label='Nidus',command=self.viewniduslog)
        self.mnuViewLogs.add_command(label='DySKT',command=self.viewdysktlog)
        self.mnuView.add_cascade(label='Logs',menu=self.mnuViewLogs)

        # Nidus Menu
        self.mnuNidus = Tix.Menu(self.menubar,tearoff=0)
        self.mnuNidus.add_command(label='Start',command=self.startnidus) # 0
        self.mnuNidus.add_command(label='Stop',command=self.stopnidus)   # 1

        # DySKT Menu
        self.mnuDySKT = Tix.Menu(self.menubar,tearoff=0)
        self.mnuDySKT.add_command(label='Start',command=self.startdyskt)           # 0
        self.mnuDySKT.add_command(label='Stop',command=self.stopdyskt)             # 1
        self.mnuDySKT.add_separator()                                              # 2
        self.mnuDySKT.add_command(label='Control Panel',command=self.dysktctrlpnl) # 3

        # Help Menu
        self.mnuHelp = Tix.Menu(self.menubar,tearoff=0)
        self.mnuHelp.add_command(label='About',command=self.about)
        self.mnuHelp.add_command(label='Help',command=self.help)

        # add the menus
        self.menubar.add_cascade(label='Wraith',menu=self.mnuWraith)
        self.menubar.add_cascade(label="Tools",menu=self.mnuTools)
        self.menubar.add_cascade(label='View',menu=self.mnuView)
        self.menubar.add_cascade(label='Nidus',menu=self.mnuNidus)
        self.menubar.add_cascade(label='DySKT',menu=self.mnuDySKT)
        self.menubar.add_cascade(label='Help',menu=self.mnuHelp)

#### MENU CALLBACKS

    def editprefs(self):
        """ display config file preference editor """
        self.unimplemented()

    def editnidusprefs(self):
        """ display nidus config file preference editor """
        self.unimplemented()

    def editdysktprefs(self):
        """ display dyskt config file preference editor """
        self.unimplemented()

    def viewdatabins(self):
        """ display the data bins panel """
        panel = self.getpanels("databin",False)
        if not panel:
            t = Tix.Toplevel()
            pnl = DataBinPanel(t,self)
            self.addpanel(pnl._name,gui.PanelRecord(t,pnl,"databin"))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

    def viewdata(self):
        """ display data panel """
        self.unimplemented()

    def viewniduslog(self):
        """ display data panel """
        self.unimplemented()

    def viewdysktlog(self):
        """ display data panel """
        self.unimplemented()

    def startnidus(self):
        """ starts database and storage manager """
        pass

    def stopnidus(self):
        """ stops database and storage manager """
        self.unimplemented()

    def startdyskt(self):
        """ starts DySKT sensor """
        self.unimplemented()

    def stopdyskt(self):
        """ stops DySKT sensor """
        self.unimplemented()

    def dysktctrlpnl(self):
        """ displays DySKT Control Panel """
        self.unimplemented()

    def about(self):
        """ display the about panel """
        panel = self.getpanels("about",False)
        if not panel:
            t = Tix.Toplevel()
            pnl = AboutPanel(t,self)
            self.addpanel(pnl._name,gui.PanelRecord(t,pnl,"about"))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

    def help(self):
        """ display the help panel """
        self.unimplemented()

#### MINION METHODS

    def showpanel(self,desc):
        """ opens a panel of type desc """
        if desc == 'log': self.viewlog()
        elif desc == 'databin': self.viewdatabins()
        else: raise RuntimeError, "WTF Cannot open %s" % desc

#### HELPER FUNCTIONS

    def _setstate(self,f,up=True):
        """
         sets internal state's flag f to 1 if up is True or 0 otherwise
        """
        if up:
            self._state = bits.bitmask_set(_STATE_FLAGS_,
                                           self._state,
                                           _STATE_FLAGS_NAME_[f])
        else:
            self._state = bits.bitmask_unset(_STATE_FLAGS_,
                                             self._state,
                                             _STATE_FLAGS_NAME_[f])

    def _readconf(self):
        """ read in configuration file """
        conf = ConfigParser.RawConfigParser()
        if not conf.read("wraith.conf"): return "wraith.conf does not exist"

        self._conf = {}
        try:
            # read in mandatory
            self._conf['store'] = {'host':conf.get('Storage','host'),
                                   'db':conf.get('Storage','db'),
                                   'user':conf.get('Storage','user'),
                                   'pwd':conf.get('Storage','pwd'),
                                   'polite':True,
                                   'shutdown':True}

            # optional
            if conf.has_option('Storage','polite'):
                if conf.get('Storage','polite').lower() == 'off':
                    self._conf['store']['polite'] = False
            if conf.has_option('Storage','shutdown'):
                if conf.get('Storage','shutdown').lower() == 'manual':
                    self._conf['store']['shutdown'] = False


            # return no errors
            return ''
        except (ConfigParser.NoSectionError,ConfigParser.NoOptionError) as e:
            return e

    def _menuenable(self):
        """ enable/disable menus as necessary """
        # get all flags
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)

        # adjust nidus/dyskt menu
        if flags['store'] and flags['conn'] and flags['nidus']:
            # all storage components are 'up'
            self.mnuNidus.entryconfig(0,state=Tix.DISABLED) # start
            self.mnuNidus.entryconfig(1,state=Tix.NORMAL)   # stop

            # we can start,stop,configure dyskt
            self.mnuDySKT.entryconfig(0,state=Tix.NORMAL)  # start
            self.mnuDySKT.entryconfig(1,state=Tix.NORMAL)  # stop
            self.mnuDySKT.entryconfig(3,state=Tix.NORMAL) # ctrl panel
        elif not flags['store'] and not flags['conn'] and not flags['nidus']:
            # no storage component is 'up'
            self.mnuNidus.entryconfig(0,state=Tix.NORMAL)   # start
            self.mnuNidus.entryconfig(1,state=Tix.DISABLED) # stop

            # we cannot do anything with dyskt
            self.mnuDySKT.entryconfig(0,state=Tix.DISABLED)  # start
            self.mnuDySKT.entryconfig(1,state=Tix.DISABLED)  # stop
            self.mnuDySKT.entryconfig(3,state=Tix.DISABLED) # ctrl panel
        else:
            # storage components are in a 'mixed' state
            self.mnuNidus.entryconfig(0,state=Tix.NORMAL) # start
            self.mnuNidus.entryconfig(1,state=Tix.NORMAL) # stop

            # we can start/stop, configure dyskt only if store and nidus are up
            if flags['store'] and flags['nidus']:
                self.mnuDySKT.entryconfig(0,state=Tix.NORMAL)  # start
                self.mnuDySKT.entryconfig(1,state=Tix.NORMAL)  # stop
                self.mnuDySKT.entryconfig(3,state=Tix.NORMAL) # ctrl panel

    def _startstorage(self):
        """ start postgresql db and nidus storage manager """
        pass

    def _stopstorage(self):
        """ stop posgresql db and nidus storage manager """
        pass

    def _getpwd(self):
        """ prompt for sudo password """
        dlg = gui.PasswordDialog(self)
        try:
            # try pwd out on a simple ls sending results to bit bucket
            if os.system("echo '%s' | sudo -k -S %s > /dev/null" % (dlg.pwd,'ls -al')) == 0:
                return dlg.pwd
            else:
                return -1 # bad password
        except AttributeError:
            return None # canceled

if __name__ == 'wraith-rt':
    t = Tix.Tk()
    t.option_add('*foreground','blue')                # normal fg color
    t.option_add('*background','black')               # normal bg color
    t.option_add('*activeBackground','black')         # bg on mouseover
    t.option_add('*activeForeground','blue')          # fg on mouseover
    t.option_add('*disabledForeground','gray')        # fg on disabled widget
    t.option_add('*disabledBackground','black')       # bg on disabled widget
    t.option_add('*troughColor','black')              # trough on scales/scrollbars
    WraithPanel(t).mainloop()