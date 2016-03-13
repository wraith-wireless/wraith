#!/usr/bin/env python
""" subpanels.py - defines the subpanels called by the wraith Master panel """

__name__ = 'subpanels'
__license__ = 'GPL v3.0'
__version__ = '0.0.5'
__revdate__ = 'January 2016'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import Tkinter as tk                       # gui constructs
import tkFileDialog as tkFD                # import file gui dialogs
import tkSimpleDialog as tkSD              # input dialogs
import tkMessageBox as tkMB                # simple info dialgos
import ttk                                 # ttk widgets
import mgrs                                # for mgrs2latlon conversions etc
import math                                # for conversions, calculations
import time                                # for timestamps
from PIL.ImageTk import PhotoImage         # image loading
from PIL.Image import open as imgopen      # image opening
import psycopg2 as psql                    # postgresql api
import psycopg2.extras as pextras          # cursors and such
import ConfigParser                        # config file parsing
import threading                           # Threads et al
import select                              # non-blocking poll
import socket                              # socket errors from C2C
import wraith                              # version info & constants
import wraith.widgets.panel as gui         # graphics suite
from wraith.wifi.interface import radio    # wireless interface details
from wraith.wifi.standards import mpdu     # for 802.11 types/subtypes
from wraith.wifi.standards import channels # available channels
from wraith.utils import timestamps        # valid data/time
from wraith.utils import landnav           # lang nav utilities
from wraith.utils import cmdline           # cmdline functionality
from wraith.utils import valrep            # validity checks

# Some constants
COPY = u"\N{COPYRIGHT SIGN}"

#### MENU PANELS

# Wraith->Configure
class WraithConfigPanel(gui.ConfigPanel):
    """ Display Wraith Configuration Panel """
    def __init__(self,tl,chief):
        gui.ConfigPanel.__init__(self,tl,chief,"Configure Wraith")

    def _makegui(self,frm):
        """ set up entry widgets """
        # Storage Configuration
        frmS = ttk.LabelFrame(frm,text='Storage')
        frmS.grid(row=0,column=0,sticky='nwse')
        ttk.Label(frmS,text='Host: ').grid(row=0,column=0,sticky='w')
        self._entHost = ttk.Entry(frmS,width=15)
        self._entHost.grid(row=0,column=1,sticky='e')
        ttk.Label(frmS,text=' ').grid(row=0,column=2) # separator
        ttk.Label(frmS,text='Port: ').grid(row=0,column=3,sticky='w')
        self._entPort = ttk.Entry(frmS,width=5)
        self._entPort.grid(row=0,column=4,sticky='w')
        ttk.Label(frmS,text='DB: ').grid(row=1,column=0,sticky='w')
        self._entDB = ttk.Entry(frmS,width=10)
        self._entDB.grid(row=1,column=1,sticky='w')
        ttk.Label(frmS,text='User: ').grid(row=1,column=3,sticky='w')
        self._entUser = ttk.Entry(frmS,width=10)
        self._entUser.grid(row=1,column=4,sticky='e')
        ttk.Label(frmS,text='PWD: ').grid(row=4,column=0,sticky='w')
        self._entPWD = ttk.Entry(frmS,width=20)
        self._entPWD.grid(row=4,column=1,columnspan=4,sticky='w')

        # Policy Configuration
        frmP = ttk.LabelFrame(frm,text='Policy')
        frmP.grid(row=1,column=0,sticky='nswe')

        # polite
        ttk.Label(frmP,text="Polite:").grid(row=0,column=0,sticky='w')
        self._vpolite = tk.IntVar(self)
        ttk.Radiobutton(frmP,text='On',variable=self._vpolite,value=1).grid(row=0,column=1,sticky='w')
        ttk.Radiobutton(frmP,text='Off',variable=self._vpolite,value=0).grid(row=1,column=1,sticky='w')

        # separator label
        ttk.Label(frmP,text=" ").grid(row=0,column=2)

        # shutdown
        ttk.Label(frmP,text="Shutdown:").grid(row=0,column=3,sticky='w')
        self._vstop = tk.IntVar(self)
        ttk.Radiobutton(frmP,text='Auto',variable=self._vstop,value=1).grid(row=0,column=4,sticky='w')
        ttk.Radiobutton(frmP,text='Manual',variable=self._vstop,value=0).grid(row=1,column=4,sticky='w')

    def _initialize(self):
        """ insert values from config file into entry boxes """
        conf = ConfigParser.RawConfigParser()
        if not conf.read(wraith.WRAITHCONF):
            self.err("File Not Found","File wraith.conf was not found")
            return

        # in case the conf file is invalid, set to empty if not present
        self._entHost.delete(0,tk.END)
        if conf.has_option('Storage','host'): self._entHost.insert(0,conf.get('Storage','host'))

        self._entPort.delete(0,tk.END)
        if conf.has_option('Storage','port'): self._entPort.insert(0,conf.get('Storage','port'))

        self._entDB.delete(0,tk.END)
        if conf.has_option('Storage','db'): self._entDB.insert(0,conf.get('Storage','db'))

        self._entUser.delete(0,tk.END)
        if conf.has_option('Storage','user'): self._entUser.insert(0,conf.get('Storage','user'))

        self._entPWD.delete(0,tk.END)
        if conf.has_option('Storage','pwd'): self._entPWD.insert(0,conf.get('Storage','pwd'))

        if conf.has_option('Policy','polite') and conf.get('Policy','polite').lower() == 'off':
            self._vpolite.set(0)
        else:
            self._vpolite.set(1)

        if conf.has_option('Policy','shutdown') and conf.get('Policy','shutdown').lower() == 'manual':
            self._vstop.set(0)
        else:
            self._vstop.set(1)

    def _validate(self):
        """ validate entries """
        host = self._entHost.get()
        if not valrep.validaddr(host): return False
        port = self._entPort.get()
        try:
            port = int(port)
            if port < 1024 or port > 65535: raise RuntimeError("")
        except:
            self.err("Invalid Input","Port must be a number between 1024 and 65535")
            return False
        if len(self._entDB.get()) < 1 or len(self._entDB.get()) > 15:
            self.err("Invalid Input","DB name must be between 1 and 15 characters")
            return False
        if len(self._entUser.get()) < 1 or len(self._entUser.get()) > 15:
            self.err("Invalid Input","User name must be between 1 and 15 characters")
            return False
        if len(self._entPWD.get()) < 1 or len(self._entPWD.get()) > 15:
            self.err("Invalid Input","Password must be between 1 and 15 characters")
            return False
        return True

    def _write(self):
        """ write entry inputs to config file """
        fout = None
        try:
            cp = ConfigParser.ConfigParser()
            cp.add_section('Storage')
            cp.set('Storage','host',self._entHost.get())
            cp.set('Storage','port',self._entPort.get())
            cp.set('Storage','db',self._entDB.get())
            cp.set('Storage','user',self._entUser.get())
            cp.set('Storage','pwd',self._entUser.get())
            cp.add_section('Policy')
            cp.set('Policy','polite','on' if self._vpolite else 'off')
            cp.set('Policy','shutdown','auto' if self._vstop else 'manual')
            fout = open(wraith.WRAITHCONF,'w')
            cp.write(fout)
        except IOError as e:
            self.err("File Error","Error <{0}> writing to config file".format(e))
        except ConfigParser.Error as e:
            self.err("Configuration Error",
                     "Error <{0}> writing config file".format(e))
        else:
            self.info('Success',"Restart for changes to take effect")
        finally:
            if fout: fout.close()

# Tools->Convert
class ConvertPanel(gui.SimplePanel):
    """ several conversion utilities """
    def __init__(self,tl,chief):
        self._mgrs = mgrs.MGRS()
        gui.SimplePanel.__init__(self,tl,chief,"Conversions","widgets/icons/convert.png")

    def _body(self):
        """ creates the body """
        # create the location frame
        frmGeo = ttk.LabelFrame(self,text='Location')
        frmGeo.grid(row=0,column=0,sticky='w')
        # add widgets to the location frame
        ttk.Label(frmGeo,text='Lat/Lon: ').grid(row=0,column=0,sticky='w')
        self._entLatLon = ttk.Entry(frmGeo,width=15)
        self._entLatLon.grid(row=0,column=1,sticky='w')
        ttk.Label(frmGeo,text=' MGRS: ').grid(row=0,column=2,sticky='w')
        self._entMGRS = ttk.Entry(frmGeo,width=15)
        self._entMGRS.grid(row=0,column=3,sticky='w')
        ttk.Button(frmGeo,text='Convert',width=8,command=self.convertgeo).grid(row=0,column=4)
        # create the power frame
        frmPwr = ttk.LabelFrame(self,text='Power')
        frmPwr.grid(row=1,column=0,sticky='n')
        # add widgets to the power frame
        ttk.Label(frmPwr,text="dBm: ").grid(row=0,column=0)
        self._entdBm = ttk.Entry(frmPwr,width=8)
        self._entdBm.grid(row=0,column=1)
        ttk.Label(frmPwr,text=" mBm: ").grid(row=0,column=2)
        self._entmBm = ttk.Entry(frmPwr,width=8)
        self._entmBm.grid(row=0,column=3)
        ttk.Label(frmPwr,text=" mW: ").grid(row=0,column=4)
        self._entmW = ttk.Entry(frmPwr,width=8)
        self._entmW.grid(row=0,column=5)
        ttk.Button(frmPwr,text='Convert',width=8,command=self.convertpwr).grid(row=0,column=6)
        frmBtns = ttk.Frame(self,borderwidth=0)
        frmBtns.grid(row=2,column=0,sticky='n')
        ttk.Button(frmBtns,text='OK',width=6,command=self.delete).grid(row=0,column=0)
        ttk.Button(frmBtns,text='Clear',width=6,command=self.clear).grid(row=0,column=1)

    def convertgeo(self):
        """convert geo from lat/lon to mgrs or vice versa """
        m = self._entMGRS.get()
        ll = self._entLatLon.get()
        if m and ll: self.err('Error',"One field must be empty")
        else:
            if m:
                try:
                    ll = self._mgrs.toLatLon(m)
                    self._entLatLon.insert(0,"%.3f %.3f" % (ll[0],ll[1]))
                except:
                    self.err('Error',"MGRS is not valid")
            elif ll:
                try:
                    ll = ll.split()
                    self._entMGRS.insert(0,self._mgrs.toMGRS(ll[0],ll[1]))
                except:
                    self.err('Error',"Lat/Lon is not valid")

    def convertpwr(self):
        """ convert dBm to mW or vice versa """
        d = self._entdBm.get()
        w = self._entmW.get()
        m = self._entmBm.get()
        if d and not (m or w):
            try:
                w = math.pow(10,(float(d)/10.0))
                m = 100 * float(d)
                self._entmW.insert(0,'%.3f' % w)
                self._entmBm.insert(0,'%.3f' % m)
            except:
                self.err('Error',"dBm is not valid")
        elif w and not (m or d):
            try:
                d = 10*math.log10(float(w))
                m = 100 * d
                self._entdBm.insert(0,'%.3f' % d)
                self._entmBm.insert(0,'%.3f' % m)
            except:
                self.err('Error',"dBm is not valid")
        elif m and not (d or m):
            try:
                d = float(m) / 100
                w = math.pow(10,(float(d)/10.0))
                self._entdBm.insert(0,'%.3f' % d)
                self._entmW.insert(0,'%.3f' % w)
            except:
                self.err('Error',"mBm is not valid")
        else: self.err('Error',"Two fields must be empty")

    def clear(self):
        """ clear all entries """
        self._entLatLon.delete(0,tk.END)
        self._entMGRS.delete(0,tk.END)
        self._entdBm.delete(0,tk.END)
        self._entmBm.delete(0,tk.END)
        self._entmW.delete(0,tk.END)

#### CALCULATIONS - dict of calculation options for CalculatePanel
CALCS = {'EIRP':{'inputs':[('Pwr (mW)',5,'float'),('Gain (dBi)',5,'float')],
                 'answer':("10*math.log10($0) + $1",'dB'),'rc':[2]},
         'FSPL':{'inputs':[('Distance (m)',7,'float'),('RF (MHz)',5,'float')],
                  'answer':("20*math.log10($0/1000) + 20*math.log10($1) + 32.44",'dB'),
                  'rc':[2]},
         'Link Budget':{'inputs':[('Tx Pwr (mW)',5,'float'),('Tx Gain (dBi)',3,'float'),
                                  ('Tx Loss (dB)',3,'float'),('Rx Gain (dBi)',3,'float'),
                                  ('Rx Loss (dB)',3,'float'),('Distance (kM)',3,'float'),
                                  ('RF (MHz)',4,'float')],
                        'answer':("10*math.log10($0)+$1-$2+$3-$4-(20*math.log10($5) + 20*math.log10($6) + 32.44)",'dB'),
                        'rc':[3,2,2]},
         'Fresnel Zone':{'inputs':[('Dist. 1 (kM)',5,'float'),
                                   ('Dist. 2 (kM)',5,'float'),
                                   ('RF (MHz)',4,'float'),
                                   ('Zone #',3,'int')],
                         'answer':("17.3*math.sqrt(($3/($2/1000))*($1*$0/($1+$0)))",'m'),
                         'rc':[4]},
         'Distance':{'inputs':[("Start (mgrs)",15,'str'),("End (mgrs)",15,'str')],
                     'answer':("landnav.dist($0,$1)[0]",'m'),
                     'rc':[1,1]},
         'Terminus':{'inputs':[("Point (mgrs)",15,'str'),("LOB (TN)",4,'float'),
                               ("Dist (m)",5,'float')],
                     'answer':("landnav.terminus($0,$1,$2)[2]",'mgrs'),
                     'rc':[1,2]},
         'Cut':{'inputs':[("Pt 1 (mgrs)",15,'str'),("LOB 1 (TN)",4,'float'),
                          ("Pt 2 (mgrs)",15,'str'),("LOB 2 (TN)",4,'float')],
                'answer':("landnav.findcut($0,$1,$2,$3)",'mgrs'),
                'rc':[2,2]}}

