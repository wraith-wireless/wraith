#!/usr/bin/env python
""" panel.py - defines a suite of graphical windows called panes

Defines a graphic suite based on Tix where a set of non-modal panels operate under
the control of a master panel and execute tasks, display information independently
of (or in conjuction with) this panel and other panels. (Think undocked windows)
Panels can be configured so that they can be opened, closed, "raised", minimized
by the user or only by a calling panel.
NOTE:
 a panel may be a master panel and a slave panel.
 one and only panel will be "The Master" Panel

This was actually written in 2009 but was forgotten after two deployments.
Dragging it back out IOT to use a subset for the LOBster program, I noticed that
there were a lot of small errors, irrelevant or redudant code and code that just
did not make sense. So, I am starting basically from scratch and adding the code
for subclasses as they becomes necessary.

 TODO:
   3) handle no icons or invalid icon paths
   4) issues happen with the TailLogger after the corresponding logfile is deleted
   5) create a method in MasterPanel to handle creation of signular pattern i.e.
     panel = self.getpanels(desc,False)
     if not panel:
        t = ttk.Toplevel()
        pnl = PanelClase(t,self,argc)
        self.addpanel(pnl.name,gui.PanelRecord(t,pnl,desc))
      else:
        panel[0].tk.deiconify()
        panel[0].tk.lift()
   7) disable/enable resize as necessary and if enabled ensure widgets resize
      as necessary -> self.master.resizable(0,0)
   8) Treeview horizontal does not scroll
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

# HELPER FUNCTIONS

# return the width in pixels of the string s
def lenpix(s): return tkFont.Font().measure(s)

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
        self.entPWD = None
        self.canceled = False
    def body(self,master):
        self.title('sudo Password')
        ttk.Label(master,text='Password: ').grid(row=0,column=1)
        self.entPWD = ttk.Entry(master,show='*')
        self.entPWD.grid(row=0,column=1)
        return self.entPWD
    def validate(self):
        if self.entPWD.get() == '': return 0
        return 1
    def apply(self):
        self.pwd = self.entPWD.get()

#### SUPER GUI CLASSES ####

class Panel(ttk.Frame):
    """
     Panel: This is the base class from which which all non-modal gui classes are
      derived
      1) traps the exit from the title bar and passes it to delete()
      2) maintains a dictionary of opened slave panels
        self._panels[panelname] => panelrecord where:
         panelname is the unique name given by Toplevel._name
         panelrec is a PanelRecord tuple
        NOTE: there may be multiple panels with the same desc but all panels
        can be uniquely identified by the self.name
      3) provides functionality to handle storage/retrieval/deletion of slave
         panels
      4) allows for the setting/display of an icon
        
     Derived classes must implement
      delete - user exit trap
      close - normal close

     Derive classes should implement
      notifyclose if the derived class needs to process closing slaves
    """
    # noinspection PyProtectedMember
    def __init__(self,tl,iconPath=None,resize=False):
        """
         tl - this is the Toplevel widget for this panel (managed directly
          by the window manger)
         iconPath - path of icon (if one) to display the title bar
         resize - allow resize of Panel ornot
        """
        ttk.Frame.__init__(self,tl)
        self.appicon = ImageTk.PhotoImage(Image.open(iconPath)) if iconPath else None
        if self.appicon: self.tk.call('wm','iconphoto',self.master._w,self.appicon)
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
                if pnlOnly:
                    opened.append(self._panels[name].pnl)
                else:
                    opened.append(self._panels[name])
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

class SlavePanel(Panel):
    """
     SlavePanel - defines a slave panel which has a controlling panel. i.e. it
     is opened dependant on and controlled by another panel. The name can be
     a misnomer as this class can also control slave panels

     Derived classes must implement:
      _shutdown: perform necessary cleanup functionality
      reset: Master panel is requesting the panel to reset itself
      update: Master panel is requesting the panel to update itself

    Derived classes should override:
     delete if they want to dissallow user from closing the panel
     notifyclose if they need to further handle closing Slave panels

     NOTE: The SlavePanel itself has no methods to define gui widgets, i.e.
      menu, main frame etc
    """
    def __init__(self,tl,chief,title,iconPath=None,resize=False):
        """ chief is the controlling (Master) panel """
        Panel.__init__(self,tl,iconPath,resize)
        self._chief = chief
        self.master.title(title)

    def _shutdown(self):
        """ cleanup functionality prior to quitting """
        raise NotImplementedError("SlavePanel::_shutdown")

    def reset(self):
        """ reset to original/default setup """
        raise NotImplementedError("SlavePanel::reset")

    def update(self):
        """ something has changed, update ourselve """
        raise NotImplementedError("SlavePanel::update")

    def delete(self):
        """user initiated - notify master of request to close """
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
     not expected to have any slave panels. Additionally, showing static data,
     SimplePanels are not expected to display information that needs to be
     updated or reset.

     Derived class must implement:
      _body: define gui widgets
      in addition to SlavePanel::_shutdown, SlavePanel::reset, SlavePanel::update

     Derived class should override:
      reset,update if dynamic data is being displayed
      _shutdown if any cleanup needs to be performed prior to closing
    """
    def __init__(self,tl,chief,title,iconpath=None,resize=False):
        SlavePanel.__init__(self,tl,chief,title,iconpath,resize)
        frm = ttk.Frame(self)
        frm.grid(row=0,column=0,sticky='nwse')
        self._body(frm)
    def _body(self,frm): raise NotImplementedError("SimplePanel::_body")
    def reset(self): pass
    def update(self): pass
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
    def __init__(self,tl,chief,title,resize=False):
        """ initialize configuration panel """
        SlavePanel.__init__(self,tl,chief,"widgets/icons/config.png",resize)
        self.master.title(title)

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
    def reset(self): pass
    def update(self): pass
    def _shutdown(self): pass

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
     configure the ScrolledHList's number of columns, and whether or not to
     include headers for the columns.

     NOTE: this class does not define any methods to insert/remove/delete from
      this list

     Derived class must implement:
      _shutdown: perform necessary cleanup functionality
      reset: Master panel is requesting the panel to reset itself
      update: Master panel is requesting the panel to update itself

     Derived classes should implement:
      topframe if any widgets need to be added to the top frame
      bottomframe if any widgets need to be added to the bottom frame

     Derived classes can also manipulate the style of the tree as desired

     NOTE:
      derived classes can change selection mode and display of icon, headers
      as desired
    """
    def __init__(self,tl,chief,ttl,h,cols=None,iconPath=None,resize=False):
        """
         initialize
         tl: the Toplevel of this panel
         chief: the master/controlling panel
         ttl: title to display
         h: # of lines to configure the treeview's height
         cols: a list of tuples t =(l,w) where:
           l is the text to display in the header
           w is the desired width of the column in pixels
         iconPath: path of appicon
         resize: allow Panel to be resized by user
        """
        SlavePanel.__init__(self,tl,chief,iconPath,resize)
        self.master.title(ttl)

        # create and allow derived classes to setup top frame
        frmT = ttk.Frame(self)
        if self.topframe(frmT): frmT.grid(row=0,column=0,sticky='nwse')

        # setup the main frame (NOTE: we set the row to 1 regardless of topframe)
        frmM = ttk.Frame(self)
        frmM.grid(row=1,column=0,sticky='nwse')

        # create a multi-column Tree
        self.tree = ttk.Treeview(frmM)
        self.tree.grid(row=0,column=0,sticky='nwse')
        self.tree.config(height=h)
        self.tree.config(selectmode='none')

        # with attached horizontal/vertical scrollbars
        vscroll = ttk.Scrollbar(frmM,orient=tk.VERTICAL,command=self.tree.yview)
        vscroll.grid(row=0,column=1,sticky='ns')
        self.tree['yscrollcommand'] = vscroll.set
        hscroll = ttk.Scrollbar(frmM,orient=tk.HORIZONTAL,command=self.tree.xview)
        hscroll.grid(row=1,column=0,sticky='ew')
        self.tree['xscrollcommand'] = hscroll.set

        # configure the headers
        self.tree['columns'] = [t[0] for t in cols]
        for i in xrange(len(cols)):
            try:
                w = max(lenpix(cols[i][0]),cols[i][1])
                if w is None: w = 0
            except:
                w = 0
            self.tree.column(i,width=w,anchor=tk.CENTER)

        # allow a bottom frame
        frmB = ttk.Frame(self)
        if self.bottomframe(frmB): frmB.grid(row=2,column=0,sticky='nwse')

    # noinspection PyUnusedLocal
    def topframe(self,frm): return None # override to add widgets to topframe
    # noinspection PyUnusedLocal
    def bottomframe(self,frm): return None # override to add widgets to bottomframe

#### LOG MESSAGE TYPES ####
LOG_NOERR = 0
LOG_WARN  = 1
LOG_ERR   = 2
LOG_NOTE  = 3

class LogPanel(TabularPanel):
    """
     a singular panel which display information pertaining to the "program",
     cannot be closed by the user only by the MasterPanel
    """
    def __init__(self,tl,chief):
        TabularPanel.__init__(self,tl,chief,"Log",5,
                              [('',lenpix('[+] ')),('',lenpix('00:00:00')),('',lenpix('w')*20)],
                              "widgets/icons/log.png")
        self._l = threading.Lock() # lock for writing
        self._n = 0                # current entry number

        # configure the tree to left justify the message column, hide icon/headers
        # and use a darkgray background to better highlight the colored text
        self.tree.column(2,anchor='w')
        self.tree['show'] = ''
        ttk.Style().configure('Log.Treeview',
                              fieldbackground="darkgray",
                              background='darkgray')
        self.tree['style'] = 'Log.Treeview'

        # set symbols for message types and tags for colored text
        self._symbol = ['[+]','[?]','[-]','[!]']
        self.tree.tag_configure(LOG_NOERR,foreground='green')
        self.tree.tag_configure(LOG_WARN,foreground='yellow')
        self.tree.tag_configure(LOG_ERR,foreground='red')
        self.tree.tag_configure(LOG_NOTE,foreground='blue')

    def delete(self): pass    # user can never close only the primary chief
    def reset(self): pass     # nothing needs to be reset
    def update(self): pass    # nothing needs to be updated
    def _shutdown(self): pass # nothing needs to be cleaned up
    def logwrite(self,msg,mtype=LOG_NOERR):
        """ writes message msg of type mtype to the log """
        self._l.acquire()
        try:
            self.tree.insert('','end',iid=str(self._n),
                             values=(self._symbol[mtype],time.strftime('%H:%M:%S'),msg),
                             tags=(mtype,))
            self._n += 1
            self.tree.yview('moveto',1.0)
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
                self.tree.insert('','end',iid=str(self._n),
                                 values=(self._symbol[m[2]],m[0],m[1]),
                                 tag=(m[2],))
                self._n += 1
                self.tree.yview('moveto',1.0)
        except Exception as e:
            print e
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
        TabularPanel.__init__(self,tl,chief,ttl,5,[('',lenpix('w')*w)],
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
        self.tree['show'] = ''
        self.tree.column(0,anchor='w')

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

    def reset(self):
        """ resets the log panel """
        # reset internal structures and clear the list
        if self._n:
            self._n = 0
            self._ctime = None
            self._offset = None
            self.tree.delete(*self.tree.get_children())

    def update(self): pass    # no need to implement
    def _shutdown(self): pass # no need to implement

    # PRIVATE HELPER
    def _newlines(self,lines):
        """ writes new lines to panel """
        for line in lines:
            #print line
            self.tree.insert('','end',iid=str(self._n),values=(line.strip(),))
            self._n += 1
            self.tree.yview('moveto',1.0)

class MasterPanel(Panel):
    """
     the MasterPanel is the primary panel which controls the flow of the overall
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
    """
    def __init__(self,tl,ttl,datatypes=None,iconPath=None,resize=False):
        """
         ttl - title of the window/panel
         datatypes - list of strings for data bins, etc
         logpanel - if True, will initiate a logpanel
         iconPath - path of image to show as icon for this panel
        """
        Panel.__init__(self,tl,iconPath,resize)
        self.tk = tl
        self.menubar = None
        
        # data bins, registered panels, and what data is hidden, selected
        self.audit_registered = {} # panels auditing for notification
        self.bin = {}              # data dictionaries
        self.hidden = {}           # keys of hidden data in bin
        self.selected = {}         # keys of selected data in bin
        for datatype in datatypes:
            self.audit_registered[datatype] = []
            self.bin[datatype] = {}
            self.hidden[datatype] = []
            self.selected[datatype] = []   

        # set the title
        self.master.title(ttl)
        self.grid(sticky='nwse')
        
        # try and make the menu
        self._makemenu()
        try:
            self.master.config(menu=self.menubar)
        except AttributeError:
            self.master.tk.call(self.master,"config","-menu",self.menubar)

        # initialiez
        self._initialize()

        # is there a default toolset saved?
        if os.path.exists('default.ts'): self.guiload('default.ts')
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
            self.logwrite('Quitting...')
            #self.closepanels()
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

    @property
    def getstate(self): return None

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

    def unimplemented(self):
        """ displays info dialog with not implmented message """
        self.info('Not Implemented',"This function not currently implemented")
        
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

    # Panel/date update functionality

    def audit_register(self,dtype,name):
        """ register panel for dtype audits """
        self.audit_registered[dtype].append(name)

    def audit_deregister(self,name):
        """
         deregister panel from all audits
        """
        for registered in self.audit_registered:
            if name in self.audit_registered[registered]:
                self.audit_registered[registered].remove(name)

    def hideentries(self,dtype,name,ids):
        """
         notification that the panel name is hiding ids - will notify all audit 
         registered panels that these ids are hidden
        """
        self.hidden[dtype].extend(ids)
        for panel in self.audit_registered[dtype]:
            if panel != name:
                self._panels[panel].pnl.notifyhiddencb(dtype,ids)

    def selectentries(self,dtype,name,ids):
        """
         notification that the panel name has selected ids - will notify all audit
         registered panels that these ids are selected
        """
        self.selected[dtype] = ids
        for panel in self.audit_registered[dtype]:
            if panel != name: 
                self._panels[panel].pnl.notifyselectcb(dtype,ids)
        
    def restorehidden(self,dtype,name):
        """
         notification that the panel name is restoring ids - will notify all audit
        registered panels that all ids are being restored
        """
        h = self.hidden[dtype]
        self.hidden[dtype] = []
        for panel in self.audit_registered[dtype]:
            if panel != name:
                self._panels[panel].pnl.notifyrestorecb(dtype,h)

    def updatepanels(self):
        """ notify open panels something has changed """
        # use keys() to handle event where a panel may close itself
        for name in self._panels: self._panels[name].pnl.update()

    def resetpanels(self):
        """ notify open panels everything is reset """
        for name in self._panels: self._panels[name].pnl.reset()