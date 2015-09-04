#!/usr/bin/env python
""" wraith-rt.py - defines the Master(main) Panel of the wraith gui
"""

#__name__ = 'wraith-rt'
__license__ = 'GPL v3.0'
__version__ = '0.0.4'
__revdate__ = 'May 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import os                                  # file info etc
import sys                                 # for exit
import time                                # sleeping, timestamps
import psycopg2 as psql                    # postgresql api
#import psycopg2.extras as pextras          # cursors and such
import Tkinter as tk                       # gui constructs
import ttk                                 # ttk widgets
from PIL import Image,ImageTk              # image input & support
import ConfigParser                        # config file parsing
import argparse                            # cmd line arguments
import getpass                             # get sudo password
import wraith                              # version info/constants
import wraith.widgets.panel as gui         # graphics suite
import wraith.subpanels as subgui          # our subpanels
from wraith.utils import bits              # bitmask functions
from wraith.utils import cmdline           # command line stuff

# server/services functions shared by splash and main panel

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
        if not cmdline.runningservice(wraith.NIDUSPID): raise RuntimeError
    except RuntimeError:
        return False
    else:
        return True

def stopnidus(pwd):
    """ stop nidus storage manager. pwd: Sudo password """
    try:
        cmdline.service('nidusd',pwd,False)
        while cmdline.runningservice(wraith.NIDUSPID): time.sleep(1.0)
    except RuntimeError as e:
        return False
    else:
        return True

def startiyri(pwd):
    """ start Iyri sensor. pwd: the sudo password """
    try:
        cmdline.service('Iyrid',pwd)
        time.sleep(1.0)
        if not cmdline.runningservice(wraith.LYRIPID): raise RuntimeError
    except RuntimeError:
        return False
    else:
        return True

def stopIyri(pwd):
    """ stop Iyri sensor. pwd: Sudo password """
    try:
        cmdline.service('Iyrid',pwd,False)
        while cmdline.runningservice(wraith.LYRIPID): time.sleep(1.0)
    except RuntimeError as e:
        return False
    else:
        return True

def readconf():
    """ read in configuration file """
    cp = ConfigParser.RawConfigParser()
    if not cp.read("wraith.conf"): return "wraith.conf does not exist"

    conf = {}
    try:
        ## STORAGE
        conf['store'] = {'host':cp.get('Storage','host'),
                         'port':cp.getint('Storage','port'),
                         'db':cp.get('Storage','db'),
                         'user':cp.get('Storage','user'),
                         'pwd':cp.get('Storage','pwd')}

        ## POLICY
        conf['policy'] = {'polite':True,'shutdown':True}

        if cp.has_option('Policy','polite'):
            if cp.get('Policy','polite').lower() == 'off':
                conf['policy']['polite'] = False
        if cp.has_option('Policy','shutdown'):
            if cp.get('Policy','shutdown').lower() == 'manual':
                conf['policy']['shutdown'] = False

        # return no errors
        return conf
    except (ConfigParser.NoSectionError,ConfigParser.NoOptionError) as e:
        return {'err':e.__str__()}

#### STATE DEFINITIONS
_STATE_INIT_   = 0
_STATE_STORE_  = 1
_STATE_CONN_   = 2
_STATE_NIDUS_  = 3
_STATE_LYRI_  = 4
_STATE_EXIT_   = 5
_STATE_FLAGS_NAME_ = ['init','store','conn','nidus','Iyri','exit']
_STATE_FLAGS_ = {'init':(1 << 0),   # initialized properly
                 'store':(1 << 1),  # storage instance is running (i.e. postgresql)
                 'conn':(1 << 2),   # connected to storage instance
                 'nidus':(1 << 3),  # nidus storage manager running
                 'Iyri':(1 << 4),  # at least one sensor is collecting data
                 'exit':(1 << 5)}   # exiting/shutting down

class WraithPanel(gui.MasterPanel):
    """ WraithPanel - master panel for wraith gui """
    def __init__(self,tl,pwd=None):
        """
         set up, initialize parent and then initialize the gui
         our variables
         tl: tk's toplevel
         pwd: sudo password
        """
        self._conf = None   # configuration
        self._bSQL = False  # postgresql was running on startup
        self._pwd = pwd     # sudo password (should we not save it?)

        # set up super
        gui.MasterPanel.__init__(self,tl,"Wraith  v%s" % wraith.__version__,
                                 [],"widgets/icons/wraith3.png",False)
        self._menuenable()

#### PROPS

    @property # return the state as a dict of flag->values
    def stateflags(self): return bits.bitmask_list(_STATE_FLAGS_,self._state)

    @property # return {True: is initialized|False: is not intialized}
    def isinitialized(self): return bits.bitmask_list(_STATE_FLAGS_,self._state)['init']

    @property # return {True: Posqtgre is running|False: Postgre is not running)
    def psqlisrunning(self): return bits.bitmask_list(_STATE_FLAGS_,self._state)['store']

    @property # return {True: connected to backend|False: Not connected to backend}
    def isconnected(self): return bits.bitmask_list(_STATE_FLAGS_,self._state)['conn']

    @property # return {True: Nidus is running|False: Nidus is not running}
    def nidusisrunning(self): return bits.bitmask_list(_STATE_FLAGS_,self._state)['nidus']

    @property # return {True: Iyri is running|False: Iyri is not running|
    def Iyriisrunning(self): return bits.bitmask_list(_STATE_FLAGS_,self._state)['Iyri']

    @property # return {True: Wraith is exiting|False: Wraith is not exiting}
    def isexiting(self): return bits.bitmask_list(_STATE_FLAGS_,self._state)['exit']

    @property # return DB connect dict w/ keys 'host','port','db','user','pwd'
    def connectstring(self):
        try:
            return self._conf['store']
        except:
            return None