# Tools->Calculate(all)
class CalculatePanel(gui.SimplePanel):
    """
     Base calculator panel - a simple panel that displays specified entries and
     calculates a specified formula
    """
    def __init__(self,tl,chief,ttl,inputs,result,rc=None):
        """
          inputs is a list of tuples of the form t = (label,width,type) where:
           label is the text to display in the entry's label
           width is the width (# of characters) for the entry
           type is the conversion to use on the text from the entry (as a string)
           see above
          result is a tuple t = (formula,measurement) such that
           formula is a string representing the mathematical formula to evaluate
           where each placeholder $i is substituted with the value in entry i
           i.e. "$0 * $1" results in the multiplication of the value in entry 0
           and entry 1
           and measurement is the answer's measurement (string)
          rc (if specified) can be used to define how many entries per row to
          place. i.e. [3,2,2] designates 3 rows of 3 entries, 2 entries and 2 entries
        """
        # initiate variables prior to call SimplePanel::init
        self._entries = []
        self._inputs = inputs
        self._ans = tk.StringVar()
        self._ans.set("")
        self._formula = result[0]
        self._meas = result[1]
        self._rc = rc if rc else [len(inputs)]
        gui.SimplePanel.__init__(self,tl,chief,ttl,"widgets/icons/calculator.png")

    def _body(self):
        """ creates the body """
        # entries frame
        frmEnt = ttk.Frame(self,borderwidth=0)
        frmEnt.grid(row=0,column=0,sticky='w')

        # create the widgets
        inputs = []
        x = 0
        for r in self._rc:
            inputs.append(self._inputs[x:x+r])
            x += r

        r = 0
        i = 0
        for input in inputs:
            for c in xrange(len(input)):
                txt = " {0}: ".format(input[c][0])
                ttk.Label(frmEnt,text=txt).grid(row=r,column=c*2,sticky='w')
                self._entries.append(ttk.Entry(frmEnt,width=input[c][1]))
                self._entries[i].grid(row=r,column=c*2+1,sticky='w')
                i += 1
            r += 1

        # answer frame, then button frames
        frmAns = ttk.Frame(self,borderwidth=0)
        frmAns.grid(row=1,column=0,sticky='n')
        ttk.Label(frmAns,text="Answer: ").grid(row=0,column=0)
        ttk.Label(frmAns,width=20,textvariable=self._ans).grid(row=0,column=1)
        frmBtns = ttk.Frame(self,borderwidth=0)
        frmBtns.grid(row=2,column=0,sticky='ns')
        ttk.Button(frmBtns,text="Calculate",width=9,command=self.calc).grid(row=0,column=0)
        ttk.Button(frmBtns,text="Reset",width=9,command=self.clear).grid(row=0,column=1)
        ttk.Button(frmBtns,text="Close",width=9,command=self.delete).grid(row=0,column=2)

    def calc(self):
        """ apply formula with entries """
        f = self._formula
        # make sure no entries are empty substituting the entry's  value as we go
        for i,entry in enumerate(self._entries):
            x = entry.get()
            if x:
                f = f.replace('$%d' % i,"%s('%s')" % (self._inputs[i][2],x))
            else:
                self.err('Error',"All entries must be filled in")
                return

        # attempt to calculate
        try:
            self._ans.set("{0} {1}".format(str(eval(f)),self._meas))
        except ValueError as e:
            err = "{0} is not a valid input".format(e.message.split(':')[1].strip())
            self.err("Invalid Input",err)
        except Exception as e:
            self.err('Error',e)

    def clear(self):
        """ clear all entries """
        for entry in self._entries: entry.delete(0,tk.END)
        self._ans.set('')

class InterfacePanel(gui.PollingTabularPanel):
    """ a singular panel displaying info on available wireless nics """
    def __init__(self,tl,chief):
        gui.PollingTabularPanel.__init__(self,tl,chief,"Interfaces",5,
                                         [('PHY',gui.lenpix(6),str),
                                          ('NIC',gui.lenpix(5),str),
                                          ('MAC',gui.lenpix(15),str),
                                          ('Mode',gui.lenpix(7),str),
                                          ('Driver',gui.lenpix(10),str),
                                          ('Chipset',gui.lenpix(15),str)],
                                         "widgets/icons/sensor.png",False)

        # configure tree to show headings but not 0th column
        self._tree['show'] = 'headings'

    def pnlreset(self): pass

    def _shutdown(self): pass

    def pnlupdate(self):
        """ lists interfaces """
        # get list of current wifaces on system & list of wifaces in tree
        nics = radio.winterfaces()
        ls = self._tree.get_children()

        # remove nics that are no longer present
        for l in ls:
            if not l in nics: self._tree.delete(l)

        # add new system nics
        r = radio.Radio()
        for nic in nics:
            r.setnic(nic)
            if nic in ls:
                # check if data has changed -
                cur = self._tree.set(nic)
                if cur['PHY'] != r.phy: self._tree.set(nic,'PHY',r.phy)
                if cur['MAC'] != r.hwaddr: self._tree.set(nic,'MAC',r.hwaddr)
                if cur['Mode'] != r.mode: self._tree.set(nic,'Mode',r.mode)
                if cur['Driver'] != r.driver: self._tree.set(nic,'Driver',r.driver)
                if cur['Chipset'] != r.chipset: self._tree.set(nic,'Chipset',r.chipset)
            else:
                self._tree.insert('','end',iid=nic,values=(r.phy,nic,r.hwaddr,
                                                           r.mode,r.driver,r.chipset))
# View->DataBin
class DatabinPanel(gui.SimplePanel):
    """ DatabinPanel - displays a set of data bins for retrieved data storage """
    def __init__(self,tl,chief,conn):
        """
         initialization
         tl: the Toplevel
         chief: master panel
         conn: the db connection
        """
        self._bins = {}
        #self._curs = {}
        self._conn = conn
        gui.SimplePanel.__init__(self,tl,chief,'Databin',"widgets/icons/db.png")

    def _body(self):
        """ creates the body """
        # add the bin buttons
        # NOTE: for whatever reason, trying to create individual viewquery functions
        # for each bin results in issues, if the button w/ function call is
        # created directly in the loop. But, if a function is called that creates
        # the button w/ lambda function, there is no issue
        for b in wraith.BINS: self._makebin(self,b)

    def _makebin(self,frm,b):
        """ makes a button for bin b """
        # attempt to load the icon if it fails use text, save the name of this
        # button, then grid the button
        try:
            ipath = 'widgets/icons/bin{0}.png'.format(b)
            self._bins[b] = {'img':PhotoImage(imgopen(ipath))}
        except:
            self._bins[b] = {'img':None}
            self._bins[b]['btn'] = ttk.Button(frm,text=b,
                                              command=lambda:self.viewquery(b))
        else:
            self._bins[b]['btn'] = ttk.Button(frm,image=self._bins[b]['img'],
                                              command=lambda:self.viewquery(b))
        self._bins[b]['name'] = self._bins[b]['btn']._name
        self._bins[b]['btn'].grid(row=0,column=wraith.BINS.index(b),sticky='w')

        # bind the right click to this button to show a context menu
        self._bins[b]['btn'].bind('<Button-3>',self.binrc)

    def viewquery(self,b):
        """
         shows query panel for bin b
         :param b: the data bin
        """
        # notify user if not connected to database
        if not self._chief.isconnected:
            self.warn("Disconnected","Connect and try again")
            return

        panel = self.getpanels('query{0}'.format(b),False)
        if not panel:
            t = tk.Toplevel()
            pnl = QueryPanel(t,self,"Query [bin {0}]".format(b),b,
                             self._chief.connectstring)
            self.addpanel(pnl.name,gui.PanelRecord(t,pnl,"bin{0}".format(b)))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

    def binrc(self,event):
        """
         on right click, show context menu for this button
         :param event: required parameter from tk/ttk
        """
        # determine which bin
        #bin = None
        #for b in self._bins:
        #    if self._bins[b]['name'] == event.widget._name: bin = b

        # and show context menu
        mnu = tk.Menu(None,tearoff=0)
        mnu.add_command(label='Delete',command=self.unimplemented)
        mnu.add_command(label='Copy To',command=self.unimplemented)
        mnu.add_command(label='Move To',command=self.unimplemented)
        mnu.add_command(label='Export As',command=self.unimplemented)
        mnu.add_separator()
        mnu.add_command(label='Save',command=self.unimplemented)
        mnu.add_command(label='Open',command=self.unimplemented)
        mnu.tk_popup(event.x_root,event.y_root)

# Databin->Query

# Radiotap Flag constansts
RT_FLAGS = ['CFP','Short','WEP','Frag','FCS','Failed','Pad']
RT_FLAG_CFP   = 0
RT_FLAG_SHORT = 1
RT_FLAG_WEP   = 2
RT_FLAG_FRAG  = 3
RT_FLAG_FCS   = 4
RT_FLAG_FAIL  = 5
RT_FLAG_PAD   = 6

# Channel Flag constants
CH_FLAGS = ['Turbo','CCK','OFDM','2 GHz','5 Ghz','Passive','CCK-OFDM','GFSS']
CH_FLAGS_TURBO    = 0
CH_FLAGS_CCK      = 1
CH_FLAGS_OFDM     = 2
CH_FLAGS_2GHZ     = 3
CH_FLAGS_5GHZ     = 4
CH_FLAGS_PASSIVE  = 5
CH_FLAGS_CCK_OFDM = 6
CH_FLAGS_GFSS     = 7

# HT BWs (0: 20, 1: 40, 2: 20L, 3: 20U)
BW_FLAGS = ['20','40','20L','20U']
BW_20  = 0
BW_40  = 1
BW_20L = 2
BW_20U = 3

# Frame Control Flags constants
FC_FLAGS = ['To DS','From DS','More Frag','Retry','PWR Mgmt','More Data','Protected','Ordered']
FC_FLAGS_TODS      = 0
FC_FLAGS_FROMDS    = 1
FC_FLAGS_FRAG      = 2
FC_FLAGS_RETRY     = 3
FC_FLAGS_PWRMGMT   = 4
FC_FLAGS_MOREDATA  = 5
FC_FLAGS_PROTECTED = 6
FC_FLAGS_ORDERED   = 7

