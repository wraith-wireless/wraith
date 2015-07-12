#!/usr/bin/env python
""" panel.py - defines a suite of graphical windows called panes

Defines a graphic suite based on Tix where a set of non-modal panels operate under
the control of a master panel and execute tasks, display information independently
of or in conjuction with this panel and other panels. (Think undocked windows)
Panels can be configured so that they can be opened, closed, "raised", minimized
by the user or only by a calling panel.

Conventions: As there are several conventions used to differentiate between Tk/Tcl
 master/child attributes and these are sometimes conflicting in their use throughout
 the comments, they are listed below
 Panel: (a window) a frame with a title bar
 Master: not to be confused with Tcl/Tk master attribute. The Master (capitalized)
  refers to the main gui panel controlling all other gui subpanels
 master: (uncapitalized) not to be confused with Tcl/Tk master attribute. A panel
  that controls another panel
 slave: a panel that is controlled by another panel. Every panel but the Master
  is a slave panel.
 _chief: a panels controlling panel
 _panels: a slave/child panel
 data: when refering to data that a panel shows, "singular" identifies data
  that is not referenced/used elsewhere in the program and "static" identifies
  data that does not change (or changes only seldomly). If not decorated, then
  data is assumed to be shared among multiple panels - changes to data in one panel
  is reflected in other panels

NOTE:
 - Assumes a database backend (although could be used with any type of data i.e
   xml or csv) but due to implementations varying across DBs and APIS, does not
     assume what database is used and therefore leaves majority of DB functionality
     to the derived class(es).
 - a panel may be a master panel and a slave panel.
 - one and only panel will be "The Master" Panel

This was originally written in 2009 but was forgotten after two deployments.
Dragging it back out IOT to use a subset for the LOBster program, I noticed that
there were a lot of small errors, irrelevant or redudant code and code that just
did not make sense. So, I am starting basically from scratch and adding the code
for subclasses as they becomes necessary.
"""

__name__ = 'panel'
__license__ = 'GPL v3.0'
__version__ = '0.13.7'
__date__ = 'March 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import os                         # files operations etc
import time                       # dtg parsing etc
import pickle                     # load and dump
import threading                  # for threads
import Tkinter as tk              # gui constructs
import tkFont                     # gui fonts
import ttk                        # ttk widgets
import tkMessageBox as tkMB       # info dialogs
import tkFileDialog as tkFD       # file gui dialogs
import tkSimpleDialog as tkSD     # input dialogs
from PIL import Image,ImageTk     # image input & support

#### LOG MESSAGE TYPES ####
LOG_NOERR = 0
LOG_WARN  = 1
LOG_ERR   = 2
LOG_NOTE  = 3

# HELPER FUNCTIONS

# return the width in pixels of the string s or if s is an integer, the length
# of s '0's
def lenpix(s):
    if type(s) == type(''): return tkFont.Font().measure(s)
    else: return tkFont.Font().measure('0') * s

#### PANEL EXCEPTIONS ####
class PanelException(Exception): pass # TopLevel generic error

class PanelRecord(tuple):
    """
     a record of a panel used as an item in a list of active "slave" panels
      tk - the Toplevel
      pnl - access this panel's methods
      desc - string description of this panel
    """
    # noinspection PyInitNewSignature
    def __new__(cls,tk,pnl,desc):
        return super(PanelRecord,cls).__new__(cls,tuple([tk,pnl,desc]))
    @property
    def tk(self): return self[0]
    @property
    def pnl(self): return self[1]
    @property
    def desc(self): return self[2]

#### helper dialogs

class PasswordDialog(tkSD.Dialog):
    """ PasswordDialog - (Modal) prompts user for password, hiding input """
    def __init__(self,parent):
        tkSD.Dialog.__init__(self,parent)
        self._entPWD = None
        self._canceled = False
    def body(self,master):
        self.title('sudo Password')
        ttk.Label(master,text='Password: ').grid(row=0,column=1)
        self._entPWD = ttk.Entry(master,show='*')
        self._entPWD.grid(row=0,column=1)
        return self._entPWD
    def validate(self):
        if self._entPWD.get() == '': return 0
        return 1
    def apply(self):
        # noinspection PyAttributeOutsideInit
        self.pwd = self._entPWD.get()