#### OVERRIDES

    def _initialize(self):
        """ initialize gui, determine initial state """
        # configure panel & write initial message have to manually enter the
        # desired size, as the menu does not expand the visible portion automatically
        self.tk.wm_geometry("300x1+0+0") # our desired size
        self.update_idletasks()          # force update -> should put the log panel 2nd

        # if a pwd was given, the wraith will be created during the splash screen
        # if not, we have to create here
        if self._pwd is None: self._create()

    def _create(self):
        # read in conf file, exit on error
        msgs = [(time.strftime('%H:%M:%S'),"Wraith v%s" % wraith.__version__,gui.LOG_NOERR)]
        self._conf = readconf()
        if 'err' in self._conf:
            msgs.append((time.strftime('%H:%M:%S'),
                          "Configuration file is invalid. %s" % self._conf['err'],
                          gui.LOG_ERR))
            return

        # determine if postgresql is running
        if cmdline.runningprocess('postgres'):
            # update self, msg and connect
            msgs.append((time.strftime('%H:%M:%S'),'PostgreSQL running',gui.LOG_NOERR))
            if not self._pwd: self._bSQL = True
            self._setstate(_STATE_STORE_)
            (self._conn,ret) = cmdline.psqlconnect(self._conf['store'])
            if not self._conn is None:
                self._setstate(_STATE_CONN_)
                msgs.append((time.strftime('%H:%M:%S'),'Connected to DB',gui.LOG_NOERR))
            else:
                msgs.append((time.strftime('%H:%M:%S'),"Connect to DB failed: %s" % ret,gui.LOG_ERR))
                return
        else:
            msgs.append((time.strftime('%H:%M:%S'),"PostgreSQL not running",gui.LOG_WARN))
            msgs.append((time.strftime('%H:%M:%S'),"Not connected to DB",gui.LOG_WARN))

        # nidus running?
        if cmdline.runningservice(wraith.NIDUSPID):
            msgs.append((time.strftime('%H:%M:%S'),"Nidus running",gui.LOG_NOERR))
            self._setstate(_STATE_NIDUS_)
        else:
            msgs.append((time.strftime('%H:%M:%S'),"Nidus not running",gui.LOG_WARN))

        # Iyri running?
        if cmdline.runningservice(wraith.LYRIPID):
            msgs.append((time.strftime('%H:%M:%S'),"Iyri running",gui.LOG_NOERR))
            self._setstate(_STATE_LYRI_)
        else:
            msgs.append((time.strftime('%H:%M:%S'),"DySKt not running",gui.LOG_WARN))

        # set initial state to initialized
        self._setstate(_STATE_INIT_)

        # show log, write messages & display any saved panels
        self.viewlog()
        self.getpanel("log",True).delayedwrite(msgs)
        if os.path.exists('default.ts'): self.guiload('default.ts')

        # check if something outside this program stopped a service
        self.after(500,self._poll)

    def _shutdown(self):
        """ if connected to datastorage, closes connection """
        self.setbusy()               # we're busy
        self._setstate(_STATE_EXIT_) # set the state
        self._stopsensor()           # shutdown Iyri
        self._stopstorage()          # shutdown storage
        self.setbusy(False)          # we're done

    def _makemenu(self):
        """ make the menu """
        self._menubar = tk.Menu(self)

        # Wraith Menu
        # all options will always be enabled
        self._mnuWraith = tk.Menu(self._menubar,tearoff=0)
        self._mnuWraithGui = tk.Menu(self._mnuWraith,tearoff=0)
        self._mnuWraithGui.add_command(label='Save',command=self.guisave)
        self._mnuWraithGui.add_command(label='Load',command=self.guiload)
        self._mnuWraith.add_cascade(label='Gui',menu=self._mnuWraithGui)
        self._mnuWraith.add_separator()
        self._mnuWraith.add_command(label='Configure',command=self.configwraith)
        self._mnuWraith.add_separator()
        self._mnuWraith.add_command(label='Exit',command=self.delete)

        # Tools Menu
        # all options will always be enabled
        self._mnuTools = tk.Menu(self._menubar,tearoff=0)
        self._mnuTools.add_command(label='Convert',command=self.viewconvert)
        self._mnuToolsCalcs = tk.Menu(self._mnuTools,tearoff=0)
        self._mnuToolsCalcs.add_command(label='EIRP',command=lambda:self.calc('EIRP'))
        self._mnuToolsCalcs.add_command(label='FSPL',command=lambda:self.calc('FSPL'))
        self._mnuToolsCalcs.add_command(label='Link Budget',command=lambda:self.calc('Link Budget'))
        self._mnuToolsCalcs.add_command(label="Fresnel Zone",command=lambda:self.calc('Fresnel Zone'))
        self._mnuToolsCalcs.add_separator()
        self._mnuToolsCalcs.add_command(label='Distance',command=lambda:self.calc('Distance'))
        self._mnuToolsCalcs.add_command(label='Terminus',command=lambda:self.calc('Terminus'))
        self._mnuToolsCalcs.add_command(label='Cut',command=lambda:self.calc('Cut'))
        self._mnuTools.add_cascade(label='Calcuators',menu=self._mnuToolsCalcs)
        self._mnuTools.add_separator()
        self._mnuTools.add_command(label='Interfaces',command=self.viewinterfaces)

        # Data Menu
        # all options will always be enabled
        self._mnuData = tk.Menu(self._menubar,tearoff=0)
        self._mnuData.add_command(label='Data Bins',command=self.viewdatabins)     # 0
        self._mnuData.add_separator()                                              # 1
        self._mnuData.add_command(label='View Data',command=self.viewdata)         # 2
        self._mnuData.add_separator()                                              # 3
        self._mnuData.add_command(label='Sessions',command=self.viewsessions)      # 4

        # Storage Menu
        self._mnuStorage = tk.Menu(self._menubar,tearoff=0)
        self._mnuStorage.add_command(label="Start All",command=self.storagestart)  # 0
        self._mnuStorage.add_command(label="Stop All",command=self.storagestop)    # 1
        self._mnuStorage.add_separator()                                           # 2
        self._mnuStoragePSQL = tk.Menu(self._mnuStorage,tearoff=0)
        self._mnuStoragePSQL.add_command(label='Start',command=self.psqlstart)       # 0
        self._mnuStoragePSQL.add_command(label='Stop',command=self.psqlstop)         # 1
        self._mnuStoragePSQL.add_separator()                                         # 2
        self._mnuStoragePSQL.add_command(label='Connect',command=self.connect)       # 3
        self._mnuStoragePSQL.add_command(label='Disconnect',command=self.disconnect) # 4
        self._mnuStoragePSQL.add_separator()                                         # 5
        self._mnuStoragePSQL.add_command(label='Fix',command=self.psqlfix)           # 6
        self._mnuStoragePSQL.add_command(label='Delete All',command=self.psqldelall) # 7
        self._mnuStorage.add_cascade(label='PostgreSQL',menu=self._mnuStoragePSQL)  # 3
        self._mnuStorageNidus = tk.Menu(self._mnuStorage,tearoff=0)
        self._mnuStorageNidus.add_command(label='Start',command=self.nidusstart)     # 0
        self._mnuStorageNidus.add_command(label='Stop',command=self.nidusstop)       # 1
        self._mnuStorageNidus.add_separator()                                        # 2
        self._mnuNidusLog = tk.Menu(self._mnuStorageNidus,tearoff=0)
        self._mnuNidusLog.add_command(label='View',command=self.viewniduslog)         # 0
        self._mnuNidusLog.add_command(label='Clear',command=self.clearniduslog)       # 1
        self._mnuStorageNidus.add_cascade(label='Log',menu=self._mnuNidusLog)         # 3
        self._mnuStorageNidus.add_separator()                                        # 4
        self._mnuStorageNidus.add_command(label='Config',command=self.confignidus)   # 5
        self._mnuStorage.add_cascade(label='Nidus',menu=self._mnuStorageNidus)      # 4

        # Iyri Menu
        self._mnuIyri = tk.Menu(self._menubar,tearoff=0)
        self._mnuIyri.add_command(label='Start',command=self.Iyristart)   # 0
        self._mnuIyri.add_command(label='Stop',command=self.Iyristop)     # 1
        self._mnuIyri.add_separator()                                      # 2
        self._mnuIyri.add_command(label='Control',command=self.Iyrictrl)  # 3
        self._mnuIyri.add_separator()                                      # 4
        self._mnuIyriLog = tk.Menu(self._mnuIyri,tearoff=0)
        self._mnuIyriLog.add_command(label='View',command=self.viewIyrilog)   # 0
        self._mnuIyriLog.add_command(label='Clear',command=self.clearIyrilog) # 1
        self._mnuIyri.add_cascade(label='Log',menu=self._mnuIyriLog)       # 5
        self._mnuIyri.add_separator()                                      # 6
        self._mnuIyri.add_command(label='Config',command=self.configIyri) # 7

        # Help Menu
        self._mnuHelp = tk.Menu(self._menubar,tearoff=0)
        self._mnuHelp.add_command(label='About',command=self.about)
        self._mnuHelp.add_command(label='Help',command=self.help)

        # add the menus
        self._menubar.add_cascade(label='Wraith',menu=self._mnuWraith)
        self._menubar.add_cascade(label="Tools",menu=self._mnuTools)
        self._menubar.add_cascade(label='Data',menu=self._mnuData)
        self._menubar.add_cascade(label='Storage',menu=self._mnuStorage)
        self._menubar.add_cascade(label='Iyri',menu=self._mnuIyri)
        self._menubar.add_cascade(label='Help',menu=self._mnuHelp)

    def showpanel(self,desc):
        """ opens a panel of type desc """
        if desc == 'log': self.viewlog()
        elif desc == 'databin': self.viewdatabins()
        elif desc == 'interfaces': self.viewinterfaces()
        elif desc == 'sessions': self.viewsessions()
        elif desc == 'preferences': self.configwraith()
        elif desc == 'niduslog': self.viewniduslog()
        elif desc == 'nidusprefs': self.confignidus()
        elif desc == 'Iyrilog': self.viewIyrilog()
        elif desc == 'Iyriprefs': self.configIyri()
        elif desc == 'about': self.about()
        else: raise RuntimeError, "WTF Cannot open %s" % desc

