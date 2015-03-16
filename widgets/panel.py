#!/usr/bin/env python
""" panel.py - defines a suite of graphical windows called panes

Panels operate under the control of a master panel and execute tasks, display
information independently of (or in conjuction with) this panel and other panels.
Panels can be configured so that they can be opened, closed, "raised", minimized
by the user or only by a calling panel

 TODO:
   3) handle no icons or invalid icon paths
"""

__name__ = 'panel'
__license__ = 'GPL v3.0'
__version__ = '0.13.5'
__date__ = 'February 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import os                         # files operations etc
import time                       # dtg parsing etc
import pickle                     # load and dump
import threading                  # for threads
#from operator import itemgetter  # iterators
import Tix                        # Tix widgets
#import Tkconstants as TKC         # tk constants
import tkMessageBox as tkMB        # info dialogs
import tkFileDialog as tkFD        # file gui dialogs
import tkSimpleDialog as tkSD      # input dialogs
from PIL import Image,ImageTk     # image input & support

#### PANEL EXCEPTIONS ####
class PanelException(Exception): pass            # TopLevel generic error

class PanelRecord(tuple):
    # noinspection PyInitNewSignature
    def __new__(cls,tk,pnl,desc):
        """
         a record of a panel used as an item in a list of active "slave" panels
          tk - toplevel
          pnl - access this panel's methods
          desc - string description of this panel
        """
        return super(PanelRecord,cls).__new__(cls,tuple([tk,pnl,desc]))
    @property
    def tk(self): return self[0]
    @property
    def pnl(self): return self[1]
    @property
    def desc(self): return self[2]

#### helper dialogs

class PasswordDialog(tkSD.Dialog):
    """ PasswordDialog - prompts user for password, hiding input """
    def __init__(self,parent):
        tkSD.Dialog.__init__(self,parent)
        self.entPWD = None
        self.canceled = False
    def body(self,master):
        self.title('sudo Password')
        Tix.Label(master,text='Password: ').grid(row=0,column=1)
        self.entPWD = Tix.Entry(master,show='*')
        self.entPWD.grid(row=0,column=1)
        return self.entPWD
    def validate(self):
        if self.entPWD.get() == '': return 0
        return 1
    def apply(self):
        self.pwd = self.entPWD.get()

#### SUPER GUI CLASSES ####

class Panel(Tix.Frame):
    """
     Panel: Superclass from which all non-modal gui classes are derived
      1) traps the exit from the title bar and passes it to derived close
      2) maintains a dictionary of opened slave panels
        self._panels["panelname"] => [panel1,panel2,...,paneln]
        NOTE: there may be multiple panels with the same desc but all panels
        can be uniquely identified by the self._name
        
     Derived classes must:
      implement close()
    """
    # noinspection PyProtectedMember
    def __init__(self,toplevel,iconPath=None):
        """
         toplevel - controling window
         iconPath - path of icon (if one) to display the title bar
        """
        self.appicon=None
        self._panels = {}
        if iconPath: self.appicon = ImageTk.PhotoImage(Image.open(iconPath))
        Tix.Frame.__init__(self,toplevel)
        self.master.protocol("WM_DELETE_WINDOW",self.delete)
        if self.appicon: self.tk.call('wm','iconphoto',self.master._w,self.appicon)

    # panel exit trap function
    def delete(self): self.close()

    # our exit function (must be defined in subclasses
    def close(self): raise NotImplementedError("Panel::close")

    #### panel list functions

    def addpanel(self,name,panel):
        """ adds the panel object panel having key name to panels """
        self._panels[name] = panel

    def deletepanel(self,name):
        """ delete the panel with name and remove it from the list """
        self._panels[name].tk.destroy()
        del self._panels[name]

    def deletepanels(self,desc):
        """ deletes all panels with desc """
        for panel in self.getpanels(desc,False): panel.pnl.close()

    def getpanel(self,desc,pnlOnly=True):
        """ returns the first panel with desc or None """
        for panel in self._panels:
            if self._panels[panel].desc == desc:
                if pnlOnly:
                    return self._panels[panel].pnl
                else:
                    return self._panels[panel]
        return None
        
    def getpanels(self,desc,pnlOnly=True):
        """ returns all panels with desc or [] if there are none open """
        opened = []
        for panel in self._panels:
            if self._panels[panel].desc == desc:
                if pnlOnly:
                    opened.append(self._panels[panel].pnl)
                else:
                    opened.append(self._panels[panel])
        return opened

    def haspanel(self,desc):
        """ returns True if there is at least one panel with desc """
        for panel in self._panels:
            if self._panels[panel].desc == desc: return True
        return False

    def numpanels(self,desc):
        """ returns a count of all panels with desc """
        n = 0
        for panel in self._panels:
            if self._panels[panel].desc == desc: n +=1
        return n

    def closepanels(self):
        """ notifies all open panels to close """
        for panel in self._panels.keys(): self._panels[panel].pnl.close()