#### SUPER GUI CLASSES ####

class Panel(ttk.Frame):
    """
     Panel: This is the base class from which which all (non-modal) gui classes
     are derived
      1) traps the exit from the title bar and passes it to delete()
      2) maintains a dictionary of opened slave panels
        self._panels[panelname] => panelrecord where:
         panelname is the unique name given by Toplevel._name
         panelrec is a PanelRecord tuple
        NOTE: there may be multiple panels with the same desc but all panels
        can be uniquely identified by the self.name
      3) provides functionality to maintain/manipulate the slave panel dict
      4) allows for the setting/display of an icon
      5) provides for setting/unsetting a busy cursor on the panel
        
     Derived classes must implement
      delete - user exit trap
      close - normal close

     Derive classes should implement
      notifyclose if the derived class needs to process closing slaves
    """
    # noinspection PyProtectedMember
    def __init__(self,tl,ipath=None,resize=False):
        """
         tl - this is the Toplevel widget for this panel (managed directly
          by the window manger)
         ipath - path of icon (if one) to display the title bar
         resize - allow resize of Panel ornot
        """
        ttk.Frame.__init__(self,tl)
        self._appicon = ImageTk.PhotoImage(Image.open(ipath)) if ipath else None
        if self._appicon: self.tk.call('wm','iconphoto',self.master._w,self._appicon)
        self.master.protocol("WM_DELETE_WINDOW",self.delete)
        self._panels = {}
        self.grid(row=0,column=0,sticky='nwse')
        if not resize: self.master.resizable(0,0)

    # properties/attributes
    @property
    def name(self): return self._name

    # virtual methods
    def delete(self): raise NotImplementedError("Panel::delete") # user initiated
    def close(self): raise NotImplementedError("Panel::close") # self/master initiated

    ### busy/notbusy

    def setbusy(self,on=True):
        """ set busy cursor on this panel if on is True, otherwise set normal """
        if on: self.master.config(cursor='watch')
        else: self.master.config(cursor='')

    #### slave panel storage functions

    def notifyclose(self,name):
        """ slave panel known by name is notifying of a pending close """
        del self._panels[name]

    def addpanel(self,name,panelrec):
        """ adds the panel record panelrec having with unique name to internal """
        self._panels[name] = panelrec

    def killpanel(self,name):
        """ force the panel identifed by name to quit - panel may not cleanup """
        if not name in self._panels: return
        self._panels[name].tk.destroy()
        del self._panels[name]

    def deletepanel(self,name):
        """ delete the panel with name and remove it from the internal dict """
        if not name in self._panels: return
        self._panels[name].pnl.close()
        del self._panels[name]

    def deletepanels(self,desc):
        """ deletes all panels with desc """
        for panel in self.getpanels(desc,False):
            panel.pnl.close()
            del self._panels[panel.pnl.name]

    def getpanel(self,desc,pnlOnly=True):
        """
         returns the first panel with desc or None
         if pnlOnly is True returns the panel object otherwise returns the
         PanelRecord
        """
        for name in self._panels:
            if self._panels[name].desc == desc:
                if pnlOnly: return self._panels[name].pnl
                else: return self._panels[name]
        return None
        
    def getpanels(self,desc,pnlOnly=True):
        """
         returns all panels with desc or [] if there are none open
         if pnlOnly is True returns the panel object otherwise returns the
         PanelRecord
        """
        opened = []
        for name in self._panels:
            if self._panels[name].desc == desc:
                if pnlOnly: opened.append(self._panels[name].pnl)
                else: opened.append(self._panels[name])
        return opened

    def haspanel(self,desc):
        """ returns True if there is at least one panel with desc """
        for name in self._panels:
            if self._panels[name].desc == desc: return True
        return False

    def numpanels(self,desc):
        """ returns a count of all panels with desc """
        n = 0
        for name in self._panels:
            if self._panels[name].desc == desc: n +=1
        return n

    def closepanels(self):
        """ notifies all open panels to close """
        for name in self._panels: self._panels[name].pnl.close()

    # message box methods
    def err(self,t,m): tkMB.showerror(t,m,parent=self)
    def warn(self,t,m): tkMB.showwarning(t,m,parent=self)
    def info(self,t,m): tkMB.showinfo(t,m,parent=self)
    def ask(self,t,m,opts=None):
        if opts == 'retrycancel': return tkMB.askretrycancel(t,m,parent=self)
        elif opts == 'yesno': return tkMB.askyesno(t,m,parent=self)
        elif opts == 'okcancel': return tkMB.askokcancel(t,m,parent=self)
        else: return tkMB.askquestion(t,m,parent=self)
    def unimplemented(self): self.warn('Note',"This function not currently implemented")