#### MENU CALLBACKS

#### Wraith Menu

    def configwraith(self):
        """ display config file preference editor """
        panel = self.getpanels('preferences',False)
        if not panel:
            t = tk.Toplevel()
            pnl = subgui.WraithConfigPanel(t,self)
            self.addpanel(pnl.name,gui.PanelRecord(t,pnl,'preferences'))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

#### Tools Menu

    def viewconvert(self):
        """ display conversion panel """
        panel = self.getpanels('convert',False)
        if not panel:
            t = tk.Toplevel()
            pnl = subgui.ConvertPanel(t,self)
            self.addpanel(pnl.name,gui.PanelRecord(t,pnl,'convert'))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

    def calc(self,key):
        """ calculate the function defined by key in the _CALCS_ dict"""
        panel = self.getpanels('%scalc' % key)
        if not panel:
            t = tk.Toplevel()
            pnl = subgui.CalculatePanel(t,self,key,subgui.CALCS[key]['inputs'],
                                                   subgui.CALCS[key]['answer'],
                                                   subgui.CALCS[key]['rc'])
            self.addpanel(pnl.name,gui.PanelRecord(t,pnl,'%scalc' % key))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

    def viewinterfaces(self):
        """ show all interfaces """
        panel = self.getpanels('interfaces',False)
        if not panel:
            t = tk.Toplevel()
            pnl = subgui.InterfacePanel(t,self)
            self.addpanel(pnl.name,gui.PanelRecord(t,pnl,'interfaces'))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