class SlavePanel(Panel):
    """
     SlavePanel - defines a slave panel which has a controlling panel. i.e. it
     is opened dependant on another panel.
      defines:
        pnlreset - notification that the current job is being cleared
        setstates - should be overridden if subclass needs to set states based
         on changes by controlling panel
        close - allows panel to close itself (and all children panels) notifying
        controlling panel as well
     NOTE: The SlavePanel itself has no methods to define gui widgets, i.e.
      menu, main frame etc
    """
    def __init__(self,toplevel,chief,iconPath=None):
        Panel.__init__(self,toplevel,iconPath)
        self._chief = chief

    def setstates(self,state): pass

    def close(self): 
        """ close any open panels - then notify master we are closing """
        self.closepanels()
        self._chief.panelclose(self._name)

    def pnlupdate(self): pass
    def pnlreset(self): 
        """ closes all open panels - override to change """
        self.closepanels()

    def panelclose(self,name):
        """ an open "sub" panel is desiring to close """
        self.deletepanel(name)

class SimplePanel(SlavePanel):
    """
     Defines a simple panel with body
     Derived class must implement _body()
    """
    def __init__(self,toplevel,chief,title,iconpath=None):
        SlavePanel.__init__(self,toplevel,chief,iconpath)
        self.master.title(title)
        self.pack(expand=True,fill=Tix.BOTH,side=Tix.TOP)
        self._body()
    def _body(self): raise NotImplementedError("SimplePanel::_body")

class ConfigPanel(SlavePanel):
    """
     Configuration file view/edit panel. Provides a frame for input widgets and
     a button frame with
      ok: writes new values to config file and exits
      apply: writes new values to config file
      reset: resets to original file
      cancel: exits without writing to config file

     Derived classes must implement
     _confs - add widgets to view/edit configuration file entries
     _initialize - initial entry of config file values into the widgets and reset()
     _validate - validate entries before writing
     _write - writes the values of the entries into the config file
    """
    def __init__(self,toplevel,chief,title):
        """ initialize configuration panel """
        SlavePanel.__init__(self,toplevel,chief,"widgets/icons/config.png")
        self.master.title(title)
        self.pack(expand=True,fill=Tix.BOTH,side=Tix.TOP)

        # set up the input widget frame
        frmConfs = Tix.Frame(self)
        self._confs(frmConfs)
        frmConfs.pack(side=Tix.TOP,fill=Tix.BOTH,expand=True)

        # set up the button widget frame
        frmBtns = Tix.Frame(self)
        frmBtns.pack(side=Tix.TOP)

        # four buttons, Ok, Apply, Reset and Cancel
        Tix.Button(frmBtns,text='OK',command=self.ok).grid(row=0,column=0)
        Tix.Button(frmBtns,text='Apply',command=self.apply).grid(row=0,column=1)
        Tix.Button(frmBtns,text='Reset',command=self.reset).grid(row=0,column=2)
        Tix.Button(frmBtns,text='Cancel',command=self.cancel).grid(row=0,column=3)

        # insert values from config file
        self._initialize()
    def _confs(self,frm): raise NotImplementedError("ConfigPanel::_confs")
    def _initialize(self): raise NotImplementedError("ConfigPanel::_initialize")
    def _validate(self): raise NotImplementedError("ConfigPanel::_validate")
    def _write(self): raise NotImplementedError("ConfigPanel::_write")
    def ok(self):
        if self._validate():
            self._write()
            self.close()
    def apply(self):
        if self._validate():
            self._write()
    def reset(self): self._initialize()
    def cancel(self): self.close()