class QueryPanel(gui.SlavePanel):
    """Display query for data panel """
    def __init__(self,tl,parent,ttl,b,connstr):
        """
         tl: Toplevel
         parent: our master panel
         ttl: title
         b: databin querying for
         connstr: connection string dict
        """
        gui.SlavePanel.__init__(self,tl,parent,ttl,'widgets/icons/bin%s.png'%b)
        self._bin = b
        self._connstr = connstr
        self._makegui()
        self._makemenu()

    def _makegui(self):
        """ make the query gui """
        # three frames 1) data, 2) Filters, 3) buttons
        self.grid(sticky='nwse')

        # session/time frame
        # two subframes: 'left' Session(s) Frame has a tree view of sessions, 'right'
        # Period has entries to select from and to date/times. Additionally, below
        # the period subframe is a checkbox to enable data collation
        frmL = ttk.Frame(self)
        frmL.grid(row=0,column=0,sticky='nwse')
        frmR = ttk.Frame(self)
        frmR.grid(row=0,column=1,sticky='nwse')
        frmLS = ttk.LabelFrame(frmL,text='Session(s)')
        frmLS.grid(row=0,column=0,sticky='nwse')
        self._trSess = ttk.Treeview(frmLS)
        self._trSess.grid(row=0,column=0,sticky='nwse')
        self._trSess.config(height=8)
        self._trSess.config(selectmode='extended')
        self._trSess['show'] = 'headings'
        vscroll = ttk.Scrollbar(frmLS,orient=tk.VERTICAL,command=self._trSess.yview)
        vscroll.grid(row=0,column=1,sticky='ns')
        self._trSess['yscrollcommand'] = vscroll.set
        # configure session tree's headers & fill the tree w/ current sessions
        hdrs = ['ID','Host','Start','Frames']
        hdrlens = [gui.lenpix(3),gui.lenpix(4),gui.lenpix(13),gui.lenpix(6)]
        self._trSess['columns'] = hdrs
        for i,hdr in enumerate(hdrs):
            self._trSess.column(i,width=hdrlens[i],anchor=tk.CENTER)
            self._trSess.heading(i,text=hdr)
        self._getsessions()
        # enable ctrl-a (select all) on the tree
        self._trSess.bind('<Control-a>',self.trsessca)
        frmRP = ttk.LabelFrame(frmR,text='Period')
        frmRP.grid(row=0,column=0,sticky='nwse')
        ttk.Label(frmRP,text='YYYY-MM-DD').grid(row=0,column=1,sticky='ne')
        ttk.Label(frmRP,text='HH:MM:SS').grid(row=0,column=2,sticky='ne')
        ttk.Label(frmRP,text='From: ').grid(row=1,column=0,sticky='w')
        self._entFromDate = ttk.Entry(frmRP,width=10)
        self._entFromDate.grid(row=1,column=1,sticky='e')
        self._entFromTime = ttk.Entry(frmRP,width=9)
        self._entFromTime.grid(row=1,column=2,sticky='e')
        ttk.Button(frmRP,text='Now',width=4,command=self.fromnow).grid(row=1,column=3,sticky='w')
        ttk.Label(frmRP,text='To: ').grid(row=2,column=0,sticky='w')
        self._entToDate = ttk.Entry(frmRP,width=10)
        self._entToDate.grid(row=2,column=1,sticky='e')
        self._entToTime = ttk.Entry(frmRP,width=9)
        self._entToTime.grid(row=2,column=2,sticky='e')
        ttk.Button(frmRP,text='Now',width=4,command=self.tonow).grid(row=2,column=3,sticky='w')
        self._vcollate = tk.IntVar()
        ttk.Checkbutton(frmRP,text="Collate",variable=self._vcollate).grid(row=3,column=0,sticky='nwse')

        # filter on frame
        frmFO = ttk.LabelFrame(frmR,text="Filter On")
        frmFO.grid(row=1,column=0,sticky='nwse')
        filters = ['Sensor','Signal','Traffic']
        self._vfilteron = []
        for i,f in enumerate(filters):
            self._vfilteron.append(tk.IntVar())
            ttk.Checkbutton(frmFO,text=f,variable=self._vfilteron[i]).grid(row=0,column=i,sticky='w')

        # progress frame
        frmP = ttk.Frame(frmR)
        frmP.grid(row=2,column=0,sticky='nwse')
        self._pb = ttk.Progressbar(frmP,style="reg.Horizontal.TProgressbar",
                                   maximum=10,orient=tk.HORIZONTAL,mode='determinate')
        self._pb.grid(row=0,column=0,sticky='nwse')

        # 3 buttons query,reset and cancel
        frmB = ttk.Frame(frmR)
        frmB.grid(row=3,column=0,sticky='ns')
        ttk.Button(frmB,text='Query',width=6,command=self.query).grid(row=0,column=0)
        ttk.Button(frmB,text='Clear',width=6,command=self.widgetreset).grid(row=0,column=1)
        ttk.Button(frmB,text='Cancel',width=6,command=self.delete).grid(row=0,column=2)

        # filters frame (For now, allow filters on Radio/Sensor,Signal,Traffic,STA
        frmF = ttk.LabelFrame(self,text='Filters')
        frmF.grid(row=1,column=0,columnspan=2,sticky='nwse')
        nb = ttk.Notebook(frmF)
        nb.grid(row=0,column=0,sticky='nwse')

        # Sensor tab
        frmS = ttk.Frame(nb)
        frmSL = ttk.Frame(frmS)
        frmSL.grid(row=0,column=0,sticky='nwse')
        frmSR = ttk.Frame(frmS)
        frmSR.grid(row=0,column=1,sticky='nwse')
        ttk.Label(frmSL,text='Interface').grid(row=0,column=0,columnspan=2,sticky='w')
        ttk.Label(frmSL,text='Not').grid(row=0,column=2,sticky='w')
        ttk.Label(frmSL,text='Role').grid(row=0,column=3,sticky='w')
        ttk.Label(frmSL,text='Host: ').grid(row=1,column=0,sticky='w')
        self._entSensorHost = ttk.Entry(frmSL,width=17)
        self._entSensorHost.grid(row=1,column=1,sticky='e')
        self._vnothost = tk.IntVar()
        ttk.Checkbutton(frmSL,variable=self._vnothost).grid(row=1,column=2,sticky='w')
        ttk.Label(frmSL,text='NIC: ').grid(row=2,column=0,sticky='w')
        self._entSensorNic = ttk.Entry(frmSL,width=10)
        self._entSensorNic.grid(row=2,column=1,sticky='e')
        self._vnotnic = tk.IntVar()
        ttk.Checkbutton(frmSL,variable=self._vnotnic).grid(row=2,column=2,sticky='w')
        ttk.Label(frmSL,text='MAC: ').grid(row=3,column=0,sticky='w')
        self._entSensorMac = ttk.Entry(frmSL,width=17)
        self._entSensorMac.grid(row=3,column=1,sticky='e')
        self._vnotmac = tk.IntVar()
        ttk.Checkbutton(frmSL,variable=self._vnotmac).grid(row=3,column=2,sticky='w')
        ttk.Label(frmSL,text='Spoof: ').grid(row=4,column=0,sticky='w')
        self._entSensorSpoof = ttk.Entry(frmSL,width=17)
        self._entSensorSpoof.grid(row=4,column=1,sticky='e')
        self._vnotspoof = tk.IntVar()
        ttk.Checkbutton(frmSL,variable=self._vnotspoof).grid(row=4,column=2,sticky='w')
        ttk.Label(frmSL,text='STDs: ').grid(row=5,column=0,sticky='w')
        self._entSensorStd = ttk.Entry(frmSL,width=5)
        self._entSensorStd.grid(row=5,column=1,sticky='e')
        self._vnotstd = tk.IntVar()
        ttk.Checkbutton(frmSL,variable=self._vnotstd).grid(row=5,column=2,sticky='w')
        ttk.Label(frmSL,text='Driver: ').grid(row=6,column=0,sticky='w')
        self._entSensorDriver = ttk.Entry(frmSL,width=17)
        self._entSensorDriver.grid(row=6,column=1,sticky='e')
        self._vnotdriver = tk.IntVar()
        ttk.Checkbutton(frmSL,variable=self._vnotdriver).grid(row=6,column=2,sticky='w')
        self._vrecon = tk.IntVar()
        ttk.Checkbutton(frmSL,text='Abad',variable=self._vrecon).grid(row=1,column=3,sticky='w')
        self._vcoll = tk.IntVar()
        ttk.Checkbutton(frmSL,text='Shama',variable=self._vcoll).grid(row=2,column=3,sticky='w')
        frmSRL = ttk.LabelFrame(frmSR,text='Location')
        frmSRL.grid(row=0,column=1,sticky='nwse')
        ttk.Label(frmSRL,text='Center PT: ').grid(row=1,column=5,sticky='w')
        self._entCenterPT = ttk.Entry(frmSRL,width=15)
        self._entCenterPT.grid(row=1,column=6,sticky='w')
        ttk.Label(frmSRL,text='Radius: (m)').grid(row=2,column=5,sticky='w')
        self._entRadius = ttk.Entry(frmSRL,width=6)
        self._entRadius.grid(row=2,column=6,sticky='w')
        self.vfixed = tk.IntVar()
        ttk.Checkbutton(frmSRL,text='Fixed',variable=self.vfixed).grid(row=3,column=5,sticky='w')
        self._vdynamic = tk.IntVar()
        ttk.Checkbutton(frmSRL,text='Dynamic',variable=self._vdynamic).grid(row=3,column=6,sticky='w')
        nb.add(frmS,text='Sensor')
        # signal tab
        frmSig = ttk.Frame(nb)
        frmSigParams = ttk.Frame(frmSig)
        frmSigParams.grid(row=0,column=0,sticky='nwse')
        ttk.Label(frmSigParams,text='Not').grid(row=0,column=2,sticky='w')
        ttk.Label(frmSigParams,text='Standard(s)').grid(row=1,column=0,sticky='w')
        self._entSignalStd = ttk.Entry(frmSigParams,width=10)
        self._entSignalStd.grid(row=1,column=1,sticky='e')
        self._vnotstd = tk.IntVar()
        ttk.Checkbutton(frmSigParams,variable=self._vnotstd).grid(row=1,column=2,sticky='w')
        ttk.Label(frmSigParams,text='Rate(s)').grid(row=2,column=0,sticky='w')
        self._entSignalRate = ttk.Entry(frmSigParams,width=10)
        self._entSignalRate.grid(row=2,column=1,sticky='e')
        self._vnotrate = tk.IntVar()
        ttk.Checkbutton(frmSigParams,variable=self._vnotrate).grid(row=2,column=2,sticky='w')
        ttk.Label(frmSigParams,text='Channel(s)').grid(row=3,column=0,sticky='w')
        self._entSignalCh = ttk.Entry(frmSigParams,width=10)
        self._entSignalCh.grid(row=3,column=1,sticky='e')
        self._vnotch = tk.IntVar()
        ttk.Checkbutton(frmSigParams,variable=self._vnotch).grid(row=3,column=2,sticky='w')
        # flags and channel flags are contained in separate frames
        # we want rows of 4 flags
        frmSigFlags = ttk.LabelFrame(frmSig,text='Flags')
        frmSigFlags.grid(row=1,column=0,sticky='nwse')
        self._vrtflags = []
        for i,RT_FLAG in enumerate(RT_FLAGS):
            self._vrtflags.append(tk.IntVar())
            chk = ttk.Checkbutton(frmSigFlags,text=RT_FLAG,variable=self._vrtflags[i])
            chk.grid(row=(i / 4),column=(i % 4),sticky='w')
        ttk.Separator(frmSigFlags,orient=tk.VERTICAL).grid(row=0,column=4,rowspan=2,sticky='ns')
        self._vandorrtflags = tk.IntVar()
        ttk.Radiobutton(frmSigFlags,text='AND',variable=self._vandorrtflags,value=0).grid(row=0,column=5,sticky='w')
        ttk.Radiobutton(frmSigFlags,text='OR',variable=self._vandorrtflags,value=1).grid(row=1,column=5,sticky='w')
        frmSigChFlags = ttk.LabelFrame(frmSig,text="Channel Flags")
        frmSigChFlags.grid(row=2,column=0,sticky='nwse')
        self._vchflags = []
        for i,CH_FLAG in enumerate(CH_FLAGS):
            self._vchflags.append(tk.IntVar())
            chk = ttk.Checkbutton(frmSigChFlags,text=CH_FLAG,variable=self._vchflags[i])
            chk.grid(row=(i / 4),column=(i % 4),sticky='w')
        ttk.Separator(frmSigChFlags,orient=tk.VERTICAL).grid(row=0,column=4,rowspan=2,sticky='ns')
        self.vandorchflags = tk.IntVar()
        ttk.Radiobutton(frmSigChFlags,text='AND',variable=self.vandorchflags,value=0).grid(row=0,column=5,sticky='w')
        ttk.Radiobutton(frmSigChFlags,text='OR',variable=self.vandorchflags,value=1).grid(row=1,column=5,sticky='w')
        # add HT data parameters
        frmSigHT = ttk.LabelFrame(frmSig,text="802.11 Parameters")
        frmSigHT.grid(row=0,column=1,rowspan=2,sticky='nwse')
        frmSigHT1 = ttk.Frame(frmSigHT)
        frmSigHT1.grid(row=0,column=0,sticky='nwse')
        self._vhtonly = tk.IntVar()
        ttk.Checkbutton(frmSigHT1,text="HT Only",variable=self._vhtonly).grid(row=0,column=0,sticky='nwse')
        self._vampdu = tk.IntVar()
        ttk.Checkbutton(frmSigHT1,text='AMPDU',variable=self._vampdu).grid(row=0,column=1,sticky='nwse')
        frmSigHTBW = ttk.Frame(frmSigHT)
        frmSigHTBW.grid(row=1,column=0,sticky='nwse')
        ttk.Label(frmSigHTBW,text='BW: ').grid(row=0,column=0,sticky='nwse')
        self._vbws = []
        for i in xrange(len(BW_FLAGS)):
            self._vbws.append(tk.IntVar())
            chk = ttk.Checkbutton(frmSigHTBW,text=BW_FLAGS[i],variable=self._vbws[i])
            chk.grid(row=0,column=i+1,sticky='w')
        frmSigHT2 = ttk.Frame(frmSigHT)
        frmSigHT2.grid(row=2,column=0)
        ttk.Label(frmSigHT2,text='GI: ').grid(row=0,column=0,sticky='nwse')
        self._vgis = [tk.IntVar(),tk.IntVar()]
        ttk.Checkbutton(frmSigHT2,text='Short',variable=self._vgis[0]).grid(row=0,column=1,sticky='nwse')
        ttk.Checkbutton(frmSigHT2,text='Long',variable=self._vgis[1]).grid(row=1,column=1,sticky='nwse')
        self._vformats = [tk.IntVar(),tk.IntVar()]
        ttk.Label(frmSigHT2,text='Format: ').grid(row=0,column=2,sticky='nwse')
        ttk.Checkbutton(frmSigHT2,text='Mixed',variable=self._vgis[0]).grid(row=0,column=3,sticky='nwse')
        ttk.Checkbutton(frmSigHT2,text='Greenfield',variable=self._vgis[1]).grid(row=1,column=3,sticky='nwse')
        frmSigHT3 = ttk.Frame(frmSigHT)
        frmSigHT3.grid(row=3,column=0,sticky='nwse')
        ttk.Label(frmSigHT3,text='MCS Index: ').grid(row=0,column=0,sticky='nwse')
        self._entIndex = ttk.Entry(frmSigHT3,width=15)
        self._entIndex.grid(row=0,column=1,sticky='nwse')
        nb.add(frmSig,text='Signal')
        # traffic
        frmT = ttk.Frame(nb)
        frmL = ttk.Frame(frmT)
        frmL.grid(row=0,column=0,sticky='nwse')
        self._trTypes = ttk.Treeview(frmL)
        self._trTypes.grid(row=0,column=0,sticky='nwse')
        self._trTypes.config(height=10)
        self._trTypes.config(selectmode='extended')
        self._trTypes['show'] = 'tree'
        vscroll = ttk.Scrollbar(frmL,orient=tk.VERTICAL,command=self._trTypes.yview)
        vscroll.grid(row=0,column=1,sticky='ns')
        self._trTypes['yscrollcommand'] = vscroll.set
        # fill the tree
        self._trTypes['columns'] = ('one',)
        self._trTypes.column('#0',stretch=0,width=15,anchor='w')
        self._trTypes.column('one',stretch=0,width=140,anchor='w')
        self._trTypes.insert('','end',iid='MGMT',values=('MGMT',))
        for mgmt in mpdu.ST_MGMT_TYPES:
            if mgmt == 'rsrv': continue
            self._trTypes.insert('MGMT','end',
                                 iid="{0}.{1}".format('MGMT',mgmt),
                                 values=(mgmt,))
        self._trTypes.insert('','end',iid='CTRL',values=('CTRL',))
        for ctrl in mpdu.ST_CTRL_TYPES:
            if ctrl == 'rsrv': continue
            self._trTypes.insert('CTRL','end',
                                 iid="{0}.{1}".format('CTRL',ctrl),
                                 values=(ctrl,))
        self._trTypes.insert('','end',iid='DATA',values=('DATA',))
        for data in mpdu.ST_DATA_TYPES:
            if data == 'rsrv': continue
            self._trTypes.insert('DATA','end',
                                 iid="{0}.{1}".format('DATA',data),
                                 values=(data,))
        frmR = ttk.Frame(frmT)
        frmR.grid(row=0,column=1,sticky='nswe')
        frmRFC = ttk.LabelFrame(frmR,text="Frame Control Frames")
        frmRFC.grid(row=0,column=0,sticky='nwse')
        self._vfcflags = []
        for i,FC_FLAG in enumerate(FC_FLAGS):
            self._vfcflags.append(tk.IntVar())
            chk = ttk.Checkbutton(frmRFC,text=FC_FLAG,variable=self._vfcflags[i])
            chk.grid(row=(i / 4),column=(i % 4),sticky='w')
        ttk.Separator(frmRFC,orient=tk.VERTICAL).grid(row=0,column=4,rowspan=2,sticky='ns')
        self.vandorfcflags = tk.IntVar()
        ttk.Radiobutton(frmRFC,text='AND',variable=self.vandorfcflags,value=0).grid(row=0,column=5,sticky='w')
        ttk.Radiobutton(frmRFC,text='OR',variable=self.vandorfcflags,value=1).grid(row=1,column=5,sticky='w')

        frmRA = ttk.LabelFrame(frmR,text='HW ADDR')
        frmRA.grid(row=1,column=0,sticky='nwse')
        ttk.Label(frmRA,text='Single: ').grid(row=0,column=0,sticky='nwse')
        self._entHWAddr = ttk.Entry(frmRA,width=17)
        self._entHWAddr.grid(row=0,column=1,sticky='nwse')
        ttk.Label(frmRA,text='File: ').grid(row=1,column=0,sticky='nwse')
        self._entSelFile = ttk.Entry(frmRA,width=20)
        self._entSelFile.grid(row=1,column=1,sticky='ne')
        ttk.Button(frmRA,text='Browse',width=6,command=self.browse).grid(row=1,column=2,sticky='nw')
        ttk.Button(frmRA,text='Clear',width=6,command=self.clearselfile).grid(row=1,column=3,sticky='nw')
        ttk.Label(frmRA,text='Limit To: ').grid(row=2,column=0)
        frmRAL = ttk.Frame(frmRA,border=0)
        frmRAL.grid(row=2,column=1,columnspan=3)
        self._vlimitto = []
        for i in xrange(4):
            self._vlimitto.append(tk.IntVar())
            chk = ttk.Checkbutton(frmRAL,
                                  text="ADDR {0}".format((i+1)),
                                  variable=self._vlimitto[i])
            chk.grid(row=0,column=i,sticky='nwse')
        nb.add(frmT,text='Traffic')

        # we have to force an update, get size of holding frame and set pbar's length
        self.update_idletasks()
        self._pb.configure(length=frmP.winfo_width())

    def _makemenu(self):
        """ display simple file menu with open/save option """
        self.menubar = tk.Menu(self)
        self.mnuFile = tk.Menu(self.menubar,tearoff=0)
        self.mnuFile.add_command(label='Open',command=self.qrysave)
        self.mnuFile.add_command(label='Save',command=self.qryload)
        self.mnuFile.add_separator()
        self.mnuFile.add_command(label='Quit',command=self.close)
        self.menubar.add_cascade(label='File',menu=self.mnuFile)
        try:
            self.master.config(menu=self.menubar)
        except AttributeError:
            self.master.tk.call(self.master,"config","-menu",self.menubar)

    # bindings
    def trsessca(self,event):
        """
         sessions tree ctrl-a -> selects all
         :param event: required param of tk/ttk
        """
        self._trSess.selection_set(self._trSess.get_children(''))

    # virtual implementations

    def _shutdown(self): pass
    def pnlreset(self): pass
    def pnlupdate(self): pass

    # menu callbacks

    def qrysave(self): pass

    def qryload(self): pass

    # button callbacks

    def query(self):
        """ queries db for specified data """
        if self._validate():
            self.setbusy()
            self.setbusy(False)

    def widgetreset(self):
        """ clears all user inputed data """
        # time periods
        for s in self._trSess.selection(): self._trSess.selection_remove(s)
        self._entFromDate.delete(0,tk.END)
        self._entFromTime.delete(0,tk.END)
        self._entToDate.delete(0,tk.END)
        self._entToTime.delete(0,tk.END)
        self._vcollate.set(0)
        # sensor
        self._entSensorHost.delete(0,tk.END)
        self._vnothost.set(0)
        self._entSensorNic.delete(0,tk.END)
        self._vnotnic.set(0)
        self._entSensorMac.delete(0,tk.END)
        self._vnotmac.set(0)
        self._entSensorSpoof.delete(0,tk.END)
        self._vnotspoof.set(0)
        self._entSensorStd.delete(0,tk.END)
        self._vnotstd.set(0)
        self._entSensorDriver.delete(0,tk.END)
        self._vnotdriver.set(0)
        self._vrecon.set(0)
        self._vcoll.set(0)
        self._entCenterPT.delete(0,tk.END)
        self._entRadius.delete(0,tk.END)
        self.vfixed.set(0)
        self._vdynamic.set(0)
        # signal
        self._entSignalStd.delete(0,tk.END)
        self._vnotstd.set(0)
        self._entSignalRate.delete(0,tk.END)
        self._vnotrate.set(0)
        self._entSignalCh.delete(0,tk.END)
        self._vnotch.set(0)
        for chk in self._vrtflags: chk.set(0)
        self._vandorrtflags.set(0)
        for chk in self._vchflags: chk.set(0)
        self.vandorchflags.set(0)
        self._vhtonly.set(0)
        self._vampdu.set(0)
        for chk in self._vbws: chk.set(0)
        for chk in self._vgis: chk.set(0)
        for chk in self._vformats: chk.set(0)
        self._entIndex.delete(0,tk.END)
        # traffic
        for s in self._trTypes.selection(): self._trTypes.selection_remove(s)
        for chk in self._vfcflags: chk.set(0)
        self.vandorfcflags.set(0)
        self._entHWAddr.delete(0,tk.END)
        self._entSelFile.delete(0,tk.END)
        for chk in self._vlimitto: chk.set(0)

    def fromnow(self):
        """assign now() to the from entries """
        d,t = timestamps.ts2iso(time.time()).split('T') # split isoformat on 'T'
        t = t[:8]                                       # drop the microseconds
        self._entFromDate.delete(0,tk.END)              # delete from entries
        self._entFromDate.insert(0,d)                   # and add now
        self._entFromTime.delete(0,tk.END)
        self._entFromTime.insert(0,t)

    def tonow(self):
        """ assign now() to the to entries """
        d,t = timestamps.ts2iso(time.time()).split('T') # split isoformat on 'T'
        t = t[:8]                                       # drop the microseconds
        self._entToDate.delete(0,tk.END)                # delete from entries
        self._entToDate.insert(0,d)                     # and add now
        self._entToTime.delete(0,tk.END)
        self._entToTime.insert(0,t)

    def browse(self):
        """ open a file browsing dialog for selector file """
        fpath = tkFD.askopenfilename(title="Open Selector File",
                                     filetypes=[("Text Files","*.txt"),
                                                ("Selector Files","*.sel")],
                                     parent=self)
        if fpath:
            self.update()
            self.clearselfile()
            self._entSelFile.insert(0,fpath)

    def clearselfile(self):
        """ clear the selection file """
        self._entSelFile.delete(0,tk.END)

    # private helper functions

    def _validate(self):
        """
         validates all entries
         NOTE: this does not validate for non-sensical queries i.e. those that
         will never return results
        """
        # period
        d = self._entFromDate.get()
        if d and not timestamps.validdate(d):
            self.err("Invalid Input","From date is not valid")
            return False
        t = self._entFromTime.get()
        if t and not timestamps.validtime(t):
            return False
        d = self._entToDate.get()
        if d and not timestamps.validdate(d):
            self.err("Invalid Input","To date is not valid")
            return False
        t = self._entToTime.get()
        if t and not timestamps.validtime(t):
            return False

        # only validate sensor entries if 'enabled'
        if self._vfilteron[0]:
            # allow all in host, nic, driver
            mac = self._entSensorMac.get().upper()
            if mac and not valrep.validhwaddr(mac):
                self.err("Invalid Input","MAC addr {0} is not valid".format(mac))
                return False
            mac = self._entSensorSpoof.get().upper()
            if mac and not valrep.validhwaddr(mac):
                self.err("Invalid Input","Spoof addr {0} is not valid".format(mac))
                return False
            stds = self._entSensorStd.get().split(',')
            if stds and stds != ['']:
                for std in stds:
                    if not std in ['a','b','g','n','ac']:
                        self.err("Invalid Input",
                                 "Invalid standard specifier {0}".format(std))
                        return False
            cp = self._entCenterPT.get()
            if cp and not landnav.validMGRS(cp):
                self.err("Invalid Input","Center point is not valid MGRS")
                return False

        # # only validate signal entries if 'enabled'
        if self._vfilteron[1]:
            stds = self._entSignalStd.get().split(',')
            if stds and stds != ['']:
                for std in stds:
                    if not std in ['a','b','g','n','ac']:
                        self.err("Invalid Input",
                                 "Invalid standard specifier {0}".format(std))
                        return False
            rs = self._entSignalRate.get().split(',')
            if rs and rs != ['']:
                try:
                    map(float,rs)
                except ValueError:
                    self.err("Invalid Input","Rate(s) must be numeric")
                    return False
            if not valrep.channellist(self._entSignalCh.get(),'scan'):
                self.err("Invalid Input","Invalid channel(s0 specification")
                return False
            mis = self._entIndex.get().split(',')
            if mis and mis != ['']:
                try:
                    mis = map(int,mis)
                except ValueError:
                    self.err("Invalid Input","MCS Index must be integer(s)")
                    return False
                else:
                    for mi in mis:
                        if mi < 0 or mi > 31:
                            self.err("Invalid Input","mcs index must be between 0 and 31")
                            return False

        # only validate traffic entries if 'enabled'
        if self._vfilteron[2]:
            mac = self._entHWAddr.get().upper()
            if mac and not valrep.validhwaddr(mac):
                self.err("Invalid Input","HW Addr {0} is not valid".format(mac))
                return False
            # check file path and file
            fin = None
            fpath = None
            try:
                fpath = self._entSelFile.get()
                fin = open(fpath,'r')
                ss = fin.read().split(',')
                for s in ss:
                    if not valrep.validhwaddr(s.strip()):
                        self.err("Invalid Input",
                                 "File {0} has invalid data {1}".format(fpath,s))
                        return False
            except IOError:
                self.err("Invalid Input",
                         "Select file {0} does not exist".format(fpath))
                return False
            else:
                if fin: fin.close()
        return True

    def _getsessions(self):
        """ retrieve all sessions and add to tree """
        # get a connection and cursor executing intial query
        conn = curs = None
        try:
            conn,err = cmdline.psqlconnect(self._connstr)
            if conn is None:
                self.err('Connect Error',err)
                return
            curs = conn.cursor(cursor_factory=pextras.DictCursor)
            curs.execute("SET TIME ZONE 'UTC';")
        except psql.Error as e:
            conn.rollback()
            conn.close()
            self.err('Query Error',e)
            return

        # pull out all sessions and insert into tree
        try:
            sql1 = "SELECT session_id,hostname,ip,lower(period) FROM sensor;"
            sql2 = "SELECT count(frame_id) FROM frame WHERE sid=%s;"
            curs.execute(sql1)
            ss = curs.fetchall()
            for s in ss:
                curs.execute(sql2,(s['session_id'],))
                fc = curs.fetchone()
                self._trSess.insert('','end',iid=str(s['session_id']),
                                    values=(s['session_id'],
                                    s['hostname'],
                                    s['lower'].strftime("%d%m%y %H%M%S"),
                                    fc['count']))
        except Exception as e:
            if conn: conn.rollback()
            self.err("Error Retrieving Sessions",e)
        finally:
            if curs: curs.close()
            if conn: conn.close()