#### View Menu

    def viewdatabins(self):
        """ display the data bins panel """
        panel = self.getpanels('databin',False)
        if not panel:
            t = tk.Toplevel()
            pnl = subgui.DatabinPanel(t,self,self._conn)
            self.addpanel(pnl.name,gui.PanelRecord(t,pnl,'databin'))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

    def viewdata(self):
        """ display data panel """
        self.unimplemented()

    def viewsessions(self):
        """ display data sessions panel """
        panel = self.getpanels('sessions',False)
        if not panel:
           t = tk.Toplevel()
           pnl = subgui.SessionsPanel(t,self,self._conf['store'])
           self.addpanel(pnl.name,gui.PanelRecord(t,pnl,'sessions'))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

#### Storage Menu

    def storagestart(self):
        """ starts database and storage manager """
        self._startstorage()
        self._updatestate()
        self._menuenable()

    def storagestop(self):
        """ stops database and storage manager """
        self._stopstorage()
        self._updatestate()
        self._menuenable()

    def connect(self):
        """ connects to postgresql """
        # NOTE: this should not be enabled unless psql is running and we are
        # not connected, but check anyway
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if not flags['conn']:
            cmdline.psqlconnect(self._conf['store'])
            self._updatestate()
            self._menuenable()

    def disconnect(self):
        """ connects to postgresql """
        # NOTE: should not be enabled if already disconnected but check anyway
        # TODO: what to do once we have data being pulled?
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if flags['conn']:
            self._psqldisconnect()
            self._updatestate()
            self._menuenable()

    def psqlstart(self):
        """ starts postgresql """
        # NOTE: should not be enabled if postgresql is already running but check anyway
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if not flags['store']:
            # do we have a password
            if not self._pwd:
                pwd = self._getpwd()
                if pwd is None:
                    self.logwrite("Password entry canceled. Cannot continue",
                                  gui.LOG_WARN)
                    return
                self._pwd = pwd
            self.logwrite("Starting Postgresql...",gui.LOG_NOTE)
            if startpsql(self._pwd):
                self.logwrite('Postgresql started')
                self._updatestate()
                self._menuenable()
            else:
                self.logwrite("Postgresql failed to start")

    def psqlstop(self):
        """ starts postgresql """
        # should not be enabled if postgresql is not running, but check anyway
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if flags['store'] and not flags['Iyri']:
            # do we have a password
            if not self._pwd:
                pwd = self._getpwd()
                if pwd is None:
                    self.logwrite("Password entry canceled. Cannot continue",
                                  gui.LOG_WARN)
                    return
                self._pwd = pwd
            if stoppsql(self._pwd):
                self._updatestate()
                self._menuenable()
            else:
                self.logwrite("Failed to stop PostgreSQL",gui.LOG_ERR)

    def psqlfix(self):
        """
         fix any open-ended periods left over by errors. An error or kill -9
         may leave periods in certain tables as NULL-ended which will throw an
         error during insert of new records
        """
        # should not be enabled unless postgres is running, we are connected
        # and no sensors are running
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if flags['store'] and flags['conn'] and not flags['Iyri']:
            curs = None
            try:
                self.logwrite("Fixing null-ended records in database...",gui.LOG_NOTE)
                curs = self._conn.cursor()
                curs.callproc("fix_nullperiod")
                self._conn.commit()
                self.logwrite("Fixed all null-ended records")
            except psql.Error as e:
                self._conn.rollback()
                self.logwrite("Error fixing records <%s: %s>" % (e.pgcode,e.pgerror),
                              gui.LOG_ERR)
            finally:
                if curs: curs.close()

    def psqldelall(self):
        """ delete all data in nidus database """
        # should not be enabled unless postgres is running, we are connected
        # and a sensor is not running, but check anyway
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if flags['store'] and flags['conn'] and not flags['Iyri']:
            ans = self.ask('Delete Records','Delete all DB records?')
            self.update()
            if ans == 'no': return
            curs = None
            try:
                # get a cursor and execute the delete_all procedure
                self.logwrite("Deleting all records in database...",gui.LOG_NOTE)
                curs = self._conn.cursor()
                curs.callproc('delete_all')
                self._conn.commit()
                self.logwrite("Deleted all records")
            except psql.Error as e:
                self._conn.rollback()
                self.logwrite("Delete Failed<%s: %s>" % (e.pgcode,e.pgerror),gui.LOG_ERR)
            finally:
                if curs: curs.close()

    def nidusstart(self):
        """ starts nidus storage manager """
        # NOTE: should not be enabled if postgresql is not running but check anyway
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if not flags['nidus']:
            # do we have a password
            if not self._pwd:
                pwd = self._getpwd()
                if pwd is None:
                    self.logwrite("Password entry canceled. Cannot continue",
                                  gui.LOG_WARN)
                    return
                self._pwd = pwd
            self.logwrite('Starting Nidus...',gui.LOG_NOTE)
            if startnidus(self._pwd):
                self._updatestate()
                self._menuenable()
                self.logwrite('Nidus Started')
            else:
                self.logwrite("Failed to start Nidus",gui.LOG_ERR)

    def nidusstop(self):
        """ stops nidus storage manager """
        # should not be enabled if nidus is not running, but check anyway
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if flags['nidus']:
            # do we have a password
            if not self._pwd:
                pwd = self._getpwd()
                if pwd is None:
                    self.logwrite("Password entry canceled. Cannot continue",
                                  gui.LOG_WARN)
                    return
                self._pwd = pwd

            self.logwrite("Stopping Nidus...",gui.LOG_NOTE)
            if stopnidus(self._pwd):
                self._updatestate()
                self._menuenable()
                self.logwrite("Nidus Stopped")
            else:
                self.logwrite("Failed to stop Nidus",gui.LOG_ERR)

    def viewniduslog(self):
        """ display Nidus log """
        panel = self.getpanels('niduslog',False)
        if not panel:
            t = tk.Toplevel()
            pnl = gui.TailLogPanel(t,self,"Nidus Log",200,wraith.NIDUSLOG,50)
            self.addpanel(pnl.name,gui.PanelRecord(t,pnl,'niduslog'))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

    def clearniduslog(self):
        """ clear nidus log """
        # prompt first
        finfo = os.stat(wraith.NIDUSLOG)
        if finfo.st_size > 0:
            ans = self.ask("Clear Log","Clear contents of Nidus log?")
            self.update()
            if ans == 'no': return
            lv = self.getpanel('niduslog')
            with open(wraith.NIDUSLOG,'w'): os.utime(wraith.NIDUSLOG,None)
            if lv: lv.reset()

    def confignidus(self):
        """ display nidus config file preference editor """
        panel = self.getpanels('nidusprefs',False)
        if not panel:
            t = tk.Toplevel()
            pnl = subgui.NidusConfigPanel(t,self)
            self.addpanel(pnl.name,gui.PanelRecord(t,pnl,'nidusprefs'))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

