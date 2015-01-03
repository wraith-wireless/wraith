#!/usr/bin/env python
""" panel.py - defines a suite of graphical windows called panes

 Panels operate under the control of a master panel and execute tasks, display
 information independently of (or in conjuction with) this panel and can be opened, 
 closed, "raised", minimized by the user

 TODO:
   1) See http://lukasz.langa.pl/5/error-opening-file-for-reading-permission-denied/
      setcap cap_net_raw=+ep /usr/bin/python2.7 will cause the import of PIL to 
      display Error opening file for reading: Permission denied 
   3) handle no icons
"""

__name__ = 'panel'
__license__ = 'GPL'
__version__ = '0.13.5'
__date__ = 'June 2013'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@hushmail.com'
__status__ = 'Development'

#from __future__ import with_statement
import os                         # files operations etc
import time                       # dtg parsing etc
import pickle                     # load and dump
from operator import itemgetter   # iterators
from Tix import *                 # Tix widgets
from Tkconstants import *         # GUI constants
from tkMessageBox import *        # info gui
from tkFileDialog import *        # file gui dialogs
from PIL import Image             # image input & support
from PIL import ImageTk           # place these after Tix import
from wraith import intersection   # intersection of lists

#### LOG MESSAGE TYPES ####
LOG_NOERROR = 0
LOG_WARNING = 1
LOG_ERROR   = 2

#### PANEL EXCEPTIONS ####
class PanelException(Exception): pass            # TopLevel generic error

class PanelRecord(object):
    """
     PanelRecord - a record (struct) placeholder - used as in item in list of 
     active "slave" master of a master panel
      tk - toplevel 
      pnl - access the Panel methods
      desc - string description
    """
    def __init__(self,tk,pnl,desc):
        self.tk=tk
        self.pnl=pnl
        self.desc=desc

#### SUPER GUI CLASSES ####