class ListPanel(SlavePanel):
    """
     ListPanel - A simple SlavePanel with a ScrolledHList which displays
     information and the option to add widgets to a topframe and/or bottom frame.
     Derived classes can configure the ScrolledHList's number of columns, and
     whether or not to include headers for the columns.

     Derived class must implement:
      methods to add (modify, delete) entries as desired
     Derived classes Should implement:
      topframe - to add widgets to top frame
      bottomframe - to add widgets to bottom frame
    """
    def __init__(self,toplevel,chief,ttl,sz,cols=1,httl=None,iconPath=None):
        SlavePanel.__init__(self,toplevel,chief,iconPath)
        self.master.title(ttl)
        self.pack(expand=True,fill=Tix.BOTH,side=Tix.TOP)

        # create and allow derived classes to setup top frame
        frmTop = Tix.Frame(self)
        if self.topframe(frmTop): frmTop.pack(side=Tix.TOP,expand=False)

        # need hdr value for HList init
        hdr = True
        if not httl: hdr = False

        # setup the hlist
        self.frmMain = Tix.Frame(self)
        self.frmMain.pack(side=Tix.TOP,fill=Tix.BOTH,expand=True)

        # create the scrolled hlist

        # NOTE: if necessary, should be able to use Tree as below
        # self.slist = Tree(self.frmMain,options='hlist.columns %d hlist.header %d' % (cols,hdr))
        self.slist = Tix.ScrolledHList(self.frmMain,
                                       options='hlist.columns %d hlist.header %d' % (cols,hdr))

        # configure the hlist
        self.list = self.slist.hlist                       # get the hlist
        if sz: self.list.config(width=sz[0],height=sz[1])  # set the width/height
        self.list.config(selectforeground='black')         # set to black or it dissappears
        self.list.config(selectmode='extended')            # allow multiple selects
        self.list.config(separator='\t')                   # use tab ignoring special chars

        style = {}
        style['header'] = Tix.DisplayStyle(Tix.TEXT,
                                           refwindow=self.list,
                                           anchor=Tix.CENTER)
        for i in range(len(httl)):
            self.list.header_create(i,itemtype=Tix.TEXT,text=httl[i],
                                      style=style['header'])

        # and pack the scrolled list
        self.slist.pack(expand=True,fill=Tix.BOTH,side=Tix.LEFT)

        # allow a bottom frame
        frmBottom = Tix.Frame(self)
        if self.bottomframe(frmBottom):
            frmBottom.pack(side=Tix.TOP,expand=False)

    # noinspection prPyUnusedLocal
    def topframe(self,frm): return None # override to add widgets to topframe
    # noinspection PyUnusedLocal
    def bottomframe(self,frm): return None # override to add widgets to bottomframe

#### LOG MESSAGE TYPES ####
LOG_NOERR = 0
LOG_WARN  = 1
LOG_ERR   = 2
LOG_NOTE  = 3

class LogPanel(ListPanel):
    """
     a LogPanel display information pertaining to the "program", cannot be closed
     by the user only by the MasterPanel
    """
    def __init__(self,toplevel,chief):
        ListPanel.__init__(self,toplevel,chief,"Log",(60,8),2,[],"widgets/icons/log.png")
        self._l = threading.Lock()
        self._n=0
        self.LC = [Tix.DisplayStyle(Tix.TEXT,
                                    refwindow=self.list,
                                    foreground='Green',
                                    selectforeground='Green'),
                   Tix.DisplayStyle(Tix.TEXT,
                                    refwindow=self.list,
                                    foreground='Yellow',
                                    selectforeground='Yellow'),
                   Tix.DisplayStyle(Tix.TEXT,
                                    refwindow=self.list,
                                    foreground='Red',
                                    selectforeground='Red'),
                   Tix.DisplayStyle(Tix.TEXT,
                                    refwindow=self.list,
                                    foreground='Blue',
                                    selectforeground='Blue')]
        self.pre = ["[+] ","[?] ","[-] ","[!] "]
    def delete(self): pass   # user can never close only the primary chief
    def pnlreset(self): pass # don't care about reseting
    def logwrite(self,msg,mtype=LOG_NOERR):
        """ writes message msg of type mtype to the log """
        self._l.acquire()
        try:
            entry = str(self._n)
            self.list.add(entry,itemtype=Tix.TEXT,text=time.strftime('%H:%M:%S'))
            self.list.item_create(entry,1,text=self.pre[mtype] + msg)
            self.list.item_configure(entry,0,style=self.LC[mtype])
            self.list.item_configure(entry,1,style=self.LC[mtype])
            self._n += 1
            self.list.yview('moveto',1.0)
        except:
            pass
        finally:
            self._l.release()