#### Iyri Menu

    def Iyristart(self):
        """ starts Iyri sensor """
        self._startsensor()
        self._updatestate()
        self._menuenable()

    def Iyristop(self):
        """ stops Iyri sensor """
        self._stopsensor()
        self._updatestate()
        self._menuenable()

    def Iyrictrl(self):
        """ displays Iyri Control Panel """
        self.unimplemented()

    def viewIyrilog(self):
        """ display Iyri log """
        panel = self.getpanels('Iyrilog',False)
        if not panel:
            t = tk.Toplevel()
            pnl = gui.TailLogPanel(t,self,"Iyri Log",200,wraith.LYRILOG,50)
            self.addpanel(pnl.name,gui.PanelRecord(t,pnl,'Iyrilog'))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

    def clearIyrilog(self):
        """ clears the Iyri log """
        # prompt first
        finfo = os.stat(wraith.LYRILOG)
        if finfo.st_size > 0:
            ans = self.ask("Clear Log","Clear contents of Iyri log?")
            self.update()
            if ans == 'no': return
            with open(wraith.LYRILOG,'w'): pass
            lv = self.getpanel('Iyrilog')
            if lv: lv.reset()

    def configIyri(self):
        """ display Iyri config file preference editor """
        panel = self.getpanels('Iyriprefs',False)
        if not panel:
            t = tk.Toplevel()
            pnl = subgui.IyriConfigPanel(t,self)
            self.addpanel(pnl.name,gui.PanelRecord(t,pnl,'Iyriprefs'))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

#### HELP MENU

    def about(self):
        """ display the about panel """
        panel = self.getpanels('about',False)
        if not panel:
            t = tk.Toplevel()
            pnl = subgui.AboutPanel(t,self)
            self.addpanel(pnl.name,gui.PanelRecord(t,pnl,'about'))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

    def help(self):
        """ display the help panel """
        self.unimplemented()