class SlavePanel(Panel):
    """
     SlavePanel - defines a slave panel which has a controlling panel. i.e. it
     is opened dependant on and controlled by another panel. The name can be
     a misnomer as this class can also control slave panels

     Derived classes must implement:
      _shutdown: perform necessary cleanup functionality
      pnlreset: master panel is requesting the panel to reset itself
      pnlupdate: master panel is requesting the panel to update itself

    Derived classes should override:
     delete if they want to dissallow user from closing the panel
     notifyclose if they need to further handle closing Slave panels

     NOTE: The SlavePanel itself has no methods to define gui widgets, i.e.
      menu, main frame etc
    """
    def __init__(self,tl,chief,ttl,ipath=None,resize=False):
        """ chief is the controlling (master) panel """
        Panel.__init__(self,tl,ipath,resize)
        self._chief = chief
        self.master.title(ttl)

    # abstract methods must be implemented
    def _shutdown(self): raise NotImplementedError("SlavePanel::_shutdown")
    def pnlreset(self): raise NotImplementedError("SlavePanel::pmlreset")
    def pnlupdate(self): raise NotImplementedError("SlavePanel::pnlupdate")

    def logwrite(self,msg,mtype=LOG_NOERR):
        """ write messages to primary log """
        self._chief.logwrite(msg,mtype)

    def delete(self):
        """ user initiated - notify master of request to close """
        self._chief.notifyclose(self.name)
        self.close()

    def close(self):
        """
         master panel is notifying us to close, notify any slave panels to close,
         cleanup, then quit
        """
        self.closepanels()
        self._shutdown()
        self.master.destroy()

class SimplePanel(SlavePanel):
    """
     Defines a simple panel with body. Should be used to define simple description
     panels with minimal user interaction displaying static data. SimplePanels are
     not expected to have any slave panels. Additionally since they show singular
     static data, SimplePanels are not expected to display information that needs
     to be updated or reset.

     Derived class must implement:
      _body: define gui widgets
      _shutdown, pnlreset, pnlupdate from SlavePanel

     Derived class should override:
      pnlreset,pnlupdate if dynamic data is being displayed
      _shutdown if any cleanup needs to be performed prior to closing
    """
    def __init__(self,tl,chief,ttl,iconpath=None,resize=False):
        SlavePanel.__init__(self,tl,chief,ttl,iconpath,resize)
        self.grid(row=0,column=0,sticky='nwse')
        self._body()
    def _body(self): raise NotImplementedError("SimplePanel::_body")
    def pnlreset(self): pass
    def pnlupdate(self): pass
    def _shutdown(self): pass

class ConfigPanel(SlavePanel):
    """
     Configuration file view/edit panel. Provides a frame for input widgets and
     a button frame with
      ok: writes new values to config file and exits
      apply: writes new values to config file
      widgetreset: resets to original file (not to be confused with SlavePanel::Reset)
      cancel: exits without writing to config file

     Derived classes must implement
      _makegui add widgets to view/edit configuration file entries
      _initialize initial entry of config file values into the widgets. It is
        also used by the reset to button
      _validate validate entries before writing (derived class must handle
       displaying error messages to user) returns True if all widget entries
       are valid, False otherwise
      _write writes the values of the entries into the config file
    """
    def __init__(self,tl,chief,ttl,resize=False):
        """ initialize configuration panel """
        SlavePanel.__init__(self,tl,chief,ttl,"widgets/icons/config.png",resize)

        # set up the input widget frame
        frmConfs = ttk.Frame(self)
        self._makegui(frmConfs)
        frmConfs.grid(row=0,column=0,sticky='ns')

        # # four buttons, Ok, Apply, Reset and Cancel
        frmBtns = ttk.Frame(self)
        frmBtns.grid(row=1,column=0,sticky='ns')
        ttk.Button(frmBtns,text='OK',width=6,command=self.ok).grid(row=0,column=0)
        ttk.Button(frmBtns,text='Apply',width=6,command=self.apply).grid(row=0,column=1)
        ttk.Button(frmBtns,text='Reset',width=6,command=self.widgetreset).grid(row=0,column=2)
        ttk.Button(frmBtns,text='Cancel',width=6,command=self.delete).grid(row=0,column=3)

        # insert values from config file
        self._initialize()

    def _makegui(self,frm): raise NotImplementedError("ConfigPanel::_makegui")
    def _initialize(self): raise NotImplementedError("ConfigPanel::_initialize")
    def _validate(self): raise NotImplementedError("ConfigPanel::_validate")
    def _write(self): raise NotImplementedError("ConfigPanel::_write")

    # Slave Panel abstract methods we do not need for this class
    def _shutdown(self): pass
    def pnlupdate(self): pass
    def pnlreset(self): pass

    def ok(self):
        """ validate entries and if good write to file then close """
        if self._validate():
            self._write()
            self.delete()

    def apply(self):
        """ validate entries and if good, write to file but leave open """
        if self._validate(): self._write()

    def widgetreset(self):
        """ reset entries to orginal configuration file """
        self._initialize()