# Data->Sessions
class SessionsPanel(gui.DBPollingTabularPanel):
    """ a singular panel which display information pertaining to sessions """
    def __init__(self,tl,chief,connect):
        gui.DBPollingTabularPanel.__init__(self,tl,chief,connect,"Sessions",5,
                                         [('ID',gui.lenpix(3),int),
                                          ('Host',gui.lenpix(5),str),
                                          ('Kernel',gui.lenpix(8),str),
                                          ('Start',gui.lenpix(13),str),
                                          ('Stop',gui.lenpix(13),str),
                                          ('GPSD',gui.lenpix(8),str),
                                          ('Abad',gui.lenpix(12),str),
                                          ('Shama',gui.lenpix(12),str),
                                          ('Frames',gui.lenpix(6),int)],
                                         "widgets/icons/sessions.png",False)

        # configure tree to show headings but not 0th column
        self._tree['show'] = 'headings'

    def _update_(self):
        """ lists sessions """
        # get current sessions in db and list of sessions in tree
        try:
            sql = "select * from sessions;"
            self._curs.execute(sql)
        except psql.Error as e:
            self._conn.rollback()
            self.logwrite("Sessions failed: {0}".format(e),gui.LOG_NOERR)
            return

        # use difference (ls,sids) to remove items no longer in the table
        ss = self._curs.fetchall()            # get all rows
        ls = self._tree.get_children()        # & all ids from tree

        # remove sessions from tree that are no longer in db
        sids = set([str(s['session_id']) for s in ss])  # make set of str ids
        diff = [sid for sid in ls if sid not in sids]   # get the difference
        for sid in diff: self._tree.delete(sid)         # & remove

        # add new sessions (& modify any changed sessions)
        for s in ss:
            sid = str(s['session_id'])
            host = s['hostname']
            start = s['start'].strftime("%d/%m/%y %H:%M:%S")
            stop = s['stop'].strftime("%d/%m/%y %H:%M:%S") if s['stop'] else ''
            kern = s['kernel'].replace('-generic','') # save some space
            devid = s['devid']
            abad = s['abad']
            shama = s['shama']
            nF = s['fcnt']
            if sid in ls: # session is present
                # check for changes (id and start are not checked0
                cur = self._tree.set(sid)
                if cur['Host'] != host: self._tree.set(sid,'Host',host)
                if cur['Kernel'] != kern: self._tree.set(sid,'Kernel',kern)
                if cur['Stop'] != stop: self._tree.set(sid,'Stop',stop)
                if cur['GPSD'] != devid: self._tree.set(sid,'GPSD',devid)
                if cur['Abad'] != abad: self._tree.set(sid,'Abad',abad)
                if cur['Shama'] != shama: self._tree.set(sid,'Shama',shama)
                if cur['Frames'] != nF: self._tree.set(sid,'Frames',nF)
            else:         # session not present
                self._tree.insert('','end',iid=sid,values=(sid,host,kern,start,stop,
                                                           devid,abad,shama,nF))

    def treerc(self,event):
        """
         show delete context menu for the specified item
         :param event: require param from tk/ttk
        """
        # get selected item(s) and item where right click occurred
        # if right click occurred outside selected items, select it
        sids = self._tree.selection()
        rcsid = self._tree.identify_row(event.y)
        if rcsid and not rcsid in sids:
            self._tree.selection_set(rcsid)
            sids = (rcsid,)

        # show a context menu with delete (disable if iid is active)
        if sids:
            mnu = tk.Menu(None,tearoff=0)
            mnu.add_command(label='Delete',command=lambda:self.mdkp(sids))

            if len(sids) == 1:
                # if this row has no stop, assume session is still active
                if self._tree.set(sids[0],'Stop') == '':
                    mnu.entryconfig(0,state=tk.DISABLED)
            mnu.tk_popup(event.x_root,event.y_root)

    def mdkp(self,sids):
        self.update()
        self.setbusy()
        self.dkp(sids)
        self.setbusy(False)

    def dkp(self,sids=None):
        """
         delete specified entry(s)
         :param sids: list of sids to delete
        """
        sql = "delete from sensor where session_id = %s;"
        if sids is None: sids = self._tree.selection()

        # wrap the entire process in the critical section
        i = 0
        self._l.acquire()
        try:
            for sid in sids:
                # ensure session is not active
                if self._tree.set(sid,'Stop') == '':
                    self.logwrite("Cannot delete active session {0}".format(sid),
                                  gui.LOG_WARN)
                    continue
                try:
                    self._curs.execute(sql,(int(sid),))
                    self._tree.delete(sid)
                    i += 1
                except psql.Error as e:
                    self.logwrite("Failed to delete session {0}: {1}".format(sid,e),
                                  gui.LOG_ERR)
                    self._conn.rollback()
                else:
                    self._conn.commit()
        except: pass
        finally:
            self._l.release()
        self.logwrite("Deleted {0} sessions".format(i),gui.LOG_NOTE)

    def _connect(self,connect):
        """ get and return a connection object """
        self._conn,err = cmdline.psqlconnect(connect)
        if not err:
            try:
                self._curs = self._conn.cursor(cursor_factory=pextras.DictCursor)
                self._curs.execute("SET TIME ZONE 'UTC';")
            except psql.Error as e:
                self.err("Query Error",e)
        else:
            self.err("Connect Error",err)

