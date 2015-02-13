#!/usr/bin/env python
""" wraith-rt.py - defines the wraith gui

 TODO:
   
"""

__name__ = 'wraith-rt'
__license__ = 'GPL'
__version__ = '0.0.2'
__revdate__ = 'October 2014'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@hushmail.com'
__status__ = 'Development'

import wraith                       # helpful functions
from wraith.widgets.panel import *  # graphics suite

class DataBinPanel(SlavePanel):
    """ DataBinPanel - displays a set of data bins for retrieved data storage """
    def __init__(self,toplevel,chief):
        SlavePanel.__init__(self,toplevel,chief,"widgets/icons/databin.png")
        self.master.title("Bins")
        self.pack(expand=True,fill=BOTH,side=TOP)
        
        # internals
        self._bins = {}
        
        # create main frame
        self._body()

    def donothing(self): pass

    def _body(self):
        """ creates the body """
        frm = Frame(self)
        frm.pack(side=TOP,expand=False)
        
        # add the bin buttons
        bs = "ABCDEFG"
        for b in bs:
            try:
                self._bins[b] = {'img':ImageTk.PhotoImage(Image.open('widgets/icons/bin%s.png'%b))}
            except:
                self._bins[b] = {'img':None}
                self._bins[b]['btn'] = Button(frm,text=b,command=self.donothing)
            else:
                self._bins[b]['btn'] = Button(frm,image=self._bins[b]['img'],command=self.donothing)
            self._bins[b]['btn'].grid(row=0,column=bs.index(b),sticky=W)

class AboutPanel(SlavePanel):
    """ AboutPanel - displays a simple About Panel """
    def __init__(self,toplevel,chief):
        SlavePanel.__init__(self,toplevel,chief,None)
        self.master.title("About Wraith")
        self.pack(expand=True,fill=BOTH,side=TOP)
        self._body()

    def _body(self):
        frm = Frame(self)
        frm.pack(side=TOP,fill=BOTH,expand=True)
        self.logo = ImageTk.PhotoImage(Image.open("widgets/icons/wraith-banner.png"))
        Label(frm,bg="white",image=self.logo).grid(row=0,column=0,sticky=N)
        Label(frm,text="wraith-rt %s" % __version__,fg="white",font=("Roman",16,'bold')).grid(row=1,column=0,sticky=N)
        Label(frm,text="Wireless assault, reconnaissance, collection and exploitation toolkit").grid(row=2,column=0,sticky=N)

class WraithPanel(MasterPanel):
    """ WraithPanel - master panel for wraith gui """
    def __init__(self,toplevel):
        MasterPanel.__init__(self,toplevel,"Wraith  v%s" % wraith.__version__,
                             [],True,"widgets/icons/wraith.png")
        self.tk.wm_geometry("350x3+0+0")
        self.tk.resizable(0,0)
        self.logwrite("Wraith v%s" % wraith.__version__)

    def _initialize(self): pass
    def _shutdown(self): pass
    
    def _makemenu(self):
        """ make the menu """
        self.menubar = Menu(self)
        
        # File Menu
        self.mnuFile = Menu(self.menubar,tearoff=0)
        self.mnuFile.add_command(label="Exit",command=self.panelquit)
        
        # View Menu
        self.mnuView = Menu(self.menubar,tearoff=0)
        self.mnuView.add_command(label="Data Bins",command=self.viewdatabins)
        
        # Help Menu
        self.mnuHelp = Menu(self.menubar,tearoff=0)
        self.mnuHelp.add_command(label="About",command=self.about)
        self.mnuHelp.add_command(label="Help",command=self.help)
        
        # add the menus
        self.menubar.add_cascade(label="File",menu=self.mnuFile)
        self.menubar.add_cascade(label="View",menu=self.mnuView)
        self.menubar.add_cascade(label="Help",menu=self.mnuHelp)

#### MENU CALLBACKS

    def viewdatabins(self):
        """ display the data bins panel """
        panel = self.getpanels("databin",False)
        if not panel:
            t = Toplevel()
            pnl = DataBinPanel(t,self)
            self.addpanel(pnl._name,PanelRecord(t,pnl,"databin"))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

    def about(self):
        """ display the about panel """
        panel = self.getpanels("about",False)
        if not panel:
            t = Toplevel()
            pnl = AboutPanel(t,self)
            self.addpanel(pnl._name,PanelRecord(t,pnl,"about"))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()
        #showinfo("About Wraith",
        #         "Wraith v%s Copyright %s" % (wraith.__version__,wraith.__date__),
        #         parent=self)

    def help(self):
        """ display the help panel """
        self.unimplemented()

if __name__ == 'wraith-rt':
    t = Tk()
    t.option_add('*foreground','blue')                # normal fg color
    t.option_add('*background','black')               # normal bg color
    t.option_add('*activeBackground','black')         # bg on mouseover
    t.option_add('*activeForeground','blue')          # fg on mouseover
    t.option_add('*disabledForeground','gray')        # fg on disabled widget
    t.option_add('*disabledBackground','black')       # bg on disabled widget
    t.option_add('*troughColor','black')              # trough on scales/scrollbars
    WraithPanel(t).mainloop()