class TabularPanel(SlavePanel):
    """
     TabularPanel - A simple SlavePanel to display tabular information and the
     option to add widgets to a topframe and/or bottom frame. Derived classes can
     configure the number of columns, and whether or not to include headers for
     the columns. If headers are present, sorting (on the column header) will also
     be included.

     NOTE: this class does not define any methods to insert/remove/delete from
      this list

     Derived class must implement:
      _shutdown: perform necessary cleanup functionality
      pnlreset: Master panel is requesting the panel to reset itself
      pnlupdate: Master panel is requesting the panel to update itself

     Derived classes should implement:
      topframe if any widgets need to be added to the top frame
      bottomframe if any widgets need to be added to the bottom frame
      str2key if there is a desired 'mapping' from the tree's internal id
       type of str
      treerc to implement any right click actions on the tree

     Derived classes should override
      treeca: set to pass to dissallow select all

     Derived classes can also manipulate the style of the tree as desired i.e.
      change selection mode, display of icons, headers etc
    """
    def __init__(self,tl,chief,ttl,h,cols=None,ipath=None,resize=False):
        """
         initialize
         tl: the Toplevel of this panel
         chief: the master/controlling panel
         ttl: title to display
         h: # of lines to configure the treeview's height
         cols: a list of tuples col<i> =(l,w,t) where:
           l is the text to display in the header
           w is the desired width of the column in pixels
           t is the type of data in the column
         ipath: path of appicon
         resize: allow Panel to be resized by user
        """
        SlavePanel.__init__(self,tl,chief,ttl,ipath,resize)

        # create and allow derived classes to setup top frame
        frmT = ttk.Frame(self)
        if self.topframe(frmT): frmT.grid(row=0,column=0,sticky='nwse')

        # setup the main frame (NOTE: we set the row to 1 regardless of topframe)
        frmM = ttk.Frame(self)
        frmM.grid(row=1,column=0,sticky='nwse')

        # create a multi-column Tree
        self._tree = ttk.Treeview(frmM)
        self._tree.grid(row=0,column=0,sticky='nwse')
        self._tree.config(height=h)
        self._tree.config(selectmode='extended')

        # with attached horizontal/vertical scrollbars
        vscroll = ttk.Scrollbar(frmM,orient=tk.VERTICAL,command=self._tree.yview)
        vscroll.grid(row=0,column=1,sticky='ns')
        self._tree['yscrollcommand'] = vscroll.set
        hscroll = ttk.Scrollbar(frmM,orient=tk.HORIZONTAL,command=self._tree.xview)
        hscroll.grid(row=1,column=0,sticky='ew')
        self._tree['xscrollcommand'] = hscroll.set

        # configure the headers
        self._ctypes = [] # the type in this column
        self._tree['columns'] = [t[0] for t in cols]
        # TODO use enumerate here
        for i in xrange(len(cols)):
            # for each one set the column to the use specified width (or 0)
            # and set the text for each header if present as well as the sort
            # functionality (the sort functionality is set in a separate fct)
            self._ctypes.append(cols[i][2])
            try:
                w = max(lenpix(cols[i][0]),cols[i][1])
                if w is None: w = 0
            except:
                w = 0
            self._tree.column(i,width=w,anchor=tk.CENTER)
            if cols[i][0] != '': self._makesort(i,cols[i][0])

        # bind right click on the tree
        self._tree.bind('<Button-3>',self.treerc)
        self._tree.bind('<Control-a>',self.treeca)

        # allow a bottom frame
        frmB = ttk.Frame(self)
        if self.bottomframe(frmB): frmB.grid(row=2,column=0,sticky='nwse')

    def sortbycol(self,col,asc):
        """ sorts the col in ascending order if asc or descending otherwise """
        vs = [(self._tree.set(k,col),k) for k in self._tree.get_children('')]
        vs.sort(key=lambda t: self._ctypes[col](t[0]),reverse=not asc)
        for i, (_,k) in enumerate(vs): self._tree.move(k,'',i)
        self._tree.heading(col,command=lambda:self.sortbycol(col,not asc))

    def str2key(self,s): return s
    def key2str(self,k): return str(k)
    def treerc(self,event): pass
    def treeca(self,event): self._tree.selection_set(self._tree.get_children(''))

    # noinspection PyMethodMayBeStatic
    def topframe(self,frm): return None # override to add widgets to topframe
    # noinspection PyMethodMayBeStatic
    def bottomframe(self,frm): return None # override to add widgets to bottomframe

    def _makesort(self,col,text):
        """ add column header with label text at col index col (w/ sort fct) """
        self._tree.heading(col,text=text,command=lambda: self.sortbycol(col,True))