class TailLogger(threading.Thread):
    """ periodically reads the specified logfile and returns any new 'lines' """
    def __init__(self,cmd,cb,errcb,polltime,logfile):
        """
         initialize the thread
          cmd - dict of commands {'STOP':True causes thread to exit}
          cb - callback function for new lines
          errcb - callback function to report any errors
          polltime - time to sleep between polls
          logfile - logfile to tail
         NOTE: the parameter cmd must be initialized/set with all keys and starting
          values beforing being passed to __init__, any key:value pairs set after
          initialized will not be 'seen' by the thread
        """
        threading.Thread.__init__(self)
        self._cmd = cmd          # command dict from caller
        self._errcb = errcb      # error callback to report failures
        self._pause = polltime   # time to sleep between file checks
        self._lf = logfile       # path of file to monitor
        self._cb = cb            # callback for new lines
        self._ctime = None       # last time logfile was changed
        self._offset = None      # offset of last file

    def run(self):
        """ polls until told to stop or internal error is encountered """
        while not self._cmd['STOP']:
            try:
                if not self._ctime:
                    self._ctime = os.stat(self._lf).st_ctime # get current change time
                    fin = open(self._lf,'r')                 # open file
                    lines = fin.readlines()                  # read all lines
                    self._offset = fin.tell()                # get current offset
                    fin.close()                              # close the file
                    self._cb(lines)                          # forward the lines
                else:
                    ctime = os.stat(self._lf).st_ctime # latest change time
                    if ctime != self._ctime:           # any changes?
                        fin = open(self._lf,'r')       # open for reading
                        fin.seek(self._offset-1)       # go to last read position
                        lines = fin.readlines()        # read all new lines
                        self._offset = fin.tell()      # get new position
                        fin.close()                    # close the file
                        self._ctime = ctime            # update change time
                        self._cb(lines)                 # forward newly read lines
            except Exception as e:
            #except NotImplementedError as e:
                self._errcb(e)
                break
            time.sleep(self._pause)

class TailLogPanel(ListPanel):
    """
     Displays log data from a file - graphically similar to tail -f <file>
    """
    def __init__(self,toplevel,chief,ttl,polltime,logfile):
        """ initializes TailLogPanel to read from the file specified logfile """
        ListPanel.__init__(self,toplevel,chief,ttl,(60,8),1,[],"widgets/icons/log.png")
        self._n=0
        self._lf = logfile
        if not os.path.exists(logfile) and not os.path.isfile(logfile):
            self._chief.logwrite("Log File %s does not exist" % logfile,LOG_ERR)
            return
        self._polltime = polltime
        self._logPoller = None
        self._threadcmd = {'STOP':False}
        self._startlogger()

    def newlines(self,lines):
        """ callback for polling thread to pass new data """
        for line in lines:
            entry = str(self._n)
            self.list.add(entry,itemtype=Tix.TEXT,text=line.strip())
            self._n += 1
            self.list.yview('moveto',1.0)

    def logerror(self,err):
        """ received error callback for polling thread """
        self._chief.logwrite("Log for %s failed %s" % (os.path.split(self._lf)[1],err),
                             LOG_ERR)

    def close(self):
        """ closes the panel """
        # tell the logger to quit and wait for it to finish up, before notifyin
        # parent we are closing
        if self._logPoller:
            self._threadcmd['STOP'] = True
            self._logPoller.join()
        self._chief.panelclose(self._name)

    def pnlreset(self):
        """ resets the log panel """
        # stop the polling thread and join
        self._threadcmd['STOP'] = True
        self._logPoller.join()

        # reset internal structures and clear the list
        self._n = 0
        self.list.delete_all()

        # reset the log poller
        self._startlogger()

    def _startlogger(self):
        self._logPoller = None
        self._threadcmd = {'STOP':False}
        try:
            self._logPoller = TailLogger(self._threadcmd,self.newlines,
                                         self.logerror,self._polltime,self._lf)
            self._logPoller.start()
        except Exception as e:
            self._logPoller = None
            self._chief.logwrite("Log for %s failed %s" % (self._lf,e))