#### HELPER FUNCTIONS

    def _poll(self):
        """ periodically recheck state """
        # check our current state
        oldstate = self._state # save the current state
        self._updatestate()    # update it
        if oldstate != self._state: self._menuenable()
        self.after(500,self._poll)

    def _updatestate(self):
        """ reevaluates internal state """
        # state of nidus
        if cmdline.runningservice(wraith.NIDUSPID): self._setstate(_STATE_NIDUS_)
        else: self._setstate(_STATE_NIDUS_,False)

        # state of Iyri
        if cmdline.runningservice(wraith.LYRIPID): self._setstate(_STATE_LYRI_)
        else:  self._setstate(_STATE_LYRI_,False)

        # state of postgres i.e. store
        if cmdline.runningprocess('postgres'): self._setstate(_STATE_STORE_)
        else: self._setstate(_STATE_STORE_,False)

        # state of our connection - should figure out a way to determine if
        # connection is still 'alive'
        if self._conn: self._setstate(_STATE_CONN_)
        else: self._setstate(_STATE_CONN_,False)

    def _setstate(self,f,up=True):
        """ sets internal state's flag f to 1 if up is True or 0 otherwise """
        if up:
            self._state = bits.bitmask_set(_STATE_FLAGS_,
                                           self._state,
                                           _STATE_FLAGS_NAME_[f])
        else:
            self._state = bits.bitmask_unset(_STATE_FLAGS_,
                                             self._state,
                                             _STATE_FLAGS_NAME_[f])

    def _menuenable(self):
        """ enable/disable menus as necessary """
        # get all flags
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)

        # view sessions
        if flags['conn']: self._mnuData.entryconfig(4,state=tk.NORMAL)
        else: self._mnuData.entryconfig(4,state=tk.DISABLED)

        # start all
        if flags['store'] and flags['nidus'] and flags['Iyri']:
            self._mnuData.entryconfig(4,state=tk.DISABLED)
        else: self._mnuData.entryconfig(4,state=tk.NORMAL)

        # stop all
        if not flags['store'] and not flags['nidus'] and not flags['Iyri']:
            self._mnuStorage.entryconfig(1,state=tk.DISABLED)
        else: self._mnuStorage.entryconfig(1,state=tk.NORMAL)

        # start/stop postgres
        if flags['store']:
            # disable start, enable stop (if Iyri is not running)
            self._mnuStoragePSQL.entryconfig(0,state=tk.DISABLED)
            if not flags['Iyri']: self._mnuStoragePSQL.entryconfig(1,state=tk.NORMAL)
        else:
            # enable start and disable stop
            self._mnuStoragePSQL.entryconfig(0,state=tk.NORMAL)
            self._mnuStoragePSQL.entryconfig(1,state=tk.DISABLED)

        # connect/disconnect 2 postgres
        if flags['conn']:
            # disable connect and enable disconnect
            self._mnuStoragePSQL.entryconfig(3,state=tk.DISABLED)
            self._mnuStoragePSQL.entryconfig(4,state=tk.NORMAL)
        else:
            # enable connect and disable disconnect
            self._mnuStoragePSQL.entryconfig(3,state=tk.NORMAL)
            self._mnuStoragePSQL.entryconfig(4,state=tk.DISABLED)

        # fix db and delete all (only allowed if connected and Iyri is not running)
        if flags['conn']:
            if flags['Iyri']:
                self._mnuStoragePSQL.entryconfig(6,state=tk.DISABLED)
                self._mnuStoragePSQL.entryconfig(7,state=tk.DISABLED)
            else:
                self._mnuStoragePSQL.entryconfig(6,state=tk.NORMAL)
                self._mnuStoragePSQL.entryconfig(7,state=tk.NORMAL)
        else:
            self._mnuStoragePSQL.entryconfig(6,state=tk.DISABLED)
            self._mnuStoragePSQL.entryconfig(7,state=tk.DISABLED)

        # nidus start/stop & clear log NOTE: unlike psql, we allow nidus to stop
        # even in cases where Iyri may be running as Iyri will handle nidus
        # closing the comms socket)
        if flags['nidus']:
            # disable start and clear log and enable stop
            self._mnuStorageNidus.entryconfig(0,state=tk.DISABLED)
            self._mnuNidusLog.entryconfig(1,state=tk.DISABLED)
            self._mnuStorageNidus.entryconfig(1,state=tk.NORMAL)
        else:
            # enable start clear log and disable stop
            self._mnuStorageNidus.entryconfig(0,state=tk.NORMAL)
            self._mnuNidusLog.entryconfig(1,state=tk.NORMAL)
            self._mnuStorageNidus.entryconfig(1,state=tk.DISABLED)

        # Iyri
        if not flags['store'] and not flags['nidus']:
            # cannot start/stop/control Iyri unless nidus & postgres is running
            self._mnuIyri.entryconfig(0,state=tk.DISABLED)  # start
            self._mnuIyri.entryconfig(1,state=tk.DISABLED)  # stop
            self._mnuIyri.entryconfig(3,state=tk.DISABLED)  # ctrl panel
            self._mnuIyriLog.entryconfig(1,state=tk.NORMAL) # clear log
            self._mnuIyri.entryconfig(7,state=tk.NORMAL)    # configure
        else:
            if flags['Iyri']:
                # Iyri sensor is running
                self._mnuIyri.entryconfig(0,state=tk.DISABLED)    # start
                self._mnuIyri.entryconfig(1,state=tk.NORMAL)      # stop
                self._mnuIyri.entryconfig(3,state=tk.NORMAL)      # ctrl panel
                self._mnuIyriLog.entryconfig(1,state=tk.DISABLED) # clear log
                self._mnuIyri.entryconfig(7,state=tk.NORMAL)      # configure
            else:
                # Iyri sensor is not running
                self._mnuIyri.entryconfig(0,state=tk.NORMAL)    # start
                self._mnuIyri.entryconfig(1,state=tk.DISABLED)  # stop
                self._mnuIyri.entryconfig(3,state=tk.DISABLED)  # ctrl panel
                self._mnuIyriLog.entryconfig(1,state=tk.NORMAL) # clear log
                self._mnuIyri.entryconfig(7,state=tk.NORMAL)    # configure

    def _startstorage(self):
        """ start postgresql db and nidus storage manager & connect to db """
        # do we have a password
        if not self._pwd:
            pwd = self._getpwd()
            if pwd is None:
                self.logwrite("Password entry canceled. Cannot continue",gui.LOG_WARN)
                return
            self._pwd = pwd

        # start necessary storage components
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if not flags['store']:
            self.logwrite("Starting PostgreSQL...",gui.LOG_NOTE)
            if not startpsql(self._pwd):
                self.logwrite("Failed to start PostgreSQL",gui.LOG_ERR)
                return
            else:
                self.logwrite("PostgreSQL started")

        # start nidus
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if not flags['nidus'] and flags['store']:
            self.logwrite("Starting Nidus...",gui.LOG_NOTE)
            if not startnidus(self._pwd):
                self.logwrite("Failed to start Nidus",gui.LOG_ERR)
                return
            else:
                self.logwrite("Nidus started")

        # connect to db
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if not flags['conn'] and flags['store']:
            self.logwrite("Connected to database...",gui.LOG_NOTE)
            self._conn,msg = cmdline.psqlconnect(self._conf['strore'])
            if self._conn is None:
                self.logwrite(msg,gui.LOG_ERR)
                return
            else:
                self.logwrite("Connected to database")

        self._updatestate()
        self._menuenable()

    def _stopstorage(self):
        """ stop posgresql db, nidus storage manager & disconnect """
        # if Iyri is running, prompt for clearance
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if flags['Iyri']:
            ans = self.ask('Iyri Running','Quit and lose queued data?')
            self.update()
            if ans == 'no': return

        # return if no storage component is running
        if not (flags['store'] or flags['conn'] or flags['nidus']): return

        # disconnect from db
        if flags['conn']: self._psqldisconnect()

        # before shutting down nidus & postgresql, confirm auto shutdown is enabled
        if not self._conf['policy']['shutdown']: return

        # shutdown nidus
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if flags['nidus']:
            # do we have a password
            if not self._pwd:
                pwd = self._getpwd()
                if pwd is None:
                    self.logwrite("Password entry canceled. Cannot continue",gui.LOG_WARN)
                    return
                self._pwd = pwd

            self.logwrite("Stopping Nidus...",gui.LOG_NOTE)
            if not stopnidus(self._pwd):
                self.logwrite("Failed to stop Nidus",gui.LOG_WARN)
            else: self.logwrite("Nidus stopped")

        # shutdown postgresql (check first if polite)
        if self._conf['policy']['polite'] and self._bSQL: return
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if flags['store']:
            # do we have a password
            if not self._pwd:
                pwd = self._getpwd()
                if pwd is None:
                    self.logwrite("Password entry canceled. Cannot continue",gui.LOG_WARN)
                    return
                self._pwd = pwd

            self.logwrite("Stopping PostgreSQL...",gui.LOG_NOTE)
            if not stoppsql(self._pwd):
                self.logwrite("Failed to stop PostgreSQL",gui.LOG_WARN)
            else: self.logwrite("PostgreSQL stopped")

        self._updatestate()
        self._menuenable()

    def _psqldisconnect(self):
        """ disconnect from postgresl """
        self.logwrite("Disconnecting from Nidus datastore...",gui.LOG_NOTE)
        self._conn.close()
        self._conn = None
        self._setstate(_STATE_CONN_,False)
        self.logwrite("Disconnected from Nidus datastore")

    def _startsensor(self):
        """ starts the Iyri sensor """
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if flags['store'] and flags['nidus'] and not flags['Iyri']:
            # do we have a password
            if not self._pwd:
                pwd = self._getpwd()
                if pwd is None:
                    self.logwrite("Password entry canceled. Cannot continue",
                                  gui.LOG_WARN)
                    return
                self._pwd = pwd

            # start the sensor
            try:
                self.logwrite("Starting Iyri...",gui.LOG_NOTE)
                cmdline.service('Iyrid',self._pwd)
                time.sleep(0.5)
                if not cmdline.runningservice(wraith.LYRIPID): raise RuntimeError('unknown')
            except RuntimeError as e:
                self.logwrite("Error starting Iyri: %s" % e,gui.LOG_ERR)
            else:
                self.logwrite("Iyri Started")
                self._setstate(_STATE_LYRI_)

    def _stopsensor(self):
        """ stops the Iyri sensor """
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if flags['Iyri']:
            # do we have a password
            if not self._pwd:
                pwd = self._getpwd()
                if pwd is None:
                    self.logwrite("Password entry canceled. Cannot continue",
                                  gui.LOG_WARN)
                    return
                self._pwd = pwd

            # stop the sensor
            try:
                self.logwrite("Shutting down Iyri...",gui.LOG_NOTE)
                cmdline.service('Iyrid',self._pwd,False)
            except RuntimeError as e:
                self.logwrite("Error shutting down Iyri: %s" % e,gui.LOG_ERR)
            else:
                self._setstate(_STATE_LYRI_,False)
                self.logwrite("Iyri shut down")

    def _getpwd(self):
        """ prompts for sudo password until correct or canceled"""
        dlg = gui.PasswordDialog(self)
        try:
            # test out sudo pwd
            while not cmdline.testsudopwd(dlg.pwd):
                self.logwrite("Bad password entered. Try Again",gui.LOG_ERR)
                dlg = gui.PasswordDialog(self)
            return dlg.pwd
        except AttributeError:
            return None # canceled