class PollingTabularPanel(TabularPanel):
    """
     PollingTabularPanel - a TabularPanel that updates itself periodically
     through the after function
     Derived classes must implment the pnlupdate function which is used by the
      polling functionaity
    """
    def __init__(self,tl,chief,ttl,h,cols=None,ipath=None,resize=False,polltime=500):
        """
         initialize the PollingTabularPanel
         tl: the Toplevel of this panel
         chief: the master/controlling panel
         ttl: title to display
         h: # of lines to configure the treeview's height
         cols: a list of tuples col<i> =(l,w,t) where:
           l is the text to display in the header
           w is the desired width of the column in pixels
           t is the type of data in the column
         ipath: path of appicon
         resize: allow Panel to be resized by user
         polltime: time in microseconds betw/ after calls
        """
        TabularPanel.__init__(self,tl,chief,ttl,h,cols,ipath,resize)
        self._polltime = polltime
        self.pnlupdate()
        self.after(self._polltime,self.poll)
    def poll(self):
        self.pnlupdate()
        self.after(self._polltime,self.poll)

class DBPollingTabularPanel(PollingTabularPanel):
    """
     DBPollingTabularPanel - a TabularPanel that updates itself periodically
     through the after function using data from a db connection. This panel
     has an internal locking mechanism to ensure that the data being displayed
     is not modified by separate functions simultaenously. Methods pnlupdate and
     sortbycol are wrapped by lock aquisitions/release to ensure integrity.

     Derived classes must implement:
      _update_: update data (this function is wrapped by locking mechanism)
      _connect: connect to backend database & get a cursor

     Derived class should implement:
      the locking mechanism for any functions that change the data displayed
      in the treeview
    """
    def __init__(self,tl,chief,connect,ttl,h,cols=None,ipath=None,resize=False,polltime=500):
        """
         initialize the PollingTabularPanel
         tl: the Toplevel of this panel
         chief: the master/controlling panel
         connect: connect string to get a db connection
         ttl: title to display
         h: # of lines to configure the treeview's height
         cols: a list of tuples col<i> =(l,w,t) where:
           l is the text to display in the header
           w is the desired width of the column in pixels
           t is the type of data in the column
         ipath: path of appicon
         resize: allow Panel to be resized by user
         polltime: time in microseconds betw/ after calls
        """
        self._l = threading.Lock()
        self._conn = self._curs = None
        self._connect(connect)
        PollingTabularPanel.__init__(self,tl,chief,ttl,h,cols,ipath,resize,polltime)
    def pnlupdate(self):
        """ wraps updating with locking """
        self._l.acquire()
        try:
            self._update_()
        except: pass
        finally:
            self._l.release()
    def _update_(self): raise NotImplementedError("DBPolling::_connect")
    def sortbycol(self,col,asc):
        """wrap parent sortbycol with thread safety"""
        self._l.acquire()
        try:
            PollingTabularPanel.sortbycol(self,col,asc)
        except: pass
        finally:
            self._l.acquire()
    def _shutdown(self):
        if self._curs: self._curs.close()
        if self._conn: self._conn.close()
    def _connect(self,c): raise NotImplementedError("DBPolling::_connect")