class MasterPanel(Panel):
    """
     the MasterPanel is the primary panel which controls the flow of the
     overall program. The MasterPanel defines a class meant to handle the primary
     data, opening, closing children panels etc
     
     Derived classes should implement:
      _initialize -> if there is functionality that should be started
      _shutdown -> if there is functionality that should be cleanly stopped
      _makemenu -> to implement any menu
      getstate -> if there is a State of the main panel that needs to be known
       by slave panels
      showpanel -> derive for use in toolsload (loads saved panel configs)
    """
    def __init__(self,toplevel,ttl,datatypes=None,logpanel=True,iconPath=None):
        """
         ttl - title of the window/panel
         datatypes - list of strings for data bins, etc
         logpanel - if True, will initiate a logpanel
         iconPath - path of image to show as icon for this panel
        """
        Panel.__init__(self,toplevel,iconPath)
        self.tk = toplevel
        self.menubar = None
        
        # data bins, registered panels, and what data is hidden, selected
        self.audit_registered = {} # panels auditing for notification
        self.bin = {}              # data dictionaries
        self.hidden = {}           # keys of hidden data in bin
        self.selected = {}         # keys of selected data in bin
        for datatype in datatypes:
            self.audit_registered[datatype]= []
            self.bin[datatype] = {}
            self.hidden[datatype] = []
            self.selected[datatype] = []   

        # set the title
        self.master.title(ttl)
        self.grid(sticky=Tix.W+Tix.N+Tix.E+Tix.S)
        
        # try and make the menu
        self._makemenu()
        try:
            self.master.config(menu=self.menubar)
        except AttributeError:
            self.master.tk.call(self.master,"config","-menu",self.menubar)
            
        # make the log panel?
        if logpanel: self.viewlog()

        # initialiez
        self._initialize()

        # is there a default toolset saved?
        if os.path.exists('default.ts'): self.guiload('default.ts')
        self.update_idletasks()

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
            t =Tix.Toplevel()
            pnl = LogPanel(t,self)
            self.addpanel(pnl._name,PanelRecord(t,pnl,"log"))
            pnl.update_idletasks()
            t.wm_geometry("-0-0")
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

#### CALLBACKS ####

    def about(self): pass
    def help(self): pass
    def close(self): pass
    
    def unimplemented(self):
        """ displays info dialog with not implmented message """
        tkMB.showinfo('Not Implemented',"This function not currently implemented",parent=self)
        
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
                    
    def panelquit(self):
        """ cleanly exits - shuts down as necessary """
        ans = tkMB.askquestion('Quit?','Really Quit',parent=self)
        if ans == 'no':
            return
        else:
            self.logwrite('Quitting...')
            self._shutdown()
            self.quit()

    def logwrite(self,msg,mtype=LOG_NOERR):
        """ writes msg to log or shows in error message """
        log = self.getpanel("log",True)
        if log:
            log.logwrite(msg,mtype)
        elif mtype == LOG_ERR:
             tkMB.showerror('Error',msg,parent=self)

    def panelclose(self,panel):
        """
         override panelclose, we need to remove all notification requests from 
         the panel before deleting it
        """
        if panel in self._panels:
            self.audit_deregister(panel)
            self.deletepanel(panel)
        else:
            self.logwrite('Invalid panel %s' % panel)

    def audit_register(self,dtype,panel):
        """ register panel for dtype audits """
        self.audit_registered[dtype].append(panel)

    def audit_deregister(self,panel):
        """ deregister panel from all audits """
        for key in self.audit_registered.keys():
            if panel in self.audit_registered[key]:
                self.audit_registered[key].remove(panel)

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
        for panel in self._panels.keys(): self._panels[panel].pnl.pnlupdate()

    def resetpanels(self):
        """ notify open panels everything is reset """
        for panel in self._panels: self._panels[panel].pnl.pnlreset()