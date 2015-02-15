#!/usr/bin/env python
""" wraith-rt.py - defines the wraith gui

 TODO:
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
import wraith.widgets.panel as Panel       # graphics suite
from wraith.utils import bits              # bitmask functions
from wraith.utils.timestamps import ts2iso # timestamp conversions

#### HELPER FUNCTIONS

# returns the pid(s) of process if running or the empty list
def runningprocess(process):
    pids = []
    for proc in os.popen("ps -ef"):
        fields = proc.split()
        if os.path.split(fields[7])[1] == process: pids.append(int(fields[1]))
    return pids

class SimplePanel(Panel.SlavePanel):
    """
     Defines a simple panel with body
     Derived class must implement _body()
    """
    def __init__(self,toplevel,chief,title,iconpath=None):
        Panel.SlavePanel.__init__(self,toplevel,chief,iconpath)
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
        bs = "ABCDEFG"
        for b in bs:
            try:
                self._bins[b] = {'img':ImageTk.PhotoImage(Image.open('widgets/icons/bin%s.png'%b))}
            except:
                self._bins[b] = {'img':None}
                self._bins[b]['btn'] = Tix.Button(frm,text=b,command=self.donothing)
            else:
                self._bins[b]['btn'] = Tix.Button(frm,image=self._bins[b]['img'],command=self.donothing)
            self._bins[b]['btn'].grid(row=0,column=bs.index(b),sticky=Tix.W)

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
_STATE_SENSOR_ = 3
_STATE_EXIT_   = 4
_STATE_FLAGS_NAME_ = ['init','store','conn','sensor','exit']
_STATE_FLAGS_ = {'init':(1 << 0),   # initialized properly
                 'store':(1 << 1),  # storage instance is running (i.e. postgresql)
                 'conn':(1 << 2),   # connected to storage instance
                 'sensor':(1 << 3), # at least one sensor is collecting data
                 'exit':(1 << 4)}   # exiting/shutting down

class WraithPanel(Panel.MasterPanel):
    """ WraithPanel - master panel for wraith gui """
    def __init__(self,toplevel):
        # our variables
        self._conf = None # configuration
        self._state = 0   # bitmask state
        self._conn = None # connection to data storage

        # set up super
        Panel.MasterPanel.__init__(self,toplevel,"Wraith  v%s" % wraith.__version__,
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

        # read in conf file
        confMsg = self._readconf()
        if confMsg:
            self.logwrite(confMsg,Panel.LOG_ERROR)
            return
        self._state = bits.bitmask_set(_STATE_FLAGS_,self._state,
                                       _STATE_FLAGS_NAME_[_STATE_INIT_])

        # determine if postgresql is running, if so attempt connect
        if runningprocess('postgres'):
            self._state = bits.bitmask_set(_STATE_FLAGS_,self._state,
                                           _STATE_FLAGS_NAME_[_STATE_STORE_])
        curs = None
        try:
            # attempt to connect and set state accordingly
            self._conn = psql.connect(host=self._conf['store']['host'],
                                      dbname=self._conf['store']['db'],
                                      user=self._conf['store']['user'],
                                      password=self._conf['store']['pwd'],)
            self.logwrite("Connected to database")
            self._state = bits.bitmask_set(_STATE_FLAGS_,self._state,
                                           _STATE_FLAGS_NAME_[_STATE_CONN_])

            # make connection use UTC
            curs = self._conn.cursor()
            curs.execute("set time zone 'UTC';")
            self._conn.commit()

            # query for running sensors
            sql = """
                   select * from sensor
                   where %s BETWEEN lower(period) and upper(period);
                  """
            curs.execute(sql,(ts2iso(time.time()),))
            if curs.fetchall():
                self._state = bits.bitmask.set(_STATE_FLAGS_,self._state,
                                               _STATE_FLAGS_NAME_[_STATE_SENSOR_])
            else:
                self.logwrite("No running sensors",Panel.LOG_ALERT)
        except psql.OperationalError as e:
            if e.__str__().find('connect') > 0:
                self.logwrite("PostgreSQL is not running",Panel.LOG_ALERT)
                self._state = bits.bitmask_unset(_STATE_FLAGS_,self._state,
                                                 _STATE_FLAGS_NAME_[_STATE_STORE_])
            elif e.__str__().find('authentication') > 0:
                self.logwrite("Authentication string is invalid",Panel.LOG_ERROR)
            else:
                self.logwrite("Unspecified DB error occurred",Panel.LOG_ERROR)
                self._conn.rollback()
        finally:
            if curs: curs.close()

    def _shutdown(self):
        """ if connected to datastorage, closes connection """
        if self._conn: self._conn.close()
    
    def _makemenu(self):
        """ make the menu """
        self.menubar = Tix.Menu(self)
        
        # File Menu
        self.mnuFile = Tix.Menu(self.menubar,tearoff=0)
        self.mnuFile.add_command(label="Exit",command=self.panelquit)
        
        # View Menu
        self.mnuView = Tix.Menu(self.menubar,tearoff=0)
        self.mnuView.add_command(label="Data Bins",command=self.viewdatabins)
        
        # Help Menu
        self.mnuHelp = Tix.Menu(self.menubar,tearoff=0)
        self.mnuHelp.add_command(label="About",command=self.viewabout)
        self.mnuHelp.add_command(label="Help",command=self.viewhelp)
        
        # add the menus
        self.menubar.add_cascade(label="File",menu=self.mnuFile)
        self.menubar.add_cascade(label="View",menu=self.mnuView)
        self.menubar.add_cascade(label="Help",menu=self.mnuHelp)

#### MENU CALLBACKS

    def viewdatabins(self):
        """ display the data bins panel """
        panel = self.getpanels("databin",False)
        if not panel:
            t = Tix.Toplevel()
            pnl = DataBinPanel(t,self)
            self.addpanel(pnl._name,Panel.PanelRecord(t,pnl,"databin"))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

    def viewabout(self):
        """ display the about panel """
        panel = self.getpanels("about",False)
        if not panel:
            t = Tix.Toplevel()
            pnl = AboutPanel(t,self)
            self.addpanel(pnl._name,Panel.PanelRecord(t,pnl,"about"))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

    def viewhelp(self):
        """ display the help panel """
        self.unimplemented()

#### MINION METHODS

    def showpanel(self,desc):
        """ opens a panel of type desc """
        if desc == 'log': self.viewlog()
        elif desc == 'databin': self.viewdatabins()
        else: raise RuntimeError, "WTF Cannot open %s" % desc

#### HELPER FUNCTIONS

    def _readconf(self):
        """ read in configuration file """
        conf = ConfigParser.RawConfigParser()
        if not conf.read("wraith.conf"): return "wraith.conf does not exist"

        self._conf = {}
        try:
            self._conf['store'] = {'host':conf.get('Storage','host'),
                                   'db':conf.get('Storage','db'),
                                   'user':conf.get('Storage','user'),
                                   'pwd':conf.get('Storage','pwd')}
            return ''
        except (ConfigParser.NoSectionError,ConfigParser.NoOptionError) as e:
            return e

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