# Iyri->Control
CMD_STATUS = 0 # status of command
CMD_CID    = 1 # command id
CMD_RDO    = 2 # radio
CMD_MSG    = 3 # msg
def tokenize(ds):
    """
     tokenize: parses string C2C data into tokens and returns the token list
     :param ds: C2C data
     :returns: a list of token lists
    """
    ts = []
    ds = ds.split('\n')[:-1]
    for d in ds:
        newd = []    # list of parsed tokens
        token = ''   # individual token
        buff = False # buffer '\x01' has been seen

        # for each char in data string d
        d = d.strip() # remove the trailing newline
        for i in d:
            # if char is a buff, flip buff value
            # if char is a space and buff is true keep it
            # if char is a space and not buff, append the new token & make new
            # otherwise append the char to current token
            if i == '\x01':
                buff = False if buff else True
            elif i == ' ':
                if buff: token += i
                else:
                    newd.append(token)
                    token = ''
            else:
                token += i

        # append any 'hanging' tokens & enforce length of 4
        if token: newd.append(token)
        while len(newd) < 4: newd.append('')
        ts.append(newd)
    return ts

class _ParamDialog(tkSD.Dialog):
    """ _ParamDialog - (Modal) prompts user for command parameters """
    def __init__(self,parent,cmd):
        """
        :param parent: calling panel
        :param cmd: the command
        """
        self._cmd = cmd
        tkSD.Dialog.__init__(self,parent)
    def body(self,master):
        self.title('Enter Parameters')
        cmdtext = ""
        if self._cmd == 'listen': cmdtext = "ch:width "
        elif self._cmd == 'txpwr': cmdtext = "pwr:option "
        elif self._cmd == 'spoof': cmdtext = "HW Addr "
        ttk.Label(master,text=cmdtext).grid(row=0,column=0)
        # noinspection PyAttributeOutsideInit
        self._entParam = ttk.Entry(master)
        self._entParam.grid(row=0,column=1)
        return self._entParam
    def validate(self):
        if self._entParam.get() == '': return 0
        return 1
    def apply(self):
        param = self._entParam.get()
        err = ""
        if self._cmd == 'listen':
            # must be ch:chw
            try:
                if ':' in param:
                    (ch,chw) = param.split(':')
                    if not chw: chw = 'None'
                else:
                    ch = param
                    chw = 'None'
                ch = int(ch)
                if not (chw in radio.RDO_CHWS or chw == 'None'):
                    err = "Invalid channel width"
                elif not ch in channels.channels(): err = "Invalid channel"
                else: params = "{0}:{1}".format(ch,chw)
            except ValueError:
                err = "Channel must be an integer"
        elif self._cmd == 'txpwr':
            # must be pwr:option
            try:
                if ':' in param:
                    (pwr,opt) = param.split(':')
                    if not opt: opt = 'fixed'
                else:
                    pwr = param
                    opt = 'fixed'
                pwr = int(pwr)
                if not opt in ['fixed','auto','limit']: err = "Invalid power option"
                else: params = "{0}:{1}".format(pwr,opt)
            except ValueError:
                err = "Power must be an integer"
        elif self._cmd == 'spoof':
            # valid mac address (or random)
            if not (param == 'random' or valrep.validhwaddr(param)):
                err = "Invalid HW Address"
            else:
                params = param

        if err:
            tkMB.showerror("Invalid Parameters",err,parent=self)
        else:
            # noinspection PyAttributeOutsideInit
            self.params = params

class C2CPoller(threading.Thread):
    """
     C2CPoller polls receiving end of C2C socket for messages and returns
     to IyriCtrlPanel
    """
    def __init__(self,ev,rcb,ecb,sock,poll=0.25):
        """
        :param ev: poison event
        :param rcb: callback to return received data
        :param ecb: callback to return errors
        :param sock: socket to receive from
        :param poll: poll time
        """
        threading.Thread.__init__(self)
        self._stop = ev   # poison (isset = Quit)
        self._rcb = rcb   # message callback
        self._ecb = ecb   # error callback
        self._s = sock    # socket to recive from
        self._poll = poll # poll time

    def run(self):
        """ poll socket for messages """
        while True:
            if self._stop.is_set(): break
            try:
                try:
                    (rs,_,_) = select.select([self._s],[],[],self._poll)
                except select.error as e: # hide (4,'Interupted system call')
                    if e[0] == 4: continue
                    raise

                if self._s in rs:
                    msg = self._recvmsg()
                    if msg: self._rcb(msg)
            except RuntimeError:
                self._ecb("C2C server quit")
                break
            except Exception as e:
                self._ecb(e)

    def _recvmsg(self):
        """ :returns: read data from C2C """
        msg = ''
        while len(msg) == 0 or msg[-1:] != '\n':
            data = self._s.recv(256)
            if not data: raise RuntimeError
            msg += data
        return msg