class Panel(Frame):
    """
     Panel: Superclass from which all gui classes are derived 
      1) traps the exit from the title bar and passes it to derived close
      2) maintains a dictionary of opened panels 
        self._panels["panelname"] => [panel1,panel2,...,paneln]
        NOTE: there may be multiple panels with the same desc but all panels
        can be uniquely identified by the self._name
        
     Derived classes must:
      implement close()
    """
    def __init__(self,toplevel,iconPath=None):
        """
         toplevel - controling window
         iconPath - path of icon (if one) to display the title bar
        """
        self.appicon=None
        self._panels = {}
        if iconPath: self.appicon = ImageTk.PhotoImage(Image.open(iconPath))
        Frame.__init__(self,toplevel)
        self.master.protocol("WM_DELETE_WINDOW",self.delete)
        if self.appicon: self.tk.call('wm','iconphoto',self.master._w,self.appicon)

    def delete(self): self.close()
    def close(self): raise NotImplementedError("Panel::close")

    def addpanel(self,name,panel):
        """ adds the panel object panel having key name to panels """
        self._panels[name] = panel

    def deletepanel(self,name):
        """ delete the panel with name and remove it from the list """
        self._panels[name].tk.destroy()
        del self._panels[name]

    def deletepanels(self,desc):
        """ deletes all panels with desc """
        opened = self.getpanels(desc,False)
        for panel in opened: panel.pnl.close()

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
     SlavePanel - defines a slave panel which has a controlling panel. Includes 
     methods to display further information on an entry.
      defines:
        sendlogmsg - used to write message to logging panel - NOTE: this will
         only work for classes whose controller is the main panel
        pnlreset - notification that the current job is being cleared
        setstates - should be overridden if subclass needs to set states based
         on changes by controlling panel
        close - allows panel to close itself notifying control in process
         
     Derived Classes should:
      implement descriptionbody
    """
    def __init__(self,toplevel,chief,iconPath=None):
        Panel.__init__(self,toplevel,iconPath)
        self._chief = chief
    def sendlogmsg(self,msg,mtype=LOG_NOERROR): self._chief.logwrite(msg,mtype)
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
        """ an open panel is desiring to close """
        self.deletepanel(name)

    def descriptionopen(self):
        """ opens a descriptionpanel """
        if self.haspanel("description"):
            desc = self.getpanels("description",False)
            for d in desc:
                d.tk.deiconify()
                d.tk.lift()
        else:
            t = Toplevel()
            pnl = DescriptionPanel(t,self,"Description")
            self.addpanel(pnl._name,PanelRecord(t,pnl,"description"))

    def descriptionbody(self,frm): pass
    
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
    def __init__(self,toplevel,chief,ttl,sz,cols=1,httl=[],iconPath=None):
        SlavePanel.__init__(self,toplevel,chief,iconPath)
        self.master.title(ttl)
        self.pack(expand=True,fill=BOTH,side=TOP)
        
        # create and allow derived classes to setup top frame
        frmTop = Frame(self)
        if self.topframe(frmTop): frmTop.pack(side=TOP,expand=False)
        
        # need hdr value for HList init
        hdr = True
        if not httl: hdr = False
        
        # setup the hlist
        self.frmMain = Frame(self)
        self.frmMain.pack(side=TOP,fill=BOTH,expand=True)

        # create the scrolled hlist
        """
         NOTE: if necessary, should be able to use Tree as below
         self.slist = Tree(self.frmMain,options='hlist.columns %d hlist.header %d' % (cols,hdr))
        """
        self.slist = ScrolledHList(self.frmMain,options='hlist.columns %d hlist.header %d' % (cols,hdr))
        
        # configure the hlist
        self.list = self.slist.hlist                       # get the hlist
        if sz: self.list.config(width=sz[0],height=sz[1])  # set the width/height
        self.list.config(selectforeground='black')         # set to black or it dissappears
        self.list.config(selectmode='extended')            # allow multiple selects
        self.list.config(separator='\t')                   # use tab ignoring special chars 
                                                           
        style = {}
        style['header'] = DisplayStyle(TEXT,refwindow=self.list,anchor=CENTER)
        for i in range(len(httl)):
            self.list.header_create(i,itemtype=TEXT,text=httl[i],style=style['header'])
        
        # and pack the scrolled list
        self.slist.pack(expand=True,fill=BOTH,side=LEFT)
        
        # allow a bottom frame         
        frmBottom = Frame(self)
        if self.bottomframe(frmBottom):
            frmBottom.pack(side=TOP,expand=False)

    def topframe(self,frm): return None # override to add widgets to topframe
    def bottomframe(self,frm): return None # override to add widgets to bottomframe

class MenuListPanel(ListPanel):
    """
     MenuListPanel - A ListPanel with options to include:
      1) a File menu with close submenu allowing the user to close the Panel. 
       After calling MenuListPanel::__init__, derived classes can add to the 
        main menu if desired.  
      2) binding for rightclicks on the HList. 
     The MenuListPanel implements a finer control mechanism for the HList, 
     maintaining 'data', a data dictionary which reflects the data shown in the 
     list and 'order', a list of keys which reflects the order of the data as 
     shown in the list. It implements shell methods for adding entries, deleting 
     entries and updating entries so that derived classes do not have to concern
     themselves with keeping the list and the internal data synchronized. 
     
     Derived classes must implement:
      writenew - writes the inserted data to the list
      writeupdate - modifies data in the list
     Derived classes can implement
      rclist to implement binding right mouse clicks to the HList
    """
    def __init__(self,toplevel,chief,ttl,sz,cols=1,httl=[],hasMenu=True,iconPath=None):
        """
         ARGUMENTS:
          toplevel - the calling widget
          chief - the chief panel
          ttl - title of the panel
          sz - tuple defining the size of the panel
          cols - number of columns the list will have
          hdr - define headers for the columns
          httl - header titles
          hasMenu - include a Menu
        """
        ListPanel.__init__(self,toplevel,chief,ttl,sz,cols,httl,iconPath)
        self.data = {}  # data stored in the list
        self.order = [] # order of the data inserted in the list
        
        # include a Menu?
        if hasMenu:
            # create the menu
            self.menubar = Menu(self)
            self.mnuFile = Menu(self.menubar,tearoff=0)
            self.mnuFile.add_command(label="Close",command=self.close)
            self.menubar.add_cascade(label="File",menu=self.mnuFile)
            toplevel.config(menu=self.menubar)
        
        # bind right click to the HList
        self.list.bind('<Button-3>',self.rclist)       

    def pnlreset(self): 
        """
         current job being cleared - delete internal data dictionary and order
         call ListPanel.pnlreset()
        """
        ListPanel.pnlreset(self) # closes all open slave panels
        self.deleteall()

    def insertentry(self,key,data):
        """
         inserts data with id key into the internal data dictionary, and calls
         writenew to add the data to the list, entry is append to the end of order
        """
        try:
            # add the key->data to the dictionary, add this key to the end of the
            # list and call writenew to write the data to the list
            self.data[key] = data
            self.order.append(key)
            self.writenew(key)
        except TclError as e:
            del self.data[key]
            self.sendlogmsg("insertentry error: %s" % e,LOG_ERROR)

    def updateentry(self,dtype,key):
        """
         updates the internal data dictionary data[key] = new data and calls
         writeupdate to modify the data as shown in the list
        """
        if dtype != self._dtype: return
        try:
            self.data[key] = self._chief.bin[self._dtype][key]
            self.writeupdate(key)
        except TclError as e:
            del self.data[key]
            self.sendlogmsg("updateentry error: %s" % e)

    def deleteentry(self,key):
        """
         removes the entry corresponding to key from the internal data dictionary,
         the order and the HList
        """
        try:
            self.order.remove(key)
            del self.data[key]
            self.list.delete_entry(key)
        except TclError as e:
            self.sendlogmsg("deleteentry error: %s" % e)
        except Exception as e:
            self.sendlogmsg("delete entry error: %s" % e)

    def deleteall(self):
        """ removes all entries from the internal data dictionary and the HList """
        try:
            self.order = []
            self.data = {}
            self.list.delete_all()
        except TclError as e:
            self.sendlogmsg("deleteall error: %s" % e)

    def rclist(self,event): pass
    def writenew(self,key): raise NotImplementedError("MenuListPanel::writenew")
    def writeupdate(self,key): raise NotImplementedError("MenuListPanel::writeupdate")

class PollingPanel(MenuListPanel):
    """
     PollingPanel - a MenuListPanel that polls using the after() function
     updating itself
     
     Derived class must implement
      pollfunc - what to do for each poll
    """
    def __init__(self,toplevel,chief,ttl,sz,cols=1,httl=[],pollTime=1000,
                 hasMenu=False,iconPath=None):
        MenuListPanel.__init__(self,toplevel,chief,ttl,sz,cols,httl,hasMenu,iconPath)
        self.pollTime = pollTime
        self.poll()
    
    def poll(self):
        """ polls every n secs """
        self.pollfunc()
        self.after(self.pollTime,self.poll)

    def pollfunc(self): raise NotImplementedError("PollingPanel::pollfunc")

class SharedPollingPanel(MenuListPanel):
    """
     SharedPollingPanel derived from MenuListPanel, uses data collected in a 
     controlling panel. The SharedPollingPanel registers itself at initialization
     for new or updated information. SharedPollingPanels of like data types are
     "coupled": reflecting selections, hiding and restoring of data intiated by
     other like SharedPollingPanels. 
     SharedPollingPanels include a right click context menu displaying options 
     to unselect, hide (selected), restore and hide (unselected). Bindings for 
     mouse release (select) and up, down arrow key release, to react to user
     manipulation of the list data
     
     Derived classes must implement
      notifyhiddencb - another SharedPollingPanel has hidden entries
      notifyrestorecb - another SharedPollingPanel has restored hidden entries
      notifyselectcb - another SharedPollingPanel has selected entries
     Derived classes should implement
      str2key - if there is a desired mapping from the string key in the list to
       the key in the data dictionary
      additionalcontext - if there are additional menu commands to add to the right
       click context menu
      additionalbuttons - if there are additional buttons to add in the topframe

     NOTE:
      This Panel requires that the controlling panel must have a dictionary called
      bin, and implements functions selectentries, hideentries and restorehidden
      there is redundancy in that this Panel stores data that is also stored and
      maintained in the controlling panel
    """
    def __init__(self,toplevel,chief,ttl,sz,cols=1,httl=[],hasMenu=False,dtype=None,iconPath=None):
        """
         ARGUMENTS:
          toplevel - the toplevel
          chief - controlling panel
          ttl - title of this panel
          sz - tuple defining size of the panel
          cols - # of columns for the list
          httl - header titles if any
          hasMenu - include a Menu or not
          dtype - string representing what data type this panel shows
        """
        MenuListPanel.__init__(self,toplevel,chief,ttl,sz,cols,httl,hasMenu,iconPath)
        self._dtype = dtype
        
        # bindings
        self.list.bind("u",self.ukp)                        # unselect selected
        self.list.bind("h",self.hkp)                        # hide selected
        self.list.bind("r",self.rkp)                        # restore hidden
        self.list.bind("s",self.skp)                        # hide unselected
        self.list.bind('<ButtonRelease-1>',self.listselect) # mouse release
        self.list.bind('<KeyRelease>',self.keyrelease)      # any key release
        
        # register ourselves for notifications
        self._chief.audit_register(self._dtype,self._name)
        
        # intial state
        self.setstates(self._chief.getstate())

    def topframe(self,frm):
        """ defines the topframe above the list """
        # put an export button here
        col = 0
        for widget in self.additionalbuttons(frm):
            widget.grid(row=0,column=col)
            col+=1
        return True

    def getexisting(self,dtype=None):
        """
         after opening has to get any data that existed prior to creation.
         dtype can be any data, if not specified, will use registered data type
        """
        if not dtype: dtype = self._dtype
        if self._chief.bin[dtype]:
            for key in self._chief.bin[dtype]:
                self.insertentry(key,self._chief[dtype][key])
            self.notifyselectcb(self._dtype,self._chief.getselected(dtype))

    def newcb(self,dtype,keys):
        """ callback - notifys this panel of new data in the data bin """
        # ignore if not our data type
        if dtype == self._dtype:
            for key in keys: self.insertentry(key,self._chief.bin[self._dtype][key])

    def changecb(self,dtype,keys):
        """ callback - notifys this panel that existing data has been changed """
        if dtype == self._dtype:
            for key in keys: self.updateentry(key)

    # these must be implemented by deriving class
    def notifyhiddencb(self,dtype,keys): raise NotImplementedError("SharedPollingPanel::notifyhiddencb")
    def notifyrestorecb(self,dtype,keys): raise NotImplementedError("SharedPollingPanel::notifyrestorecb")
    def notifyselectcb(self,dtype,keys): raise NotImplementedError("SharedPollingPanel::notifyselectcb")

    def keyrelease(self,event):
        """
         user has released a key, if up or down arrows, process as a list selection
        """
        if event.keysym == 'Up':
            self.listselect(event)
        elif event.keysym == 'Down':
            self.listselect(event)

    def rclist(self,event):
        """
         rightclick - show context menu
        """
        if self._chief.bin[self._dtype] != {}:
            mnu = Menu(None,tearoff=0)
            mnu.add_command(label="Unselect",command=self.mukp)
            mnu.add_command(label="Hide",command=self.mhkp)
            mnu.add_command(label="Select",command=self.mskp)
            mnu.add_command(label="Restore",command=self.mrkp)
            self.additionalcontext(mnu,4)
            
            n = len(self.list.info_selection()) # of selected
            if n == 0:
                mnu.entryconfig(0,state=DISABLED)
                mnu.entryconfig(1,state=DISABLED)
                mnu.entryconfig(3,state=DISABLED)
            mnu.tk_popup(event.x_root,event.y_root,"")

    # these are just wrappers for the context menu
    def mukp(self): self.ukp(None)
    def mskp(self): self.skp(None)
    def mrkp(self): self.rkp(None)
    def mhkp(self): self.hkp(None)

    def ukp(self,event):
        """ unselects all selected """
        # clear selections & notify controlling panel
        self.list.selection_clear()
        self._chief.selectentries(self._dtype,self._name,[])    

    def skp(self,event):
        """ hides unselected entries """
        ks = self._chief.bin[self._dtype].keys()           # all keys
        ss = self.list.info_selection()                    # selected keys
        for s in ss: ks.remove(self.str2key(s))            # remove s from all keys
        for h in self._chief.hidden[self._dtype]:          # remove h from all keys
            if h in ks: ks.remove(h)
        for k in ks: self.list.hide_entry(str(k))          # hide non-selected
        self._chief.hideentries(self._dtype,self._name,ks) # notify controller

    def rkp(self,event):
        """ restore all hidden entries """
        # restore hidden and tell controller
        for h in self._chief.hidden[self._dtype]:
            self.list.show_entry(str(h))
        self._chief.restorehidden(self._dtype,self._name)    

    def hkp(self,event):
        """ hide all selected """
        # get selected, hiding the indiviudal entries and notify controller
        ss = self.list.info_selection()
        for s in ss: self.list.hide_entry(s)
        self._chief.hideentries(self._dtype,self._name,map(self.str2key,ss))

    def listselect(self,event):
        """ bind list mouse releas """
        # send all selected to controller
        self._chief.selectentries(self._dtype,self._name,
                                  map(self.str2key,self.list.info_selection()))

    def str2key(self,s): return s
    
    def additionalcontext(self,mnu,cnt): pass
    def additionalbuttons(self,btn): return []

class SharedPollingPanelEx(SharedPollingPanel):
    """
     SharedPollingPanelEx is the primary panel for displaying tabular data. It 
     extends the SharedPollingPanel by:
      1 enabling sorts based on header titles
      2 displays a cnt of the number of 'entries' displayed vice total number of 
        entries on the bottom frame
      3 allows rows to be highlighted/colored by field
     Note: this class can only handle simple data, dicts of dicts in the chief
     
     Derived panels must implement
      option2field - maps user friendly 'option' to data field name, set 
      self.soptions to list of string of options
    """
    def __init__(self,toplevel,chief,ttl,sz,cols,httl,hasMenu=False,dtype=None,
                 sortby=[],colors=[],iconPath=None):
        """
         initializes (see SharedPollingPanel for arg descriptions
         colors is a list (strings) of colors to be used for highlighting
        """
        # create sorting options prior to initializing super class
        self.soptions = sortby
        SharedPollingPanel.__init__(self,toplevel,chief,ttl,sz,cols,httl,hasMenu,
                                    dtype,iconPath)
        
        # load icons here 
        self.nCols = cols
        
        # define the COLORBy colors
        # TODO go back to default
        self.colors = colors    # available colors
        self.curHighlight = -1  # index to highlight list
        self.hField = None      # field to highlight
        self.highlightmap = {}  # defines value->style mappings
        
        # populate the style dict, then get existing data
        self.style = {}
        for color in self.colors:
            self.style[color] = DisplayStyle(IMAGETEXT,refwindow=self.list,
                                             foreground=color,
                                             selectforeground=color)
        self.getexisting()

    def pnlreset(self):
        """ clears additional internals before calling derived pnlreset """
        self.highlightmap = {}
        self.hField = None
        self.curHighlight = -1
        SharedPollingPanel.pnlreset(self)

    def additionalbuttons(self,frm):
        """ adds buttons to top """
        btns = []
        # if no sort options, do not add
        if self.soptions:
            self.svar = StringVar(self)
            self.svar.set(self.soptions[0])
        
            # sort by options
            self.soptMnu = Tkinter.OptionMenu(frm,self.svar,*self.soptions)
        
            # sort order options
            ooptions = ["Asc","Desc"]
            self.ovar = StringVar(self)
            self.ovar.set(ooptions[0])
            self.ooptMnu = Tkinter.OptionMenu(frm,self.ovar,*ooptions)
            
            # sort button
            try:
                self.simg = ImageTk.PhotoImage(Image.open('icons/sort.png'))
                btn = Button(frm,image=self.simg,command=self.sort)
            except Exception:
                btn = Button(frm,text="Sort",command=self.sort)
            
            btns = [self.soptMnu,self.ooptMnu,btn]

        # highlight button
        try:
            self.hlimg = ImageTk.PhotoImage(Image.open('icons/highlightmap.png'))
            ibtn = Button(frm,image=self.hlimg,command=self.showhighlightmap)            
        except Exception:
            ibtn = Button(frm,text="Highlight",command=self.showhighlightmap)
        
        btns.append(ibtn)
        return btns

    def bottomframe(self,frm):
        """ add widgets to bottomframe """
        self.status = StringVar()
        self.status.set("0 of 0")
        lblStatus = Label(frm,textvariable=self.status,anchor=W,borderwidth=1)
        lblStatus.grid(row=0,column=0)
        lblSpacer = Label(frm,text='',width=20)
        lblSpacer.grid(row=0,column=1)
        return True
    
    def sort(self):
        """ sorts data by field """
        field = self.option2field(self.svar.get())
        
        # sorting ascending or descinding?
        o = self.ovar.get()
        show = False
        if o == "Desc": show = True
        
        # make a list of (key,sortby) tuples, then sort the list based on the column
        #ls = self.generatesorttuples()
        ls = [(key,self._chief.bin[self._dtype][key][field]) for key in self._chief.bin[self._dtype]]
        ls.sort(key=itemgetter(1),reverse=show)

        # clear the list and reinsert in order
        self.deleteall()
        for l in ls:
            self.insertentry(l[0],self._chief.bin[self._dtype][l[0]])     

    def option2field(self,option):
        """ maps user named field to data field """
        raise NotImplementedError("SharedPollingPanelEx::option2field")

    def notifyhiddencb(self,dtype,keys):
        """ data has been hidden """
        for key in keys: self.list.hide_entry(key)
        self.status.set("%d of %d" %\
                        (len(self.order)-len(self._chief.hidden[self._dtype]),\
                         len(self.order)))

    def notifyselectcb(self,dtype,keys):
        """ data has been selected """
        self.list.selection_clear()
        for key in keys: self.list.selection_set(key)
    
    def notifyrestorecb(self,dtype,keys):
        """ data has been restored """
        self.list.selection_clear()
        for key in keys: self.list.show_entry(key)
        for key in self._chief.getselected(self._dtype):
            self.list.selection_set(key)
        self.status.set("%d of %d" % (len(self.order)-len(self._chief.hidden[self._dtype]),
                         len(self.order)))

    def sethighlight(self,field):
        """ set highligts """
        self.curHighlight = -1
        self.highlightmap = {}
        self.hField = field
        for key in self._chief.bin[self._dtype].keys():
            self.highlightentry(key)
            
    def clearhighlight(self):
        """ clear all highlights """
        # reset highlight stuff
        self.curHighlight = -1
        self.highlightmap = {}
        self.hField = None
        
        # to change highlights we have to remove all entries and reinsert
        self.deleteall()
        self.getexisting()

    def highlightentry(self,key):
        """ highlight a entry """
        # determine what color to use
        val = self._chief.bin[self._dtype][key][self.option2field(self.hField)]
        try:
            color = self.highlightmap[str(val)]
        except KeyError:
            self.curHighlight += 1
            if self.curHighlight >= len(self.colors):
                color = self.colors[len(self.colors)-1]
            else:
                color = self.colors[self.curHighlight]
                self.highlightmap[str(val)] = color
                panels = self.getpanels('colormap')
                if panels: panels[0].updatemapping()
        
        # change to show the selected color
        # -> make the length of columns
        #for i in range(0,len(self.soptions)):
        for i in range(0,self.nCols):
            self.list.item_configure(key,i,style=self.style[color])

    def skp(self,event):
        """ select handler """
        SharedPollingPanel.skp(self,event)
        self.status.set("%d of %d" %\
                        (len(self.order)-len(self._chief.hidden[self._dtype]),\
                         len(self.order)))

    def rkp(self,event):
        """ restore handler """
        SharedPollingPanel.rkp(self,event)
        self.status.set("%d of %d" %\
                        (len(self.order)-len(self._chief.hidden[self._dtype]),\
                         len(self.order)))

    def hkp(self,event):
        """ hide handler """
        SharedPollingPanel.hkp(self,event)
        self.status.set("%d of %d" %\
                        (len(self.order)-len(self._chief.hidden[self._dtype]),\
                         len(self.order)))

    def showhighlightmap(self):
        """ show the highlight map panel """
        # display highlight mapping or close it if open
        if self.haspanel("colormap"):
            self.deletepanels("colormap")
        else:
            t = Toplevel()
            pnl = HighlightMapPanel(t,self,self.hField,self.soptions)
            self.addpanel(pnl._name,PanelRecord(t,pnl,"colormap"))

class SharedPollingPanelComplex(SharedPollingPanelEx):
    """
     SharedPollingPanelComplex handles more complex data i.e. dicts with subdicts
     and lists of classes for displaying tabular data by using wrappers around
     data calls and adds a CountBy icon to the button bar. Override additionalbuttons 
     to dissallow it.
     
     Derived panels must implement
      option2field - maps user friendly 'option' to data field name, set 
                     self.soptions to list of string of options
      insertentry - specify how data is shown in the list               
      Wrapper function to be overridden for complex data (if not overridden, this 
      panel will function the same as a SharedPollingPanelEx
      hiddenkeys - retreive hidden keys only belonging to this panel
      selectedkeys - retreive selected keys only belonging to this panel
      databin - retreive the data bin for this panel
      keys - retreive all keys stored in primary data bin
      values - retreive all values stored in primary data bin
      structure - retreive a structure for databin
      value - retrieve a value in the structure
      displayvalue - retrieves a value from the displayed data (only necessary if
       data displayed in the panel is modified from the data in the bin)
    """
    def __init__(self,toplevel,chief,ttl,sz,cols,httl,hasMenu=False,dtype=None,
                 sortby=[],colors=[],iconPath=None):
        """
         initializes (see SharedPollingPanel,SharedPollingPanelEx for arg 
         descriptions
        """
        SharedPollingPanelEx.__init__(self,toplevel,chief,ttl,sz,cols,httl,hasMenu,
                                      dtype,sortby,colors,iconPath)

    def getexisting(self,dtype=None):
        """ override existing to use wrapper calls """
        if self.databin():
            for key in self.databin(): self.insertentry(key,self.structure(key))
            self.notifyselectcb(self._dtype,self.selectedkeys())

    def sort(self):
        """ sort by user specified field """
        # get the desired field and desc/asc sort
        field = self.option2field(self.svar.get())
        o = self.ovar.get()
        show = False
        if o == "Desc": show = True
        
        # make a list of (key,sortby) tuples, sort the list based on the specified
        # column
        ls = [(key,self.value(key,field)) for key in self.keys()]
        ls.sort(key=itemgetter(1),reverse=show)
        
        # remove all entries and reinsert in sorted order
        self.deleteall()
        for l in ls: self.insertentry(l[0],self.structure(l[0]))

    def notifyhiddencb(self,dtype,keys):
        for key in keys: self.list.hide_entry(key)
        self.status.set("%d of %d" %\
                        (len(self.order)-len(self.hiddenkeys()),\
                         len(self.order)))

    def notifyselectcb(self,dtype,keys):
        self.list.selection_clear()
        keys = intersection(keys,self.order)
        for key in keys: self.list.selection_set(key)
        self.status.set("%d of %d" %\
                        (len(self.order)-len(self.hiddenkeys()),\
                         len(self.order)))

    def notifyrestorecb(self,dtype,keys):
        self.list.selection_clear()
        for key in keys: self.list.show_entry(key)
        for key in self.selectedkeys(): self.list.selection_set(key)
        self.status.set("%d of %d" %\
                        (len(self.order)-len(self.hiddenkeys()),\
                         len(self.order)))

    def sethighlight(self,field):
        """ sets the highlight field options and highlights entries """
        self.curHighlight = -1
        self.highlightmap = {}
        self.hField = field
        for key in self.keys(): self.highlightentry(key)

    def highlightentry(self,key):
        """ highlight the entry corresponding to key """
        # what color ?
        val = self.displayvalue(key,self.option2field(self.hField))
        try:
            color = self.highlightmap[str(val)]
        except KeyError:
            # no color for this value, make a new one, if we have run out of colors
            # use the last one for extra values
            self.curHighlight += 1
            if self.curHighlight >= len(self.colors):
                color = self.colors[len(self.colors)-1]
            else:
                color = self.colors[self.curHighlight]
                self.highlightmap[str(val)] = color
                panels = self.getpanels('colormap')
                if panels: panels[0].updatemapping()
        
        # change the color of this entry (have to do each column)
        for i in range(0,len(self.soptions)):
            self.list.item_configure(key,i,style=self.style[color])

    def rclist(self,event):
        """
         rightclick - show context menu overriden to handle comlplex data
        """
        if self._chief.bin[self._dtype] != {}:
            mnu = Menu(None,tearoff=0)
            mnu.add_command(label="Unselect",command=self.mukp)
            mnu.add_command(label="Hide",command=self.mhkp)
            mnu.add_command(label="Select",command=self.mskp)
            mnu.add_command(label="Restore",command=self.mrkp)
            mnu.add_separator()
            self.additionalcontext(mnu,5)
            
            n = len(self.list.info_selection()) # of selected
            if n == 0:
                # if nothing is selected, disable all
                mnu.entryconfig(0,state=DISABLED)
                mnu.entryconfig(1,state=DISABLED)
                mnu.entryconfig(2,state=DISABLED)
                mnu.entryconfig(3,state=DISABLED)
            else:
                # only allow restore if something is hidden
                if not self.hiddenkeys(): mnu.entryconfig(3,state=DISABLED)
            mnu.tk_popup(event.x_root,event.y_root,"")

    def ukp(self,event):
        """ unselects all selected """
        # clear selections & notify controlling panel
        self.list.selection_clear()
        self._chief.selectentries(self._dtype,self._name,[])    

    def skp(self,event):
        """ hides unselected entries """
        ks = self.keys()                                      # all keys
        ss = self.list.info_selection()                       # selected keys
        for s in ss: ks.remove(self.str2key(s))               # remove s from all keys
        for h in self.hiddenkeys():                           # remove h from all keys
            if h in ks: ks.remove(h)
        for k in ks: self.list.hide_entry(str(k))             # hide non-selected
        self._chief.hideentries(self._dtype,self._name,ks)    # notify controller
        self.status.set("%d of %d" %\
                        (len(self.order)-len(self.hiddenkeys()),
                        len(self.order)))

    def rkp(self,event):
        """ restore all hidden entries """
        # restore hidden and tell controller
        for h in self.hiddenkeys():
            self.list.show_entry(str(h))
        self._chief.restorehidden(self._dtype,self._name)
        self.status.set("%d of %d" %\
                        (len(self.order)-len(self.hiddenkeys()),
                        len(self.order)))    

    def hkp(self,event):
        """ hide all selected """
        # get selected, hiding the indiviudal entries and notify controller
        ss = self.list.info_selection()
        for s in ss: self.list.hide_entry(s)
        self._chief.hideentries(self._dtype,self._name,map(self.str2key,ss))
        self.status.set("%d of %d" %\
                        (len(self.order)-len(self.hiddenkeys()),
                        len(self.order)))
    
#### WRAPPER FOR DATA CALLS ####

    """
     these attempt to make transtoplevel the fact that the chief databins
     are more complex than a simple dict of dicts. selectedkeys and hiddenkeys
     can be left as is
    """

    def selectedkeys(self):
        """ returns only those keys belong to this panel that are selected """
        skeys = self._chief.selected[self._dtype]
        return intersection(skeys,self.order)

    def hiddenkeys(self):
        """ returns only those keys belonging to this panel that are hidden """
        hkeys = self._chief.hidden[self._dtype]
        return intersection(hkeys,self.order)

    def databin(self):
        """ returns the primary data bin """
        return self._chief.bin[self._dtype]

    def keys(self):
        """ returns all keys from primary data bin """
        return self._chief.bin[self._dtype].keys()

    def values(self):
        """ returns all values from the primary data bin """
        return self._chief.bin[self._dtype].values()

    def structure(self,key):
        """ returns the structure in the key->structure tuple """
        return self._chief.bin[self._dtype][key]

    def value(self,key,field):
        """ returns the value for field in the structure specified by key """
        return self._chief.bin[self._dtype][key][field]

    def displayvalue(self,key,field):
        """ returns the displayed value """
        return self.value(self,key,field)

class CountByPanel(SharedPollingPanel):
    """
     CountByPanel - displays counts of fields 
     NOTE: the data will be of the form key->cnt,ids where key is the value of 
     the currently selected option, cnt is the number of items of type option and 
     ids is a list of ids having value for option
     Derived classes can override formatentry to format how data is displayed or
     leave as is `key (cnt)`
    """
    def __init__(self,toplevel,chief,ttl,sz,cols=1,httl=[],hasMenu=False,dtype=None,opts=[]):
        self.options = opts
        SharedPollingPanel.__init__(self,toplevel,chief,ttl,sz,cols,httl,
                                    hasMenu,dtype,"icons/calc.png")
        self.getexisting()

    def additionalbuttons(self,frm):
        # set up the option menu
        self.ovar = StringVar(self)
        self.ovar.set(self.options[0])
        self.optMnu = Tkinter.OptionMenu(frm,self.ovar,*self.options)
        
        # the count menu
        try:
            self.slimg = ImageTk.PhotoImage(Image.open('icons/calc.png'))
            btn = Button(frm,image=self.slimg,command=self.count)
        except Exception:
            btn = Button(frm,text="Count",command=self.count)
        
        return [self.optMnu,btn]

    def option2field(self,option): return option.lower()

    def listselect(self,event):
        """ list selection binding """
        # send selected to controller
        ss = self.list.info_selection()
        selected = []
        for s in ss: selected.extend(self.data[self.str2key(s)]['ids'])
        self._chief.selectentries(self._dtype,self._name,selected)

    def notifyhiddencb(self,dtype,keys):
        """ another panel has hidden keys, decrement cnts for data accordingly"""
        # for each field being shown, find the intersection of the field's ids
        # and the given keys. remove each item in the intersection from the fields
        # ids and decrement the field's cnt by the # items removed, finally, write
        # the update
        for field in self.data:
            inter = intersection(self.data[field]['ids'],keys)
            for i in inter: 
                try:
                    self.data[field]['ids'].remove(i)
                except ValueError as e:
                    self.sendlogmsg('CountBy Error for %s: %s' % (i,e))
            self.data[field]['cnt'] -= len(inter)
            self.writeupdate(field)

    def notifyselectcb(self,dtype,keys):
        """ another panel has selected keys """
        # for each field, if the intersection of the field's ids and the given
        # keys is not empty, select it
        self.list.selection_clear()
        for field in self.data:
            if intersection(self.data[field]['ids'],keys):
                self.list.selection_set(str(field))
    
    def notifyrestorecb(self,dtype,keys):
        """ another panel has restored all keys """
        # NOTE: we bypass the insertentry function here to avoid multiple updates
        # get the current countby field
        option = self.option2field(self.ovar.get())

        # use a local dictionary for tallying (don't forget what we already have)
        d = self.data 
        for key in keys:
            value = self._chief.bin[self._dtype][key][option]
            if d.has_key(value):
                d[value]['cnt'] += 1
                d[value]['ids'].append(key)
            else:
                d[value] = {'cnt':1,'ids':[key]}
        
        # update the data dictionary and the list
        for key in d:
            if self.data.has_key(key):
                self.data[key] = d[key]
                self.writeupdate(key)
            else:
                self.data[key] = d[key]
                self.writenew(key)

    def getexisting(self,dtype=None):
        """
         override SharedPollingPanel::getexisting() to avoid multiple writes during 
         tallying of existing data
        """
        # get count by field, tally data to local dict
        option = self.option2field(self.ovar.get())
        d = {}
        for key in self._chief.bin[self._dtype]:
            if not key in self._chief.hidden[self._dtype]:
                value = self._chief.bin[self._dtype][key][option]
                if d.has_key(value):
                    d[value]['cnt'] += 1
                    d[value]['ids'].append(key)
                else:
                    d[value] = {'cnt':1,'ids':[key]}
            
        # write tallied data
        for key in d:
            if self.data.has_key(key):
                self.data[key] = d[key]
                self.writeupdate(key)
            else:
                self.data[key] = d[key]
                self.writenew(key)
        self.notifyselectcb(dtype,self._chief.getselected(self._dtype))

    def insertentry(self,key,data):
        option = self.option2field(self.ovar.get())
        if not key in self._chief.hidden[self._dtype]:
            value = self._chief.bin[self._dtype][key][option]
            if self.data.has_key(value):
                self.data[value]['cnt'] += 1
                self.data[value]['ids'].append(key)
                self.writeupdate(value)
            else:
                self.data[value] = {'cnt':1}
                self.data[value]['ids'] = [key]
                self.writenew(value)
    
    def updateentry(self,key): pass
    # TODO implement this

    def writenew(self,key):
        self.order.append(key)
        self.list.add(str(key),itemtype=TEXT,
                      text=self.formatentry(key,self.data[key]['cnt']))

    def writeupdate(self,key):
        self.list.item_configure(str(key),0,itemtype=TEXT,
                                 text=self.formatentry(key,self.data[key]['cnt']))
        if self.data[key]['cnt'] == 0:
            self.list.hide_entry(str(key))
        else:
            self.list.show_entry(str(key))
            
    def formatentry(self,entry,cnt): return "%s (%d)" % (str(entry),cnt)
    
    def count(self):
        # TODO: what is this?
        self.deleteall()
        self.getexisting()

    def ukp(self,event):
        """ unselects all selected """
        SharedPollingPanel.ukp(self,event)
        self.listselect(None)
    
    def skp(self,event): 
        """ hides all non-selected entries """
        ks = self.data.keys()                                  # all keys
        ss = self.list.info_selection()                        # selected keys
        for s in ss: ks.remove(self.str2key(s))                # remove s from allkeys
        for h in self._chief.hidden[self._dtype]:           # remove h from allkeys
            if h in ks: ks.remove(h) 
        hidden = []
        for k in ks:                                           # hide non-selected
            hidden.extend(self.data[self.str2key(k)]['ids'])
            self.list.hide_entry(str(k))
        self._chief.hideentries(self._dtype,self._name,hidden)     
    
    def rkp(self,event):
        """ restores all hidden entries """
        self._chief.restorehidden(self._dtype,self._name)
        self.deleteall()
        self.getexisting()
    
    def hkp(self,event):
        """ hides all selected entries """
        ss = self.list.info_selection()
        hidden = []
        for s in ss:
            s2k = self.str2key(s)
            hidden.extend(self.data[s2k]['ids'])
            self.list.hide_entry(s)
            self.data[s2k]['cnt'] = 0
            self.data[s2k]['ids'] = []
        self._chief.hideentries(self._dtype,self._name,hidden)

class CountByPanelComplex(CountByPanel):
    """
     CountByPanel - extends the CountByPanel to display complex data 
     NOTE: the data will be of the form key->cnt,ids where key is the value of 
      the currently selected option, cnt is the number of items of type option and 
      ids is a list of ids having value for option
      Derived classes can override formatentry to format how data is displayed or
      leave as is `key (cnt)`
     Derived class must override
      hiddenkeys
      selectedkeys
      databin
      keys
      structure
      value
      option2field
    """
    def __init__(self,toplevel,chief,ttl,dtype,opts):
        CountByPanel.__init__(self,toplevel,chief,ttl,(30,8),1,[],False,dtype,opts)

    def getexisting(self,dtype=None):
        """ get count by field, tally data to local dict """
        option = self.option2field(self.ovar.get())
        d = {}
        for key in self.keys():
            if not key in self.hiddenkeys():
                value = self.value(key,option)
                if d.has_key(value):
                    d[value]['cnt'] += 1
                    d[value]['ids'].append(key)
                else:
                    d[value] = {'cnt':1,'ids':[key]}
        
        # write the tallied data
        for key in d:
            if self.data.has_key(key):
                self.data[key] = d[key]
                self.writeupdate(key)
            else:
                self.data[key] = d[key]
                self.writenew(key)
        self.notifyselectcb(dtype,self.selectedkeys())    

    def listselect(self,event):
        """ list selection binding """
        # send selected to controller
        ss = self.list.info_selection()
        selected = []
        for s in ss: selected.extend(self.data[self.str2key(s)]['ids'])
        self._chief.selectentries(self._dtype,self._name,selected)

    def changecb(self,dtype,keys):
        """ override, to retally all data """
        if dtype == self._dtype:
            self.pnlreset()
            self.getexisting()

    def insertentry(self,key,data):
        option = self.option2field(self.ovar.get())
        if not key in self.hiddenkeys():
            value = self.value(key,option)
            if self.data.has_key(value):
                self.data[value]['cnt'] += 1
                self.data[value]['ids'].append(key)
                self.writeupdate(value)
            else:
                self.data[value] = {'cnt':1}
                self.data[value]['ids'] = [key]
                self.writenew(value)
    
    def notifyrestorecb(self,dtype,keys):
        """ another panel has restored all keys """
        # NOTE: we bypass the insertentry function here to avoid multiple updates
        # get the current countby field
        option = self.option2field(self.ovar.get())

        # use a local dictionary for tallying (don't forget what we already have)
        d = self.data 
        for key in keys:
            #value = self._chief.bin[self._dtype][key][option]
            value = self.value(key,option)
            if d.has_key(value):
                d[value]['cnt'] += 1
                d[value]['ids'].append(key)
            else:
                d[value] = {'cnt':1,'ids':[key]}
        
        # update the data dictionary and the list
        for key in d:
            if self.data.has_key(key):
                self.data[key] = d[key]
                self.writeupdate(key)
            else:
                self.data[key] = d[key]
                self.writenew(key)                

    def skp(self,event): 
        """ hides all non-selected entries """
        ks = self.data.keys()                                  # all keys
        ss = self.list.info_selection()                        # selected keys
        for s in ss: ks.remove(self.str2key(s))                # remove s from allkeys
        for h in self.hiddenkeys():                            # remove h from allkeys
            if h in ks: ks.remove(h) 
        hidden = []
        for k in ks:                                           # hide non-selected
            hidden.extend(self.data[k]['ids'])
            self.list.hide_entry(str(k))
        self._chief.hideentries(self._dtype,self._name,hidden)

    def hiddenkeys(self): self._chief.hidden[self._dtype]
    def selectedkeys(self): self._chief.selected[self._dtpye]
    def databin(self): return self._chief.bin[self._dtype]
    def keys(self): return self._chief.bin[self._dtype].keys()
    def structure(self,key): return self._chief.bin[self._dtype][key]
    def value(self,key,field):
        return self._chief.bin[self._dtype][key][field]

class DescriptionPanel(SlavePanel):
    """
     Displays further description of an entry in the calling Panel - the caller
     will implement descriptionbody to add widgets
    """
    def __init__(self,toplevel,chief,ttl):
        SlavePanel.__init__(self,toplevel,chief,"icons/desc.png")
        self.master.title(ttl)
        self.pack(expand=True,fill=BOTH,side=TOP)
        frm1 = Frame(self,relief='sunken',border=2)
        frm1.pack(side=TOP,fill=BOTH,expand=True)
        self._chief.descriptionbody(frm1)
        frm2 = Frame(self,relief='sunken',border=2)
        frm2.pack(side=TOP,fill=BOTH,expand=False)
        Button(frm2,text='Close',command=self.close).pack()
            
class LogPanel(ListPanel):
    """
     a LogPanel display information pertaining to the "program", cannot be closed
     by the user only by the "highest" chief 
    """
    def __init__(self,toplevel,chief):
        ListPanel.__init__(self,toplevel,chief,"Log",(60,8),2,[],"icons/log.png")
        self.n=0
        self.LC = [DisplayStyle(TEXT,refwindow=self.list,foreground='Green',selectforeground='Green'),
                   DisplayStyle(TEXT,refwindow=self.list,foreground='Yellow',selectforeground='Yellow'),
                   DisplayStyle(TEXT,refwindow=self.list,foreground='Red',selectforeground='Red')]
    def delete(self): pass   # user can never close only the primary chief
    def pnlreset(self): pass # don't care about reseting
    def logwrite(self,msg,mtype=LOG_NOERROR): 
        entry = str(self.n)
        self.list.add(entry,itemtype=TEXT,text=time.strftime('%H:%M:%S'))
        self.list.item_create(entry,1,text=msg)
        self.list.item_configure(entry,0,style=self.LC[mtype])
        self.list.item_configure(entry,1,style=self.LC[mtype])
        self.n += 1
        self.list.yview('moveto',1.0)

class HighlightMapPanel(ListPanel):
    """
     HighlightMapPanel - simple list panel that allows user to select field to
     color by and displays color mappings for a SharedPollingPanelEx
    """
    def __init__(self,toplevel,chief,field,hoptions):
        self.hoptions = ['None'] + hoptions
        self.curField = field
        ListPanel.__init__(self,toplevel,chief,"Color (%s)" % field,(),2,[],"icons/highlightmap.png")
        
        # get existing mapping if any from chief
        self.updatemapping()

    def listselect(self,event): pass

    def topframe(self,frm):
        # get the highlight image
        try:
            self.hbtn = ImageTk.PhotoImage(Image.open('icons/highlight.png'))
        except Exception:
            self.hbtn = None
        
        # set up option menu
        self.ovar = StringVar(self)
        self.ovar.set(self.curField)
        self.optMnu = Tkinter.OptionMenu(frm,self.ovar,*self.hoptions)
        self.optMnu.grid(row=0,column=0)
        
        # highlight button
        btnHighlight = Button(frm,image=self.hbtn,command=self.highlight)
        btnHighlight.grid(row=0,column=1)
        
        return True

    def highlight(self):
        # send field to chief
        if self.ovar.get() == 'None':
            self._chief.clearhighlight()
        else:
            self._chief.sethighlight(self.ovar.get())
        self.updatemapping()

    def updatemapping(self):
        self.list.delete_all()
        for key in self._chief.highlightmap:
            self.list.add(key,itemtype=IMAGETEXT,text=key)
            self.list.item_create(key,1,itemtype=IMAGETEXT,text=self._chief.highlightmap[key])
            self.list.item_configure(key,0,style=self._chief.style[self._chief.highlightmap[key]])
            self.list.item_configure(key,1,style=self._chief.style[self._chief.highlightmap[key]])

class MasterPanel(Panel):
    """
     the MasterPanel is the primary, master panel which controls the flow of the
     overall program. The MasterPanel defines a class meant to handle primary data 
     i.e. getting, updating etc.
     
     Derived classes should implement:
      _initialize -> if there is functionality that should be started
      _shutdown -> if there is functionality that should be cleanly stopped
      _makemenu -> to implement any main menu
      getstate -> if there is a State of the main panel that needs to be know
       by slave panels
    """
    def __init__(self,toplevel,ttl,datatypes=[],logpanel=True,iconPath=None):
        """
         ttl - title of the window/panel
         datatypes - list of strings for data bins, etc
         logpanel - if True, will initiate a logpanel
        """
        Panel.__init__(self,toplevel,iconPath)
        self.tk = toplevel
        self._log = None
        
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
        self.grid(sticky=W+N+E+S)
        
        # try and make the menu
        self._makemenu()
        try:
            self.master.config(menu=self.menubar)
        except AttributeError:
            self.master.tk.call(self.master,"config","-menu",self.menubar)
                 
        # is there a default toolset saved?
        if os.path.exists('default.ts'): self.toolsload('default.ts')
        self.update_idletasks()
            
        # make the log panel?
        if logpanel:
            # we save the log IOT avoid calling getpanel each time
            l = Toplevel()
            self._log = LogPanel(l,self)
            self.addpanel(self._log._name,PanelRecord(l,self._log,"log"))
            self._log.update_idletasks()
            l.wm_geometry("-0-0")

    def _initialize(self): pass
    def _shutdown(self): pass
    def _makemenu(self): pass
    
    def getstate(self): return None

#### CALLBACKS ####

    def about(self): pass
    def help(self): pass
    def close(self): pass
    
    def unimplemented(self):
        """ displays info dialog with not implmented message """
        showinfo('Not Implemented',"This function not currently implemented",parent=self)
        
    def toolssave(self):
        """ saves current toolset configuration """
        fpath = asksaveasfilename(title='Save Toolset',
                                  filetypes=[('Toolset files','*.ts')])
        if fpath:
            gs = self.tk.winfo_geometry().split('+')
            ts = {}
            for panel in self._panels:
                c = self._panels[panel]
                c.pnl.update_idletasks()
                if c.desc != 'log':
                    if ts.has_key(c.desc):
                        ts[c.desc].append(c.tk.winfo_geometry())
                    else:
                        ts[c.desc] = [c.tk.winfo_geometry()]
            try:
                f = open(fpath,'wb')
                pickle.dump(ts,f)
                f.close()
            except Exception as e:
                self.logwrite(e,LOG_ERROR)

    def toolsload(self,fpath=None):
        """ loads a saved toolset configuration """
        if not fpath:
            fpath = askopenfilename(title='Open Toolset',
                                    filetypes=[('Toolset files','*.ts')],
                                    parent=self)
        
        if fpath:
            # open & get the saved windows + their geometry
            try:
                f = open(fpath,'rb')
                ts = pickle.load(f)
                f.close()
            except Exception as e:
                self.logwrite(e,LOG_ERROR)
            else:
                # for each saved open it (unless it already exists) and move to 
                # saved position
                for t in ts:
                    self.deletepanels(t)
                    for geos in ts[t]: self.showpanel(t)
                
                    i = 0
                    for panel in self.getpanels(t,False):
                        panel.tk.wm_geometry(ts[t][i])
                        i += 1
                    
    def panelquit(self):
        """ cleanly exits - shuts down as necessary """
        ans = askquestion('Quit?','Really Quit',parent=self)
        if ans == 'no':
            return
        else:
            self.logwrite('Quitting...')
            self._shutdown()
            self.quit()

    def logwrite(self,msg,mtype=LOG_NOERROR):
        """ writes msg to log or shows in error message """
        if self._log:
            self._log.logwrite(msg,mtype)
        else:
             showerror('Error',msg,parent=self)

    def panelclose(self,panel):
        """
         override panelclose, we need to remove all notification requests from 
         the panel before deleting it
        """
        if self._panels.has_key(panel):
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