class WraithSplash(object):
    """ Splash Window """
    def __init__(self,tl,wp,pwd):
        """
         tl: Toplevel
         wp: WraithPanel
        """
        self._tl = tl
        self._wp = wp
        self._pwd = pwd
        self._finished = False
        self._tl.overrideredirect(True) # hide the title bar

        # create our splash image, progress bar and status label
        ttk.Label(self._tl,style="splash.TLabel",font=('Gothic',20,'bold'),
                  text="WRAITH-RT %s" % wraith.__version__,
                  justify=tk.CENTER).grid(row=0,column=0,sticky='nwse')
        self._logo = ImageTk.PhotoImage(Image.open("widgets/icons/splash.png"))
        ttk.Label(self._tl,image=self._logo,
                  style="splash.TLabel").grid(row=1,column=0,sticky='nwse')
        ttk.Label(self._tl,style="splash.TLabel",font=('Helvetica',10,'italic'),
                  text="You knew that I reap where I have not sown\nand gather where I scattered no seed.",
                  justify=tk.LEFT).grid(row=2,column=0,sticky='nwse')
        self._pb = ttk.Progressbar(self._tl,style="splash.Horizontal.TProgressbar",
                                   maximum=10,orient=tk.HORIZONTAL,
                                   mode='determinate')
        self._pb.grid(row=3,column=0,sticky='nwse')
        self._sv = tk.StringVar()
        self._sv.set("Initializing...")
        ttk.Label(self._tl,style="splash.TLabel",textvariable=self._sv,
                  justify=tk.CENTER).grid(row=4,column=0,sticky='nwse')

        # center on screen
        w = self._tl.winfo_screenwidth()
        h = self._tl.winfo_screenheight()
        sz = tuple(int(_) for _ in self._tl.geometry().split('+')[0].split('x'))
        x = (w/2 - sz[0])/2
        y = (h/2 - sz[1])/2
        self._tl.geometry("+%d+%d" % (x,y))

        # start 'polling'
        self._bconfig = False
        self._bpsql = False
        self._bnidus = False
        self._bfinished = False
        self._tl.after(1000,self._busy)

    def _busy(self):
        if self._bfinished:
            self._wp.master.deiconify()
            # noinspection PyProtectedMember
            self._wp._create()
            self._tl.destroy()
        else:
            if not self._bconfig: self._chkconfig()
            elif not self._bpsql: self._chkpsql()
            elif not self._bnidus: self._chknidus()
            else: self._chkIyri()
            self._tl.after(1000,self._busy)

    def _chkconfig(self):
        self._sv.set("Checking configuration file...")
        self._pb.step(0.5)
        conf = readconf()
        if 'err' in conf: raise RuntimeError("Config file invalid: %s" % conf['err'])
        else: self._sv.set('Configuration file is valid')
        self._bconfig = True
        self._pb.step(2.0)

    def _chkpsql(self):
        self._sv.set("Checking PostgreSQL..")
        self._pb.step(0.5)
        if not cmdline.runningprocess('postgres'):
            self._sv.set("Starting PostgreSQL")
            if startpsql(pwd): self._sv.set("PostgreSQL started")
            else: self._sv.set("Failed to start PostgreSQL")
        else:
            self._sv.set("PostgreSQL already running")
        self._bpsql = True
        self._pb.step(2.0)

    def _chknidus(self):
        self._sv.set("Checking Nidus...")
        self._pb.step(0.5)
        if not cmdline.runningservice(wraith.NIDUSPID):
            self._sv.set("Starting Nidus")
            if startnidus(pwd): self._sv.set("Nidus started")
            else: self._sv.set("Failed to start Nidus")
        else:
            self._sv.set("Nidus already running")
        self._bnidus = True
        self._pb.step(2.0)

    def _chkIyri(self):
        self._sv.set("Checking Iyri...")
        self._pb.step(2.0)
        if not cmdline.runningservice(wraith.LYRIPID):
            self._sv.set("Starting Iyri")
            if not startIyri(pwd):
                # because Iyri can sometimes take a while, we will run
                # this several times
                i = 5
                while not cmdline.runningservice(wraith.LYRIPID):
                    i -= 1
                    if i == 0: break
                    time.sleep(0.5)
            if cmdline.runningservice(wraith.LYRIPID): self._sv.set("Iyri started")
            else: self._sv.set("Failed to start Iyri")
        else:
            self._sv.set("Iyri already running")
        self._bfinished = True