class IyriCtrlPanel(gui.SimplePanel):
    """ Display Iyri Control Panel """
    def __init__(self,tl,chief,sock):
        self._cid = 1                    # current command id
        self._cmds = {}                  # dict of commands entered keyed of cid
        self._imgs = {}                  # store opened image for the buttons
        self._btns = {}                  # buttons
        self._rdos = {'abad':None,       # radio states
                      'shama':None}
        self._s = sock                   # the socket to C2C
        self._tC2C = None                # polling thread to for socket recv
        self._poison = threading.Event() # poison pill to thread
        gui.SimplePanel.__init__(self,tl,chief,"Iyri Control","widgets/icons/radio.png")

        # start the C2C listener
        self._tC2C = C2CPoller(self._poison,self.resultcb,self.errcb,self._s)
        self._tC2C.start()

        # getting occasional weird responses
        assert(self._s is not None) # during testing make sure we have a socket
        self._sensorstate()

    def _body(self):
        """ make the gui """
        # a simple notebook with two tabs
        nb = ttk.Notebook(self)
        nb.grid(row=0,column=0,columnspan=2,sticky='nwse')

        # Single - one command at a time button initiated
        frmV = ttk.Frame(nb)
        frmA = ttk.LabelFrame(frmV,text='Abad')
        frmA.grid(row=0,column=0,sticky='nwse')
        frmS = ttk.LabelFrame(frmV,text='Shama')
        frmS.grid(row=1,column=0,sticky='nwse')
        frmO = ttk.Frame(frmV)
        frmO.grid(row=2,column=0,sticky='n')

        try:
            # load button images
            self._imgs['scan'] = PhotoImage(imgopen('widgets/icons/iscan.png'))
            self._imgs['pause'] = PhotoImage(imgopen('widgets/icons/ipause.png'))
            self._imgs['hold'] = PhotoImage(imgopen('widgets/icons/ihold.png'))
            self._imgs['listen'] = PhotoImage(imgopen('widgets/icons/ilisten.png'))
            self._imgs['txpwr'] = PhotoImage(imgopen('widgets/icons/itxpwr.png'))
            self._imgs['spoof'] = PhotoImage(imgopen('widgets/icons/ispoof.png'))
            self._imgs['state'] = PhotoImage(imgopen('widgets/icons/istate.png'))

            # create buttons first for abad then shama
            self._btns['ascan'] = ttk.Button(frmA,image=self._imgs['scan'],command=lambda:self.runsingle('scan','abad'))
            self._btns['apause'] = ttk.Button(frmA,image=self._imgs['pause'],command=lambda:self.runsingle('pause','abad'))
            self._btns['ahold'] = ttk.Button(frmA,image=self._imgs['hold'],command=lambda:self.runsingle('hold','abad'))
            self._btns['alisten'] = ttk.Button(frmA,image=self._imgs['listen'],command=lambda:self.runsingle('listen','abad'))
            self._btns['atxpwr'] = ttk.Button(frmA,image=self._imgs['txpwr'],command=lambda:self.runsingle('txpwr','abad'))
            self._btns['aspoof'] = ttk.Button(frmA,image=self._imgs['spoof'],command=lambda:self.runsingle('spoof','abad'))
            self._btns['astate'] = ttk.Button(frmA,image=self._imgs['state'],command=lambda:self.runsingle('state','abad'))
            self._btns['sscan'] = ttk.Button(frmS,image=self._imgs['scan'],command=lambda:self.runsingle('scan','shama'))
            self._btns['spause'] = ttk.Button(frmS,image=self._imgs['pause'],command=lambda:self.runsingle('pause','shama'))
            self._btns['shold'] = ttk.Button(frmS,image=self._imgs['hold'],command=lambda:self.runsingle('hold','shama'))
            self._btns['slisten'] = ttk.Button(frmS,image=self._imgs['listen'],command=lambda:self.runsingle('listen','shama'))
            self._btns['stxpwr'] = ttk.Button(frmS,image=self._imgs['txpwr'],command=lambda:self.runsingle('txpwr','shama'))
            self._btns['sspoof'] = ttk.Button(frmS,image=self._imgs['spoof'],command=lambda:self.runsingle('spoof','shama'))
            self._btns['sstate'] = ttk.Button(frmS,image=self._imgs['state'],command=lambda:self.runsingle('state','shama'))
        except Exception as e:
            # images failed to load
            self._btns['ascan'] = ttk.Button(frmA,text='S',command=lambda:self.runsingle('scan','abad'))
            self._btns['apause'] = ttk.Button(frmA,text='P',command=lambda:self.runsingle('pause','abad'))
            self._btns['ahold'] = ttk.Button(frmA,text='H',command=lambda:self.runsingle('hold','abad'))
            self._btns['alisten'] = ttk.Button(frmA,text='L',command=lambda:self.runsingle('listenn','abad'))
            self._btns['atxpwr'] = ttk.Button(frmA,text='T',command=lambda:self.runsingle('txpwr','abad'))
            self._btns['aspoof'] = ttk.Button(frmA,text='Sp',command=lambda:self.runsingle('spoof','abad'))
            self._btns['astate'] = ttk.Button(frmA,text='St',command=lambda:self.runsingle('state','abad'))
            self._btns['sscan'] = ttk.Button(frmS,text='S',command=lambda:self.runsingle('scan','shama'))
            self._btns['spause'] = ttk.Button(frmS,text='P',command=lambda:self.runsingle('pause','shama'))
            self._btns['shold'] = ttk.Button(frmS,text='H',command=lambda:self.runsingle('hold','shama'))
            self._btns['slisten'] = ttk.Button(frmS,text='L',command=lambda:self.runsingle('listen','shama'))
            self._btns['stxpwr'] = ttk.Button(frmS,text='T',command=lambda:self.runsingle('txpwr','shama'))
            self._btns['sspoof'] = ttk.Button(frmS,text='Sp',command=lambda:self.runsingle('spoof','shama'))
            self._btns['sstate'] = ttk.Button(frmS,text='St',command=lambda:self.runsingle('state','shama'))
        finally:
            # place the buttons and output
            self._btns['ascan'].grid(row=0,column=0)
            self._btns['apause'].grid(row=0,column=1)
            self._btns['ahold'].grid(row=0,column=2)
            self._btns['alisten'].grid(row=0,column=3)
            self._btns['atxpwr'].grid(row=0,column=4)
            self._btns['aspoof'].grid(row=0,column=5)
            self._btns['astate'].grid(row=0,column=6)
            self._btns['sscan'].grid(row=1,column=0)
            self._btns['spause'].grid(row=1,column=1)
            self._btns['shold'].grid(row=1,column=2)
            self._btns['slisten'].grid(row=1,column=3)
            self._btns['stxpwr'].grid(row=1,column=4)
            self._btns['sspoof'].grid(row=1,column=5)
            self._btns['sstate'].grid(row=1,column=6)

        # output
        self._cmdout = tk.Entry(frmO,width=28)
        self._cmdout.grid(row=0,column=0,sticky='nwse')
        self._cmdout.configure(state=tk.DISABLED)

        nb.add(frmV,text="Single")

        # Multiple - can enter multiple commands to be executed in order
        frmC = ttk.Frame(nb)
        # input text and execute button
        self._cmdline = tk.Text(frmC,width=28,height=6)
        self._cmdline.grid(row=0,column=0,sticky='nw')
        try:
            self._imgs['run'] = PhotoImage(imgopen('widgets/icons/irun.png'))
            self._btnRun = ttk.Button(frmC,image=self._imgs['run'],command=self.unimplemented)
        except:
            self._btnRun = ttk.Button(frmC,width=1,text='!',command=self.unimplemented)
        finally:
            self._btnRun.grid(row=0,column=1,sticky='nw')
        nb.add(frmC,text="Multiple")

    def close(self):
        """ override close and close socket, quit thread before exiting """
        # kill the thread & close the socket
        self._poison.set()
        if self._tC2C: self._tC2C.join()
        gui.SimplePanel.close(self)

    def resultcb(self,msg):
        """
         callback to notify this control panel that C2C has returned data
         :param msg: return message from Iyri C2C
        """
        # get tokens, attempt to make cid int
        tkns = tokenize(msg)
        for tkn in tkns: self._results(tkn)

    def errcb(self,err):
        """
         callback to notify this control panel that C2C has an error
         :param err: return message from Iyri C2C
        """
        self.logwrite(err,gui.LOG_WARN)

    def runsingle(self,cmd,rdo,ps=None):
        """
         execute a single command
         :param cmd: command to run
         :param rdo: radio to run command on
         :param ps: params (if any)
        """
        ps = ''
        if cmd in ['listen','txpwr','spoof']:
            dlg = _ParamDialog(self,cmd)
            try:
                ps = " " + dlg.params
            except AttributeError:
                return
        msg = "!{0} {1} {2}{3}\n".format(self._cid,cmd,rdo,ps)
        self._cmds[self._cid] = (cmd,rdo,ps)
        self._cid += 1
        try:
            self._s.send(msg)
        except socket.error as e:
            self.logwrite("Control Panel: {0}".format(e),gui.LOG_WARN)

    def runmultiple(self):
        """ executes multiple commands (from command line widget) """
        # pullout indiviudal cmds
        cmds = []
        lines = self._cmdline.get('1.0','end')
        lines = lines.split('\n')
        for line in lines:
            if not line: break
            line = line.split(' ')
            if len(line) < 2: continue
            elif len(line) == 2: ps = ''
            elif len(line) == 3: ps = " " + line[2]
            else: continue
            msg = "!{0} {1} {2}{3}\n".format(self._cid,line[0],line[1],ps)
            cmds.append(msg)
            self._cmds[self._cid] = msg
            self._cid += 1
        self._cmdline.delete('1.0','end')

        # & execute
        for cmd in cmds:
            try:
                self._s.send(cmd)
            except socket.error as e:
                self.logwrite("Control Panel: {0}".format(e),gui.LOG_WARN)

    def _results(self,tkns):
        """
         process results from Iyri C2C
         :param tkns: tokenized response from C2C
        """
        try:
            cid = int(tkns[CMD_CID])
        except:
            # this is a hack. For whatever reason, some (initial) state requests
            # are formatted wrong on send or recieve (cannot figure out where)
            # if we get one of those, try and resubmit the initial sensor request
            self._sensorstate()
            return

        if cid == -1: # -1 cid denotes initial connect vesion message
            return
        elif cid == 0: # 0 cid denotes a startup state request
            #['ERR', '0', 'shama', 'radio not present']
            #['OK', '0', 'abad', 'pause ch 1:None txpwr 30']
            # TODO: use state returns to enable/disable buttons on radio(s)
            # that are present
            if tkns[CMD_RDO] == 'shama': pre = 's'
            elif tkns[CMD_RDO] == 'abad': pre = 'a'
            if tkns[CMD_STATUS] == 'ERR':
                for btn in self._btns:
                    if btn.startswith(pre):
                        self._btns[btn].configure(state=tk.DISABLED)
            else:
                for btn in self._btns:
                    if btn.startswith(pre):
                        self._btns[btn].configure(state=tk.NORMAL)
            return

        # process normally
        if cid in self._cmds:
            # get the originating cmd & delete from history
            (cmd,rdo,ps) = self._cmds[cid]
            del self._cmds[cid]

            # write results
            out = ""
            if len(tkns[CMD_MSG]) > 25: out = tkns[CMD_MSG][:10] + "..."
            else: out = tkns[CMD_MSG]
            self._cmdout.configure(state=tk.NORMAL)
            self._cmdout.delete(0,tk.END)
            self._cmdout.insert(0,"{0}: {1}".format(tkns[CMD_STATUS],out))
            self._cmdout.configure(state=tk.DISABLED)
        else:
            self.warn("Unknown Command","{0} {1} {2} {3}".format(tkns[0],tkns[1],tkns[2],tkns[3]))

    def _sensorstate(self):
        """ send state requests to C2C """
        try:
            # get current states
            self._s.send("!0 state abad\n")
            self._s.send("!0 state shama\n")
        except socket.error as e:
            self.logwrite("Iyri socket failed: {0}".format(e),gui.LOG_ERR)
            self._s = None