class LogPanel(TabularPanel):
    """
     LogPanel -  a singular panel which displays information pertaining to the
     "program", cannot be closed by the user only by the MasterPanel
    """
    def __init__(self,tl,chief):
        """
         initialzie LogPanel
         tl: the Toplevel
         chief: the master panel
        """
        TabularPanel.__init__(self,tl,chief,"Log",5,
                              [('',lenpix('[+] '),str),
                               ('',lenpix('00:00:00'),str),
                               ('',lenpix(30),str)],
                              "widgets/icons/log.png")
        self._l = threading.Lock() # lock for writing
        self._n = 0                # current entry number

        # configure the tree to left justify the message column, hide icon/headers
        # and use a darkgray background to better highlight the colored text
        self._tree.column(2,anchor='w')
        self._tree['show'] = ''
        ttk.Style().configure('Log.Treeview',
                              fieldbackground="darkgray",
                              background='darkgray')
        self._tree['style'] = 'Log.Treeview'
        self._tree.config(selectmode='none')

        # set symbols for message types and tags for colored text
        self._symbol = ['[+]','[?]','[-]','[!]']
        self._tree.tag_configure(LOG_NOERR,foreground='green')
        self._tree.tag_configure(LOG_WARN,foreground='yellow')
        self._tree.tag_configure(LOG_ERR,foreground='red')
        self._tree.tag_configure(LOG_NOTE,foreground='blue')

    def delete(self): pass    # user can never close only the primary chief
    def pnlreset(self): pass     # nothing needs to be reset
    def pnlupdate(self): pass    # nothing needs to be updated
    def _shutdown(self): pass # nothing needs to be cleaned up
    def logwrite(self,msg,mtype=LOG_NOERR):
        """ writes message msg of type mtype to the log """
        self._l.acquire()
        try:
            self._tree.insert('','end',iid=str(self._n),
                             values=(self._symbol[mtype],time.strftime('%H:%M:%S'),msg),
                             tags=(mtype,))
            self._n += 1
            self._tree.yview('moveto',1.0)
        except:
            pass
        finally:
            self._l.release()
    def delayedwrite(self,ms):
        """
         writes each msg in ms to the log where msg is a tuple (time,text,type)
          time - time text occurred as a string
          text - message text
          type - type of message
        """
        self._l.acquire()
        try:
            for m in ms:
                self._tree.insert('','end',iid=str(self._n),
                                 values=(self._symbol[m[2]],m[0],m[1]),
                                 tag=(m[2],))
                self._n += 1
                self._tree.yview('moveto',1.0)
        except Exception as e:
            pass
        finally:
            self._l.release()