if __name__ == '__main__':
    # create arg parser and parse arguments
    ap = argparse.ArgumentParser(description="Wraith-rt %s" % wraith.__version__)
    ap.add_argument('-s','--start',help="Start with options = one of {nogui|gui|all}")
    ap.add_argument('-d','--stop',action='store_true',help="Stops all found services")
    ap.add_argument('-x','--exclude',action='store_true',help="Does not stop PostgreSQL")
    ap.add_argument('-v','--version',action='version',version="Wraith-rt %s" % wraith.__version__)
    args = ap.parse_args()
    sopts = args.start
    stop = args.stop
    exclude = args.exclude

    # default is start nogui (make sure both start and stop are not specified)
    # if password is entered verified correctness
    if sopts is None and stop == False: sopts = 'gui'
    if sopts is not None and stop == True: ap.error("Cannot start and stop")

    # stop services - assumes no gui
    if stop:
        # verify pwd has been set
        i = 2
        pwd = getpass.unix_getpass(prompt="Password [for %s]:" % getpass.getuser())
        while not cmdline.testsudopwd(pwd):
            pwd = getpass.unix_getpass(prompt="Incorrect password, try again:")
            i -= 1
            if i == 0: ap.error("Three incorrect password attempts")

        # stop Iyri, then Nidus, then PostgreSQL
        sd = sn = sp = True
        if cmdline.runningservice(wraith.LYRIPID):
            ret = 'ok' if stopIyri(pwd) else 'fail'
            print "Stopping Iyri\t\t\t\t[%s]" % ret
        else: print "Iyri not running"
        if cmdline.runningservice(wraith.NIDUSPID):
            ret = 'ok' if stopnidus(pwd) else 'fail'
            print "Stopping Nidus\t\t\t\t[%s]" % ret
        else: print "Nidus not running"
        if cmdline.runningprocess('postgres') and not exclude:
            ret = 'ok' if stoppsql(pwd) else 'fail'
            print "Stopping PostgreSQL\t\t\t[%s]" % ret
        else: print "PostgreSQL not running"
        sys.exit(0)

    # start specified services
    if sopts == 'nogui':
        # verify pwd is present
        i = 2
        pwd = getpass.unix_getpass(prompt="Password [for %s]:" % getpass.getuser())
        while not cmdline.testsudopwd(pwd):
            pwd = getpass.unix_getpass(prompt="Incorrect password, try again:")
            i -= 1
            if i == 0: ap.error("Three incorrect password attempts")

        # start postgresql (if needed), nidus and Iyri
        if not cmdline.runningprocess('postgres'):
            ret = 'ok' if startpsql(pwd) else 'fail'
            print "Starting PostgreSQL\t\t\t[%s]" % ret
        else:
            print "PostgreSQL already running"
        if not cmdline.runningservice(wraith.NIDUSPID):
            ret = 'ok' if startnidus(pwd) else 'fail'
            print "Starting Nidus\t\t\t\t[%s]" % ret
        else:
            print "Nidus already running"
        if not cmdline.runningservice(wraith.LYRIPID):
            ret = 'ok' if startIyri(pwd) else 'fail'
            print "Starting Iyri\t\t\t\t[%s]" % ret
        else:
            print "Iyri already Running"
        sys.exit(0)
    else:
        if sopts == 'all':
            i = 2
            pwd = getpass.unix_getpass(prompt="Password [for %s]:" % getpass.getuser())
            while not cmdline.testsudopwd(pwd):
                pwd = getpass.unix_getpass(prompt="Incorrect password, try again:")
                i -= 1
                if i == 0: ap.error("Three incorrect password attempts")
        else: pwd = None

        # configure style, using the alt theme
        t = tk.Tk()     # call our main program root first or Style() will do so
        s = ttk.Style()
        if 'alt' in s.theme_names(): s.theme_use('alt')
        # figure out how to remove the progressbar relief/border
        s.configure("splash.Horizontal.TProgressbar",foreground='green',
                    background='green',troughcolor='black',
                    troughrelief='black',borderwidth=0)
        s.configure("splash.TLabel",foreground='white',background='black',border=0)
        s.configure("reg.Horizontal.TProgressbar",foreground='green',
                    background='green',borderwidth=0)

        # WraithPanel will start everything if pwd is present otherwise just the gui
        try:
            wp = WraithPanel(t,pwd)                     # create main program
            if sopts == 'all':
                t.withdraw()                                # hide main programe
                splash = WraithSplash(tk.Toplevel(),wp,pwd) # show the splash
            wp.mainloop()                                   # start the main program
            sys.exit(0)
        except Exception as e:
            fout = open('wraith.log','a')
            fout.write("%s: %s\n" % (time.strftime("%d%H%ML%b%Y").upper(),e))
            fout.close()
            print 'Error: check wraith.log for details'
            sys.exit(1)