# Iyri->Config
class IyriConfigException(Exception): pass
class IyriConfigPanel(gui.ConfigPanel):
    """ Display Nidus Configuration Panel """
    def __init__(self,tl,chief):
        gui.ConfigPanel.__init__(self,tl,chief,"Configure Iyri")

    def _makegui(self,frm):
        """ set up entry widgets """
        nb = ttk.Notebook(frm)
        nb.grid(row=0,column=0,sticky='nwse')

        # Abad Tab Configuration
        frmA = ttk.Frame(nb)
        ttk.Label(frmA,text='NIC: ').grid(row=0,column=0,sticky='nw')
        self._entAbadNic = ttk.Entry(frmA,width=5)
        self._entAbadNic.grid(row=0,column=1,sticky='nw')
        ttk.Label(frmA,text=' ').grid(row=0,column=2,sticky='w')
        ttk.Label(frmA,text='Spoof: ').grid(row=0,column=3,sticky='nw')
        self._entAbadSpoof = ttk.Entry(frmA,width=17)
        self._entAbadSpoof.grid(row=0,column=4,sticky='nw')
        ttk.Label(frmA,text='Desc: ').grid(row=1,column=0,sticky='nw')
        self._entAbadDesc = tk.Text(frmA,width=42,height=3)
        self._entAbadDesc.grid(row=1,column=1,columnspan=4,sticky='e')

        # ANTENNA SUB SECTION
        frmAA = ttk.LabelFrame(frmA,text='Antennas')
        frmAA.grid(row=2,column=0,columnspan=5,sticky='nwse')
        # ANTENNA SUBSECTION
        ttk.Label(frmAA,text="Number: ").grid(row=0,column=0,sticky='w')
        self._entAbadAntNum = ttk.Entry(frmAA,width=2)
        self._entAbadAntNum.grid(row=0,column=1,sticky='w')
        ttk.Label(frmAA,text='Gain: ').grid(row=1,column=0,sticky='w')
        self._entAbadAntGain = ttk.Entry(frmAA,width=7)
        self._entAbadAntGain.grid(row=1,column=1,sticky='w')
        ttk.Label(frmAA,text=" ").grid(row=1,column=2)
        ttk.Label(frmAA,text="Type: ").grid(row=1,column=3,sticky='e')
        self._entAbadAntType = ttk.Entry(frmAA,width=15)
        self._entAbadAntType.grid(row=1,column=4,sticky='e')
        ttk.Label(frmAA,text='Loss: ').grid(row=2,column=0,sticky='w')
        self._entAbadAntLoss = ttk.Entry(frmAA,width=7)
        self._entAbadAntLoss.grid(row=2,column=1,sticky='w')
        ttk.Label(frmAA,text=" ").grid(row=2,column=2)
        ttk.Label(frmAA,text="XYZ: ").grid(row=2,column=3,sticky='e')
        self._entAbadAntXYZ = ttk.Entry(frmAA,width=15)
        self._entAbadAntXYZ.grid(row=2,column=4,sticky='e')
        # SCAN PATTERN SUB SECTION
        frmAS = ttk.LabelFrame(frmA,text='Scan')
        frmAS.grid(row=3,column=0,columnspan=5,sticky='nwse')
        ttk.Label(frmAS,text="Dwell: ").grid(row=0,column=0,sticky='w')
        self._entAbadScanDwell = ttk.Entry(frmAS,width=5)
        self._entAbadScanDwell.grid(row=0,column=2,sticky='w')
        ttk.Label(frmAS,text=" ").grid(row=0,column=3)
        ttk.Label(frmAS,text="Start: ").grid(row=0,column=4,sticky='e')
        self._entAbadScanStart = ttk.Entry(frmAS,width=3)
        self._entAbadScanStart.grid(row=0,column=5,sticky='w')
        ttk.Label(frmAS,text="Scan: ").grid(row=1,column=0,sticky='w')
        self._entAbadScanScan = ttk.Entry(frmAS,width=12)
        self._entAbadScanScan.grid(row=1,column=2,sticky='w')
        ttk.Label(frmAS,text=" ").grid(row=1,column=3)
        ttk.Label(frmAS,text="Pass: ").grid(row=1,column=4,sticky='w')
        self._entAbadScanPass = ttk.Entry(frmAS,width=12)
        self._entAbadScanPass.grid(row=1,column=5,sticky='e')
        self._vapause = tk.IntVar()
        ttk.Checkbutton(frmAS,text="Paused",variable=self._vapause).grid(row=2,column=0)
        nb.add(frmA,text='Abad')

        # Shama Tab Configuration
        frmC = ttk.Frame(nb)
        ttk.Label(frmC,text='NIC: ').grid(row=0,column=0,sticky='nw')
        self._entShamaNic = ttk.Entry(frmC,width=5)
        self._entShamaNic.grid(row=0,column=1,sticky='nw')
        ttk.Label(frmC,text=' ').grid(row=0,column=2,sticky='w')
        ttk.Label(frmC,text='Spoof: ').grid(row=0,column=3,sticky='wn')
        self._entShamaSpoof = ttk.Entry(frmC,width=17)
        self._entShamaSpoof.grid(row=0,column=4,sticky='nw')
        ttk.Label(frmC,text='Desc: ').grid(row=1,column=0,sticky='nw')
        self._entShamaDesc = tk.Text(frmC,width=42,height=3)
        self._entShamaDesc.grid(row=1,column=1,columnspan=4,sticky='e')

        # ANTENNA SUB SECTION
        frmCA = ttk.LabelFrame(frmC,text='Antennas')
        frmCA.grid(row=2,column=0,columnspan=5,sticky='nwse')
        # ANTENNA SUBSECTION
        ttk.Label(frmCA,text="Number: ").grid(row=0,column=0,sticky='w')
        self._entShamaAntNum = ttk.Entry(frmCA,width=2)
        self._entShamaAntNum.grid(row=0,column=1,sticky='w')
        ttk.Label(frmCA,text='Gain: ').grid(row=1,column=0,sticky='w')
        self._entShamaAntGain = ttk.Entry(frmCA,width=7)
        self._entShamaAntGain.grid(row=1,column=1,sticky='w')
        ttk.Label(frmCA,text=" ").grid(row=1,column=2)
        ttk.Label(frmCA,text="Type: ").grid(row=1,column=3,sticky='e')
        self._entShamaAntType = ttk.Entry(frmCA,width=15)
        self._entShamaAntType.grid(row=1,column=4,sticky='e')
        ttk.Label(frmCA,text='Loss: ').grid(row=2,column=0,sticky='w')
        self._entShamaAntLoss = ttk.Entry(frmCA,width=7)
        self._entShamaAntLoss.grid(row=2,column=1,sticky='w')
        ttk.Label(frmCA,text=" ").grid(row=2,column=2)
        ttk.Label(frmCA,text="XYZ: ").grid(row=2,column=3,sticky='e')
        self._entShamaAntXYZ = ttk.Entry(frmCA,width=15)
        self._entShamaAntXYZ.grid(row=2,column=4,sticky='e')
        # SCAN PATTERN SUB SECTION
        frmCS = ttk.LabelFrame(frmC,text='Scan Pattern')
        frmCS.grid(row=3,column=0,columnspan=5,sticky='nwse')
        ttk.Label(frmCS,text="Dwell: ").grid(row=0,column=0,sticky='w')
        self._entShamaScanDwell = ttk.Entry(frmCS,width=5)
        self._entShamaScanDwell.grid(row=0,column=2,sticky='w')
        ttk.Label(frmCS,text=" ").grid(row=0,column=3)
        ttk.Label(frmCS,text="Start: ").grid(row=0,column=4,sticky='e')
        self._entShamaScanStart = ttk.Entry(frmCS,width=3)
        self._entShamaScanStart.grid(row=0,column=5,sticky='w')
        ttk.Label(frmCS,text="Scan: ").grid(row=1,column=0,sticky='w')
        self._entShamaScanScan = ttk.Entry(frmCS,width=12)
        self._entShamaScanScan.grid(row=1,column=2,sticky='w')
        ttk.Label(frmCS,text=" ").grid(row=1,column=3)
        ttk.Label(frmCS,text="Pass: ").grid(row=1,column=4,sticky='w')
        self._entShamaScanPass = ttk.Entry(frmCS,width=12)
        self._entShamaScanPass.grid(row=1,column=5,sticky='e')
        self._vspause = tk.IntVar()
        ttk.Checkbutton(frmCS,text="Paused",variable=self._vspause).grid(row=2,column=0)
        nb.add(frmC,text='Shama')

        # GPS Tab Configuration
        # use a checkbutton & two subframes to differentiate betw/ fixed & dyanmic
        frmG = ttk.Frame(nb)
        self.vfixed = tk.IntVar()
        ttk.Checkbutton(frmG,text="Fixed",variable=self.vfixed,command=self.gpscb).grid(row=0,column=0,sticky='w')

        # separate dynamic and fixed
        frmGF = ttk.LabelFrame(frmG,text='Fixed')
        frmGF.grid(row=1,column=0,sticky='nw')
        ttk.Label(frmGF,text="Lat: ").grid(row=0,column=0,sticky='w')
        self._entLat = ttk.Entry(frmGF,width=10)
        self._entLat.grid(row=0,column=1,sticky='w')
        ttk.Label(frmGF,text="Lon: ").grid(row=1,column=0,sticky='w')
        self._entLon = ttk.Entry(frmGF,width=10)
        self._entLon.grid(row=1,column=1,sticky='w')
        ttk.Label(frmGF,text="Alt: ").grid(row=2,column=0,sticky='w')
        self._entAlt = ttk.Entry(frmGF,width=5)
        self._entAlt.grid(row=2,column=1,sticky='w')
        ttk.Label(frmGF,text="Heading: ").grid(row=3,column=0,sticky='w')
        self._entHeading = ttk.Entry(frmGF,width=3)
        self._entHeading.grid(row=3,column=1,sticky='w')
        frmGD = ttk.LabelFrame(frmG,text='Dynamic')
        frmGD.grid(row=1,column=2,sticky='ne')
        ttk.Label(frmGD,text="Port: ").grid(row=0,column=0,sticky='w')
        self._entGPSPort = ttk.Entry(frmGD,width=5)
        self._entGPSPort.grid(row=0,column=1,sticky='w')
        ttk.Label(frmGD,text="Dev ID: ").grid(row=1,column=0,sticky='w')
        self._entDevID = ttk.Entry(frmGD,width=9)
        self._entDevID.grid(row=1,column=1,sticky='w')
        ttk.Label(frmGD,text="Poll: ").grid(row=2,column=0,sticky='w')
        self._entPoll = ttk.Entry(frmGD,width=5)
        self._entPoll.grid(row=2,column=1,sticky='w')
        ttk.Label(frmGD,text="EPX: ").grid(row=3,column=0,sticky='w')
        self._entEPX = ttk.Entry(frmGD,width=5)
        self._entEPX.grid(row=3,column=1,sticky='w')
        ttk.Label(frmGD,text="EPY: ").grid(row=4,column=0,sticky='w')
        self._entEPY = ttk.Entry(frmGD,width=5)
        self._entEPY.grid(row=4,column=1,sticky='w')
        nb.add(frmG,text='GPS')

        # misc tab
        # storage
        frmM = ttk.Frame(nb)
        frmMS = ttk.LabelFrame(frmM,text='Storage')
        frmMS.grid(row=0,column=0,sticky='w')
        ttk.Label(frmMS,text='Host: ').grid(row=0,column=0)
        self._entStoreHost = ttk.Entry(frmMS,width=15)
        self._entStoreHost.grid(row=0,column=1)
        ttk.Label(frmMS,text=' Port: ').grid(row=0,column=2)
        self._entStorePort = ttk.Entry(frmMS,width=5)
        self._entStorePort.grid(row=0,column=3)
        ttk.Label(frmMS,text='DB: ').grid(row=1,column=0,sticky='w')
        self._entStoreDB = ttk.Entry(frmMS,width=10)
        self._entStoreDB.grid(row=1,column=1,sticky='w')
        ttk.Label(frmMS,text='User: ').grid(row=2,column=0,sticky='w')
        self._entStoreUSR = ttk.Entry(frmMS,width=10)
        self._entStoreUSR.grid(row=2,column=1,sticky='w')
        ttk.Label(frmMS,text='PWD: ').grid(row=3,column=0,sticky='w')
        self._entStorePWD = ttk.Entry(frmMS,width=10)
        self._entStorePWD.grid(row=3,column=1,sticky='w')
        # local
        frmML = ttk.LabelFrame(frmM,text='Local')
        frmML.grid(row=1,column=0,sticky='w')
        ttk.Label(frmML,text="Region: ").grid(row=0,column=0,sticky='w')
        self._entRegion = ttk.Entry(frmML,width=3)
        self._entRegion.grid(row=0,column=1,sticky='w')
        ttk.Label(frmML,text=" C2C: ").grid(row=0,column=2,sticky='w')
        self._entC2CPort = ttk.Entry(frmML,width=5)
        self._entC2CPort.grid(row=0,column=3,sticky='w')
        ttk.Label(frmML,text=" Max Threshers: ").grid(row=0,column=4,sticky='w')
        self._entMaxT = ttk.Entry(frmML,width=5)
        self._entMaxT.grid(row=0,column=5,sticky='w')
        nb.add(frmM,text='Misc.')

    def _initialize(self):
        """ insert values from config file into entry boxes """
        cp = ConfigParser.RawConfigParser()
        if not cp.read(wraith.IYRICONF):
            self.err("File Not Found","File iyri.conf was not found")
            return

        # start by reading the recon radio details
        self._entAbadNic.delete(0,tk.END)
        if cp.has_option('Abad','nic'):
            self._entAbadNic.insert(0,cp.get('Abad','nic'))
        self._entAbadSpoof.delete(0,tk.END)
        if cp.has_option('Abad','spoof'):
            self._entAbadSpoof.insert(0,cp.get('Abad','spoof'))
        self._entAbadDesc.delete(1.0,tk.END)
        if cp.has_option('Abad','desc'):
            self._entAbadDesc.insert(tk.END,cp.get('Abad','desc'))
        self._entAbadAntNum.delete(0,tk.END)
        if cp.has_option('Abad','antennas'):
            self._entAbadAntNum.insert(0,cp.get('Abad','antennas'))
        self._entAbadAntGain.delete(0,tk.END)
        if cp.has_option('Abad','antenna_gain'):
            self._entAbadAntGain.insert(0,cp.get('Abad','antenna_gain'))
        self._entAbadAntType.delete(0,tk.END)
        if cp.has_option('Abad','antenna_type'):
            self._entAbadAntType.insert(0,cp.get('Abad','antenna_type'))
        self._entAbadAntLoss.delete(0,tk.END)
        if cp.has_option('Abad','antenna_loss'):
            self._entAbadAntLoss.insert(0,cp.get('Abad','antenna_loss'))
        self._entAbadAntXYZ.delete(0,tk.END)
        if cp.has_option('Abad','antenna_xyz'):
            self._entAbadAntXYZ.insert(0,cp.get('Abad','antenna_xyz'))
        self._entAbadScanDwell.delete(0,tk.END)
        if cp.has_option('Abad','dwell'):
            self._entAbadScanDwell.insert(0,cp.get('Abad','dwell'))
        self._entAbadScanStart.delete(0,tk.END)
        if cp.has_option('Abad','scan_start'):
            self._entAbadScanStart.insert(0,cp.get('Abad','scan_start'))
        self._entAbadScanScan.delete(0,tk.END)
        if cp.has_option('Abad','scan'):
            self._entAbadScanScan.insert(0,cp.get('Abad','scan'))
        self._entAbadScanPass.delete(0,tk.END)
        if cp.has_option('Abad','pass'):
            self._entAbadScanPass.insert(0,cp.get('Abad','pass'))
        self._vapause.set(0)
        if cp.has_option('Abad','paused'):
            if cp.getboolean('Abad','paused'): self._vapause.set(1)

        # then the shama radio details
        self._entShamaNic.delete(0,tk.END)
        if cp.has_option('Shama','nic'):
            self._entShamaNic.insert(0,cp.get('Shama','nic'))
        self._entShamaSpoof.delete(0,tk.END)
        if cp.has_option('Shama','spoof'):
            self._entShamaSpoof.insert(0,cp.get('Shama','spoof'))
        self._entShamaDesc.delete(1.0,tk.END)
        if cp.has_option('Shama','desc'):
            self._entShamaDesc.insert(tk.END,cp.get('Shama','desc'))
        self._entShamaAntNum.delete(0,tk.END)
        if cp.has_option('Shama','antennas'):
            self._entShamaAntNum.insert(0,cp.get('Shama','antennas'))
        self._entShamaAntGain.delete(0,tk.END)
        if cp.has_option('Shama','antenna_gain'):
            self._entShamaAntGain.insert(0,cp.get('Shama','antenna_gain'))
        self._entShamaAntType.delete(0,tk.END)
        if cp.has_option('Shama','antenna_type'):
            self._entShamaAntType.insert(0,cp.get('Shama','antenna_type'))
        self._entShamaAntLoss.delete(0,tk.END)
        if cp.has_option('Shama','antenna_loss'):
            self._entShamaAntLoss.insert(0,cp.get('Shama','antenna_loss'))
        self._entShamaAntXYZ.delete(0,tk.END)
        if cp.has_option('Shama','antenna_xyz'):
            self._entShamaAntXYZ.insert(0,cp.get('Shama','antenna_xyz'))
        self._entShamaScanDwell.delete(0,tk.END)
        if cp.has_option('Shama','dwell'):
            self._entShamaScanDwell.insert(0,cp.get('Shama','dwell'))
        self._entShamaScanStart.delete(0,tk.END)
        if cp.has_option('Shama','scan_start'):
            self._entShamaScanStart.insert(0,cp.get('Shama','scan_start'))
        self._entShamaScanScan.delete(0,tk.END)
        if cp.has_option('Shama','scan'):
            self._entShamaScanScan.insert(0,cp.get('Shama','scan'))
        self._entShamaScanPass.delete(0,tk.END)
        if cp.has_option('Shama','pass'):
            self._entShamaScanPass.insert(0,cp.get('Shama','pass'))
        self._vspause.set(0)
        if cp.has_option('Shama','paused'):
            if cp.getboolean('Shama','paused'): self._vspause.set(1)

        # gps entries
        try:
            fixed = int(cp.getboolean('GPS','fixed'))
        except:
            fixed = 0
        self.vfixed.set(fixed)
        self._entLat.delete(0,tk.END)
        if cp.has_option('GPS','lat'): self._entLat.insert(0,cp.get('GPS','lat'))
        self._entLon.delete(0,tk.END)
        if cp.has_option('GPS','lon'): self._entLon.insert(0,cp.get('GPS','lon'))
        self._entAlt.delete(0,tk.END)
        if cp.has_option('GPS','alt'): self._entAlt.insert(0,cp.get('GPS','alt'))
        self._entHeading.delete(0,tk.END)
        if cp.has_option('GPS','heading'): self._entHeading.insert(0,cp.get('GPS','heading'))
        self._entGPSPort.delete(0,tk.END)
        if cp.has_option('GPS','port'): self._entGPSPort.insert(0,cp.get('GPS','port'))
        self._entDevID.delete(0,tk.END)
        if cp.has_option('GPS','devid'): self._entDevID.insert(0,cp.get('GPS','devid'))
        self._entPoll.delete(0,tk.END)
        if cp.has_option('GPS','poll'): self._entPoll.insert(0,cp.get('GPS','poll'))
        self._entEPX.delete(0,tk.END)
        if cp.has_option('GPS','epx'): self._entEPX.insert(0,cp.get('GPS','epx'))
        self._entEPY.delete(0,tk.END)
        if cp.has_option('GPS','epy'): self._entEPY.insert(0,cp.get('GPS','epy'))
        self.gpscb() # enable/disable entries

        # misc entries
        self._entStoreHost.delete(0,tk.END)
        if cp.has_option('Storage','host'): self._entStoreHost.insert(0,cp.get('Storage','host'))
        self._entStorePort.delete(0,tk.END)
        if cp.has_option('Storage','port'): self._entStorePort.insert(0,cp.get('Storage','port'))
        self._entRegion.delete(0,tk.END)
        if cp.has_option('Local','region'): self._entRegion.insert(0,cp.get('Local','region'))
        self._entC2CPort.delete(0,tk.END)
        if cp.has_option('Local','C2C'): self._entC2CPort.insert(0,cp.get('Local','C2C'))
        self._entMaxT.delete(0,tk.END)
        if cp.has_option('Local','maxt'):
            try:
                self._entMaxT.insert(0,cp.getint('Local','maxt'))
            except:
                pass

    def _validate(self):
        """ validate entries """
        # start with the recon radio details
        nic = self._entAbadNic.get()
        if not nic:
            self.err("Invalid Abad Input","Radio nic must be specified")
            return False
        elif not nic in radio.winterfaces():
            self.warn("Not Found","Abad radio may not be wireless")
        spoof = self._entAbadSpoof.get().upper()
        if spoof and not valrep.validhwaddr(spoof):
            self.err("Invalid Abad Input","Spoofed MAC addr %s is not valid")
            return False

        # process antennas, if # > 0 then force validation of all antenna widgets
        if self._entAbadAntNum.get():
            try:
                nA = int(self._entAbadAntNum.get())
                if nA:
                    try:
                        if len(map(float,self._entAbadAntGain.get().split(','))) != nA:
                            raise IyriConfigException("Number of gain is invalid")
                    except ValueError:
                        raise IyriConfigException("Gain must be float or list of floats")
                    if len(self._entAbadAntType.get().split(',')) != nA:
                        raise IyriConfigException("Number of types is invalid")
                    try:
                        if len(map(float,self._entAbadAntLoss.get().split(','))) != nA:
                            raise IyriConfigException("Number of loss is invalid")
                    except:
                        raise IyriConfigException("Loss must be float or list of floats")
                    try:
                        xyzs = self._entAbadAntXYZ.get().split(',')
                        if len(xyzs) != nA:
                            raise IyriConfigException("Number of xyz is invalid")
                        for xyz in xyzs:
                            xyz = xyz.split(':')
                            if len(xyz) != 3:
                                raise IyriConfigException("XYZ must be three integers")
                            map(int,xyz)
                    except ValueError:
                        raise IyriConfigException('XYZ must be integer')
            except ValueError:
                self.err("Invalid Abad Input","Number of antennas must be numeric")
                return False
            except IyriConfigException as e:
                self.err("Invalid Abad Input",e)
                return False

        # process scan patterns
        try:
            float(self._entAbadScanDwell.get())
        except:
            self.err("Invalid Abad Input","Scan dwell must be float")
            return False
        start = self._entAbadScanStart.get()
        try:
            if start:
                if ':' in start: ch,chw = start.split(':')
                else:
                    ch = start
                    chw = None
                ch = int(ch)
                if chw and not chw in radio.RDO_CHWS:
                    raise RuntimeError("Specified channel width is not valid")
        except ValueError:
            self.err("Invalid Abad Input","Scan start must be integer")
            return False
        except Exception as e:
            self.err("Invalid Abad Input",e)
            return False
        try:
            valrep.channellist(self._entAbadScanScan.get(),'scan')
            valrep.channellist(self._entAbadScanPass.get(),'pass')
        except ValueError as e:
            self.err("Invalid Abad Input",e)
            return False

        # then shama radio details
        nic = self._entShamaNic.get()
        if nic:
            if not nic in radio.winterfaces():
                self.warn("Not Found","Radio may not be wireless")
            spoof = self._entShamaSpoof.get().upper()
            if spoof and not valrep.validhwaddr(spoof):
                self.err("Invalid Shama Input","Spoofed MAC address is not valid")
                return False

            # process the antennas - if antenna number is > 0 then force validation of
            # all antenna widgets
            if self._entShamaAntNum.get():
                try:
                    nA = int(self._entShamaAntNum.get())
                    if nA:
                        try:
                            if len(map(float,self._entShamaAntGain.get().split(','))) != nA:
                                raise IyriConfigException("Number of gain is invalid")
                        except ValueError:
                            raise IyriConfigException("Gain must be float or list of floats")
                        if len(self._entShamaAntType.get().split(',')) != nA:
                            raise IyriConfigException("Number of types is invalid")
                        try:
                            if len(map(float,self._entShamaAntLoss.get().split(','))) != nA:
                                raise IyriConfigException("Number of loss is invalid")
                        except:
                            raise IyriConfigException("Loss must be float or list of floats")
                        try:
                            xyzs = self._entShamaAntXYZ.get().split(',')
                            if len(xyzs) != nA:
                                raise IyriConfigException("Number of xyz is invalid")
                            for xyz in xyzs:
                                xyz = xyz.split(':')
                                if len(xyz) != 3:
                                    raise IyriConfigException("XYZ must be three integers")
                                map(int,xyz)
                        except ValueError:
                            raise IyriConfigException("XYZ must be integer")
                except ValueError:
                    self.err("Invalid Shama Input","Number of antennas must be numeric")
                    return False
                except IyriConfigException as e:
                    self.err("Invalid Shama Input",e)
                    return False

            # process scan patterns
            try:
                float(self._entShamaScanDwell.get())
            except:
                self.err("Invalid Shama Input", "Scan dwell must be float")
                return False
            start = self._entShamaScanStart.get()
            try:
                if start:
                    if ':' in start: ch,chw = start.split(':')
                    else:
                        ch = start
                        chw = None
                    ch = int(ch)
                    if chw and not chw in radio.RDO_CHWS:
                        raise RuntimeError("Specified channel width is not valid")
            except ValueError:
                self.err("Invalid Shama Input", "Scan start must be integer")
                return False
            except Exception as e:
                self.err("Invalid Shama Input",e)
                return False
            try:
                valrep.channellist(self._entShamaScanScan.get(),'scan')
                valrep.channellist(self._entShamaScanPass.get(),'pass')
            except ValueError as e:
                self.err("Invalid Shama Input",e)
                return False

        # gps - only process enabled widgets
        if self.vfixed.get():
            # fixed is set
            try:
                float(self._entLat.get())
                float(self._entLon.get())
            except:
                self.err("Invalid GPS Input","Lat/Lon must be floats")
                return False
            try:
                float(self._entAlt.get())
            except:
                self.err("Invalid GPS Input","Altitude must be a float")
                return False
            hdg = self._entHeading.get()
            try:
                hdg = int(hdg)
                if hdg < 0 or hdg > 360: raise RuntimeError("")
            except:
                self.err("Invalid GPS Input","Heading must be an integer between 0 and 360")
                return False
        else:
            # dynamic is set
            port = self._entGPSPort.get()
            try:
                port = int(port)
                if port < 1024 or port > 65535: raise RuntimeError("")
            except:
                self.err("Invalid GPS Input","Device port must be a number between 1024 and 65535")
                return False
            if not valrep.validgpsdid(self._entDevID.get().upper()):
                self.err("Invalid GPS Input","GPS Dev ID is invalid")
                return False
            try:
                if float(self._entPoll.get()) < 0: raise RuntimeError("")
            except:
                self.err("Invalid GPS Input","Poll must be numeric and greater than 0")
                return False
            try:
                float(self._entEPX.get())
                float(self._entEPY.get())
            except:
                self.err("Invalid GPS Input","EPX/EPY must be numeric or 'inf'")
                return False

        # misc entries
        # begin with storage related
        if not valrep.validaddr(self._entStoreHost.get()):
            self.err("Invalid Storage Input","Host is not a valid address")
        try:
            port = int(self._entStorePort.get())
            if port < 1024 or port > 65535: raise ValueError("see below")
        except ValueError:
            self.err("Invalid Storage Input","Host Port must be a number between 1024 and 65535")
            return False
        if not self._entStoreDB.get():
            self.err("Invalid Storage Input","DB must be entered")
            return False
        if not self._entStoreUSR.get():
            self.err("Invalid Storage Input","User must be entered")
            return False
        if not self._entStorePWD.get():
            self.err("Invalid Storage Input","Passwored must be entered")
            return False
        # then local related
        region = self._entRegion.get()
        if region and len(region) != 2:
            self.err("Invalid Local Input","Region must be 2 characters")
            return False
        try:
            port = self._entC2CPort.get()
            if port:
                port = int(port)
                if port < 1024 or port > 65535: raise ValueError("see below")
        except ValueError:
            self.err("Invalid Local Input","C2C Port must be a number between 1024 and 65535")
            return False
        # NOTE: no validating done on oui path
        try:
            mx = self._entMaxT.get()
            if mx: mx = int()
        except ValueError:
            self.err("Invalid Local Input","If present, MaxT must be an integer")
            return False

        return True

    def _write(self):
        """ write entry inputs to config file """
        fout = None
        try:
            cp = ConfigParser.ConfigParser()
            cp.add_section('Abad')
            cp.set('Abad','nic',self._entAbadNic.get())
            cp.set('Abad','paused','on' if self._vapause.get() else 'off')
            if self._entAbadSpoof.get(): cp.set('Abad','spoof',self._entAbadSpoof.get())

            nA = self._entAbadAntNum.get()
            if nA:
                cp.set('Abad','antennas',self._entAbadAntNum.get())
                cp.set('Abad','antenna_gain',self._entAbadAntGain.get())
                cp.set('Abad','antenna_loss',self._entAbadAntLoss.get())
                cp.set('Abad','antenna_type',self._entAbadAntType.get())
                cp.set('Abad','antenna_xyz',self._entAbadAntXYZ.get())
            desc = self._entAbadDesc.get(1.0,tk.END).strip()
            if desc: cp.set('Abad','desc',desc)
            cp.set('Abad','dwell',self._entAbadScanDwell.get())
            cp.set('Abad','scan',self._entAbadScanScan.get())
            cp.set('Abad','pass',self._entAbadScanPass.get())
            cp.set('Abad','scan_start',self._entAbadScanStart.get())
            if self._entShamaNic.get():
                cp.add_section('Shama')
                cp.set('Shama','nic',self._entShamaNic.get())
                cp.set('Shama','paused','on' if self._vspause.get() else 'off')
                if self._entShamaSpoof.get():
                    cp.set('Shama','spoof',self._entShamaSpoof.get())
                nA = self._entShamaAntNum.get()
                if nA:
                    cp.set('Shama','antennas',self._entShamaAntNum.get())
                    cp.set('Shama','antenna_gain',self._entShamaAntGain.get())
                    cp.set('Shama','antenna_loss',self._entShamaAntLoss.get())
                    cp.set('Shama','antenna_type',self._entShamaAntType.get())
                    cp.set('Shama','antenna_xyz',self._entShamaAntXYZ.get())
                desc = self._entShamaDesc.get(1.0,tk.END).strip()
                if desc: cp.set('Shama','desc',desc)
                cp.set('Shama','dwell',self._entShamaScanDwell.get())
                cp.set('Shama','scan',self._entShamaScanScan.get())
                cp.set('Shama','pass',self._entShamaScanPass.get())
                cp.set('Shama','scan_start',self._entShamaScanStart.get())
            cp.add_section('GPS')
            fixed = self.vfixed.get()
            cp.set('GPS','fixed','yes' if fixed else 'no')
            if fixed:
                cp.set('GPS','lat',self._entLat.get())
                cp.set('GPS','lon',self._entLon.get())
                cp.set('GPS','alt',self._entAlt.get())
                cp.set('GPS','heading',self._entHeading.get())
            else:
                cp.set('GPS','port',self._entGPSPort.get())
                cp.set('GPS','devid',self._entDevID.get())
                cp.set('GPS','poll',self._entPoll.get())
                cp.set('GPS','epx',self._entEPX.get())
                cp.set('GPS','epy',self._entEPY.get())
            cp.add_section('Storage')
            cp.set('Storage','host',self._entStoreHost.get())
            cp.set('Storage','port',self._entStorePort.get())
            cp.set('Storage','db',self._entStoreDB.get())
            cp.set('Storage','user',self._entStoreUSR.get())
            cp.set('Storage','pwd',self._entStorePWD.get())
            region = self._entRegion.get()
            c2cport = self._entC2CPort.get()
            maxt = self._entMaxT.get()
            if region or c2cport or maxt:
                cp.add_section('Local')
                if region: cp.set('Local','region',region)
                if c2cport: cp.set('Local','C2C',c2cport)
                if maxt: cp.set('Local','maxt',maxt)
            fout = open(wraith.IYRICONF,'w')
            cp.write(fout)
        except IOError as e:
            self.err("File Error","Error <{0}> writing to config file".format(e))
        except ConfigParser.Error as e:
            self.err("Configuration Error","Error <{0}> writing to config file".format(e))
        else:
            self.info('Success',"Restart Iyri if running for changes to take effect")
        finally:
            if fout: fout.close()