class TailLogPanel(TabularPanel):
    """
     Displays log data from a file - graphically similar to tail -f <file>
     utilizing an after function
    """
    def __init__(self,tl,chief,ttl,polltime,logfile,w=20,resize=False):
        """
         initializes TailLogPanel to read from the file specified logfile
         tl: the Toplevel
         chief: the master panel
         ttl: title to display
         polltime: polltime in milliseconds to pause between file checks
         logfile: the log file to tail
         width: width of the display (in characters
         resize: allow resize
        """
        TabularPanel.__init__(self,tl,chief,ttl,5,[('',lenpix(w),str)],
                              "widgets/icons/log.png",resize)
        # check validity of logfile first
        if not os.path.exists(logfile) and not os.path.isfile(logfile):
            self._chief.logwrite("Log File %s does not exist" % logfile,LOG_ERR)
            return

        # member variables
        self._n = 0
        self._lf = logfile
        self._polltime = polltime
        self._ctime = None
        self._offset = None

        # configure tree to hide icon/headers and left-justify message column
        self._tree['show'] = ''
        self._tree.column(0,anchor='w')

        # run our polling function
        self.tail()

    def tail(self):
        """ checks log file for updates & writes if present """
        # if first time, set internals
        if self._ctime is None:
            fin = None
            try:
                self._ctime = os.stat(self._lf).st_ctime
                fin = open(self._lf,'r')
                self._newlines(fin.readlines())
                self._offset = fin.tell()
            except Exception as e:
                self._chief.logwrite("Log for %s failed %s" % (os.path.split(self._lf)[1],e),LOG_ERR)
            finally:
                if fin: fin.close()
        else:
            # check for updates
            fin = None
            try:
                ctime = os.stat(self._lf).st_ctime
                if ctime != self._ctime:
                    fin = open(self._lf,'r')
                    fin.seek(self._offset-1)
                    self._newlines(fin.readlines())
                    self._offset = fin.tell()
                    self._ctime = ctime
            except Exception as e:
                self._chief.logwrite("Log for %s failed %s" % (os.path.split(self._lf)[1],e),LOG_ERR)
            finally:
                if fin: fin.close()

        # pause during polltime
        self.after(self._polltime,self.tail)

    # VIRTUAL METHOD OVERRIDES

    def pnlreset(self):
        """ resets the log panel """
        # reset internal structures and clear the list
        if self._n:
            self._n = 0
            self._ctime = None
            self._offset = None
            self._tree.delete(*self._tree.get_children())

    def pnlupdate(self): pass    # no need to implement
    def _shutdown(self): pass # no need to implement

    # PRIVATE HELPER
    def _newlines(self,lines):
        """ writes new lines to panel """
        for line in lines:
            self._tree.insert('','end',iid=str(self._n),values=(line.strip(),))
            self._n += 1
            self._tree.yview('moveto',1.0)