#### callbacks

    def gpscb(self):
        """ enable/disable gps entries as necessary """
        if self.vfixed.get():
            # fixed is on enable only fixed entries
            self._entLat.configure(state=tk.NORMAL)
            self._entLon.configure(state=tk.NORMAL)
            self._entAlt.configure(state=tk.NORMAL)
            self._entHeading.configure(state=tk.NORMAL)
            self._entGPSPort.configure(state=tk.DISABLED)
            self._entDevID.configure(state=tk.DISABLED)
            self._entPoll.configure(state=tk.DISABLED)
            self._entEPX.configure(state=tk.DISABLED)
            self._entEPY.configure(state=tk.DISABLED)
        else:
            # fixed is off enable only dynamic entries
            self._entLat.configure(state=tk.DISABLED)
            self._entLon.configure(state=tk.DISABLED)
            self._entAlt.configure(state=tk.DISABLED)
            self._entHeading.configure(state=tk.DISABLED)
            self._entGPSPort.configure(state=tk.NORMAL)
            self._entDevID.configure(state=tk.NORMAL)
            self._entPoll.configure(state=tk.NORMAL)
            self._entEPX.configure(state=tk.NORMAL)
            self._entEPY.configure(state=tk.NORMAL)

# Help-->About
class AboutPanel(gui.SimplePanel):
    """ AboutPanel - displays a simple About Panel """
    def __init__(self,tl,chief):
        gui.SimplePanel.__init__(self,tl,chief,"About Wraith","widgets/icons/about.png")

    def _body(self):
        self.logo = PhotoImage(imgopen("widgets/icons/splash.png"))
        ttk.Label(self,image=self.logo).grid(row=0,column=0,sticky='n')
        ttk.Label(self,text="wraith-rt {0}".format(wraith.__version__),
                  font=("Roman",16,'bold')).grid(row=1,column=0,sticky='n')
        ttk.Label(self,justify=tk.CENTER,
                  text="Wireless Reconnaissance And\nIntelligent Target Harvesting",
                  font=("Roman",8,'bold')).grid(row=2,column=0,sticky='n')
        ttk.Label(self,
                  text="Copyright {0} {1} {2}".format(COPY,
                                                      wraith.__date__.split(' ')[1],
                                                      wraith.__email__),
                  font=('Roman',8,'bold')).grid(row=3,column=0,sticky='n')