class MasterPanel(Panel):
    """
     The MasterPanel is the primary panel which controls the flow of the overall
     program. The MasterPanel defines a class meant to handle the primary data,
     opening, closing children panels etc.

     Derived classes should implement:
      _initialize -> if there is functionality that should be started
      _shutdown -> if there is functionality that should be cleanly stopped
      _makemenu -> to implement any menu
      getstate -> if there is a State of the main panel that needs to be known
       by slave panels
      showpanel -> derive for use in toolsload (loads saved panel configs)
      delete and close if the derived class must further handle shutting down

     Derived classes can:
      call guiload, _makemenu in initialization function as needed
    """
    def __init__(self,tl,ttl,datatypes=None,ipath=None,resize=False):
        """
         ttl: title of the window/panel
         tl: the toplevel of this panel
         datatypes: list of strings for data bins, etc
         logpanel: if True, will initiate a logpanel
         ipath: path of image to show as icon for this panel
        """
        Panel.__init__(self,tl,ipath,resize)
        self.tk = tl

        # internal members
        self._menubar = None        # the panel's menu 9if any)
        self._state = 0             # bitmask state (define in derived class)
        self._conn = None           # the main connection (if any) to the backend db)

        # data bins, registered panels, and what data is hidden, selected
        self._audit_registered = {} # panels auditing for notification
        self._bin = {}              # data dictionaries
        self._hidden = {}           # keys of hidden data in bin
        self._selected = {}         # keys of selected data in bin
        for datatype in datatypes:
            self._audit_registered[datatype] = []
            self._bin[datatype] = {}
            self._hidden[datatype] = []
            self._selected[datatype] = []   

        # set the title
        self.master.title(ttl)
        self.grid(sticky='nwse')
        
        # try and make the menu
        self._makemenu()
        if self._menubar:
            try:
                self.master.config(menu=self._menubar)
            except AttributeError:
                self.master.tk.call(self.master,"config","-menu",self._menubar)

        # initialiez
        self._initialize()

        # is there a default toolset saved?
        self.update_idletasks()

    # Panel overrides

    def delete(self):
        """ title bar exit trap """
        self.close()

    def close(self):
        """ cleanly exits - shuts down as necessary """
        ans = self.ask('Quit?','Really Quit')
        if ans == 'no':
            return
        else:
            self.update()
            self.logwrite('Quitting...')
            self._shutdown()
            self.quit()

    def notifyclose(self,name):
        """
         override notifyclose, before allowing requesting panel to close,
         deregister it we need to remove all notification requests from
         the panel before deleting it
        """
        if name in self._panels: self.audit_deregister(name)
        del self._panels[name]

    def _initialize(self): pass
    def _shutdown(self): pass
    def _makemenu(self): pass
    def showpanel(self,t): raise NotImplementedError("MasterPanel::showpanel")

    def viewlog(self):
        """ displays the log panel """
        panel = self.getpanels("log",False)
        if not panel:
            t = tk.Toplevel()
            pnl = LogPanel(t,self)
            self.addpanel(pnl._name,PanelRecord(t,pnl,"log"))
            pnl.update_idletasks()
            t.wm_geometry("-0-0")
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

    def guisave(self):
        """ saves current toolset configuration """
        fpath = tkFD.asksaveasfilename(title='Save Toolset',
                                       filetypes=[('Toolset files','*.ts')])
        if fpath:
            gs = self.tk.winfo_geometry().split('+')
            ts = {}
            for panel in self._panels:
                c = self._panels[panel]
                c.pnl.update_idletasks()
                if c.desc != 'log':
                    if c.desc in ts:
                        ts[c.desc].append(c.tk.winfo_geometry())
                    else:
                        ts[c.desc] = [c.tk.winfo_geometry()]
            try:
                f = open(fpath,'wb')
                pickle.dump(ts,f)
                f.close()
            except Exception as e:
                self.logwrite(e,LOG_ERR)

    def guiload(self,fpath=None):
        """ loads a saved toolset configuration """
        if not fpath:
            fpath = tkFD.askopenfilename(title='Open Toolset',
                                         filetypes=[('Toolset files','*.ts')],
                                         parent=self)
        
        if fpath:
            # open & get the saved windows + their geometry
            try:
                f = open(fpath,'rb')
                ts = pickle.load(f)
                f.close()
            except Exception as e:
                self.logwrite(e,LOG_ERR)
            else:
                # for each saved open it (unless it already exists) and move to 
                # saved position
                for t in ts:
                    self.deletepanels(t)
                    for _ in ts[t]: self.showpanel(t)
                
                    i = 0
                    for panel in self.getpanels(t,False):
                        panel.tk.wm_geometry(ts[t][i])
                        i += 1

    def logwrite(self,msg,mtype=LOG_NOERR):
        """ writes msg to log or shows in error message """
        log = self.getpanel("log",True)
        if log:
            log.logwrite(msg,mtype)
        elif mtype == LOG_ERR:
             self.err('Error',msg)

    # Panel accessors

    @property
    def getstate(self): return self._state

    # Panel/data update functionality

    def audit_register(self,dtype,name):
        """ register panel for dtype audits """
        self._audit_registered[dtype].append(name)

    def audit_deregister(self,name):
        """
         deregister panel from all audits
        """
        for registered in self._audit_registered:
            if name in self._audit_registered[registered]:
                self._audit_registered[registered].remove(name)

    def hideentries(self,dtype,name,ids):
        """
         notification that the panel name is hiding ids - will notify all audit 
         registered panels that these ids are hidden
        """
        self._hidden[dtype].extend(ids)
        for panel in self._audit_registered[dtype]:
            if panel != name:
                self._panels[panel].pnl.notifyhiddencb(dtype,ids)

    def selectentries(self,dtype,name,ids):
        """
         notification that the panel name has selected ids - will notify all audit
         registered panels that these ids are selected
        """
        self._selected[dtype] = ids
        for panel in self._audit_registered[dtype]:
            if panel != name: 
                self._panels[panel].pnl.notifyselectcb(dtype,ids)
        
    def restorehidden(self,dtype,name):
        """
         notification that the panel name is restoring ids - will notify all audit
        registered panels that all ids are being restored
        """
        h = self._hidden[dtype]
        self._hidden[dtype] = []
        for panel in self._audit_registered[dtype]:
            if panel != name:
                self._panels[panel].pnl.notifyrestorecb(dtype,h)

    def pnlupdatepanels(self):
        """ notify open panels something has changed """
        # use keys() to handle event where a panel may close itself
        for name in self._panels: self._panels[name].pnl.pnlupdate()

    def pnlresetpanels(self):
        """ notify open panels everything is reset """
        for name in self._panels: self._panels[name].pnl.pnlreset()