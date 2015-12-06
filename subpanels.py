#!/usr/bin/env python
""" subpanels.py - defines the subpanels called by the wraith Master panel """

__name__ = 'subpanels'
__license__ = 'GPL v3.0'
__version__ = '0.0.3'
__revdate__ = 'May 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import os                                  # file info etc
import re                                  # reg. exp.
import Tkinter as tk                       # gui constructs
import tkFileDialog as tkFD                # import file gui dialogs
import ttk                                 # ttk widgets
import mgrs                                # for mgrs2latlon conversions etc
import math                                # for conversions, calculations
import time                                # for timestamps
from PIL import Image,ImageTk              # image input & support
import psycopg2 as psql                    # postgresql api
import psycopg2.extras as pextras          # cursors and such
import ConfigParser                        # config file parsing
import wraith                              # version info & constants
import wraith.widgets.panel as gui         # graphics suite
from wraith.wifi import iw                 # wireless interface details
from wraith.wifi import iwtools as iwt     # interface details
from wraith.wifi import mpdu               # for 802.11 types/subtypes
from wraith.iyri.iyri import parsechlist   # channelist validity check
from wraith.utils import timestamps        # valid data/time
from wraith.utils import landnav           # lang nav utilities
from wraith.utils import cmdline           # cmdline functionality

# Validation reg. exp.
IPADDR = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$") # re for ip addr
MACADDR = re.compile("^([0-9A-F]{2}:){5}([0-9A-F]{2})$")    # re for mac addr (capital letters only)
GPSDID = re.compile("^[0-9A-F]{4}:[0-9A-F]{4}$")            # re for gps device id (capital leters only)

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
        self._entPWD = ttk.Entry(frmS,width=10)
        self._entPWD.grid(row=4,column=1,sticky='w')

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
        if re.match(IPADDR,host) is None and host != 'localhost':
            self.err("Invalid Input","Host {0} is not valid".format(host))
            return False
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
        # copied from LOBster
        m = self._entMGRS.get()
        ll = self._entLatLon.get()
        if m and ll: self.err('Error',"One field must be empty")
        else:
            if m:
                try:
                    ll = self._mgrs.toLatLon(m)
                    "{0:.3} {1:.3}".format(ll[0],ll[1])
                    self._entLatLon.insert(0,"{0:.3} {1:.3}".format(ll[0],ll[1]))
                except:
                    self.err('Error',"MGRS is not valid")
            elif ll:
                try:
                    ll = ll.split()
                    m = self._mgrs.toMGRS(ll[0],ll[1])
                    self._entMGRS.insert(0,m)
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
                self._entmW.insert(0,'{0.3}'.format(w))
                self._entmBm.insert(0,'{0.3}'.format(m))
            except:
                self.err('Error',"dBm is not valid")
        elif w and not (m or d):
            try:
                d = 10*math.log10(float(w))
                m = 100 * d
                self._entdBm.insert(0,'{0.3}'.format(d))
                self._entmBm.insert(0,'{0.3}'.format(m))
            except:
                self.err('Error',"dBm is not valid")
        elif m and not (d or m):
            try:
                d = float(m) / 100
                w = math.pow(10,(float(d)/10.0))
                self._entdBm.insert(0,'{0.3}'.format(d))
                self._entmW.insert(0,'{0.3}'.format(w))
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
        formula = self._formula
        # make sure no entries are empty substituting the value of the entry as
        # we go
        # TODO use enumerate here
        for i in xrange(len(self._entries)):
            if self._entries[i].get():
                formula = formula.replace('${0}'.format(i),
                                          "{0}('{1}')".format((self._inputs[i][2],
                                                               self._entries[i].get()))
            else:
                self.err('Error',"All entries must be filled in")
                return

        # attempt to calculate
        try:
            self._ans.set("{0} {1}".format(str(eval(formula)),self._meas))
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
    """ a singular panel which display information pertaining to the "program" """
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
        nics = iwt.wifaces()
        ls = self._tree.get_children()

        # remove nics that are no longer present
        for nic in ls:
            if not nic in nics: self._tree.delete(nic)

        # add new system nics
        for nic in nics:
            (phy,w) = iw.dev(nic)
            a = w[0]['addr']
            m = w[0]['type']
            d = iwt.getdriver(nic)
            c = iwt.getchipset(d)
            if nic in ls: # nic is already listed
                # check if data has changed -
                cur = self._tree.set(nic)
                if cur['PHY'] != phy: self._tree.set(nic,'PHY',phy)
                if cur['MAC'] != a: self._tree.set(nic,'MAC',a)
                if cur['Mode'] != m: self._tree.set(nic,'Mode',m)
                if cur['Driver'] != d: self._tree.set(nic,'Driver',d)
                if cur['Chipset'] != c: self._tree.set(nic,'Chipset',c)
            else:         # nic is new
                self._tree.insert('','end',iid=nic,values=(phy,nic,a,m,d,c))

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
        self._curs = {}
        self._conn = conn
        gui.SimplePanel.__init__(self,tl,chief,'Databin',"widgets/icons/db.png")

    def donothing(self): pass

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
            self._bins[b] = {'img':ImageTk.PhotoImage(Image.open('widgets/icons/bin%s.png'%b))}
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

    def notifyclose(self,name):
        """ close the associated bin's cursor """
        self._curs[name].close()
        gui.SimplePanel.notifyclose(self,name)

    def viewquery(self,b):
        """ shows query panel for bin b """
        # notify user if not connected to database
        if not self._chief.isconnected:
            self.warn("Disconnected","Connect and try again")
            return

        panel = self.getpanels('query{0}'.format(b),False)
        if not panel:
            t = tk.Toplevel()
            pnl = QueryPanel(t,self,"Query [bin {0}]".format(b),b,
                             self._chief.connectstring)
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

    def binrc(self,event):
        """ on right click, show context menu for this button """
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
        # TODO use enumerate here
        for i in xrange(len(hdrs)):
            self._trSess.column(i,width=hdrlens[i],anchor=tk.CENTER)
            self._trSess.heading(i,text=hdrs[i])
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
        # TODO: use enumerate here
        for i in xrange(3):
            self._vfilteron.append(tk.IntVar())
            ttk.Checkbutton(frmFO,text=filters[i],variable=self._vfilteron[i]).grid(row=0,column=i,sticky='w')

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
        ttk.Checkbutton(frmSL,text='Recon',variable=self._vrecon).grid(row=1,column=3,sticky='w')
        self._vcoll = tk.IntVar()
        ttk.Checkbutton(frmSL,text='Surveillance',variable=self._vcoll).grid(row=2,column=3,sticky='w')
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
        # TODO use enumerate here
        for i in xrange(len(RT_FLAGS)):
            self._vrtflags.append(tk.IntVar())
            chk = ttk.Checkbutton(frmSigFlags,text=RT_FLAGS[i],variable=self._vrtflags[i])
            chk.grid(row=(i / 4),column=(i % 4),sticky='w')
        ttk.Separator(frmSigFlags,orient=tk.VERTICAL).grid(row=0,column=4,rowspan=2,sticky='ns')
        self._vandorrtflags = tk.IntVar()
        ttk.Radiobutton(frmSigFlags,text='AND',variable=self._vandorrtflags,value=0).grid(row=0,column=5,sticky='w')
        ttk.Radiobutton(frmSigFlags,text='OR',variable=self._vandorrtflags,value=1).grid(row=1,column=5,sticky='w')
        frmSigChFlags = ttk.LabelFrame(frmSig,text="Channel Flags")
        frmSigChFlags.grid(row=2,column=0,sticky='nwse')
        self._vchflags = []
        # TODO use enumerate here
        for i in xrange(len(CH_FLAGS)):
            self._vchflags.append(tk.IntVar())
            chk = ttk.Checkbutton(frmSigChFlags,text=CH_FLAGS[i],variable=self._vchflags[i])
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
        # TODO use enumerate here
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
        # TODO use enumerate here
        for i in xrange(len(FC_FLAGS)):
            self._vfcflags.append(tk.IntVar())
            chk = ttk.Checkbutton(frmRFC,text=FC_FLAGS[i],variable=self._vfcflags[i])
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
        # TODO should we use enumerate here
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
        """ sessions tree ctrl-a -> selects all """
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
        self._entFromDate.delete(0,tk.END)               # delete from entries
        self._entFromDate.insert(0,d)                    # and add now
        self._entFromTime.delete(0,tk.END)
        self._entFromTime.insert(0,t)

    def tonow(self):
        """ assign now() to the to entries """
        d,t = timestamps.ts2iso(time.time()).split('T') # split isoformat on 'T'
        t = t[:8]                                       # drop the microseconds
        self._entToDate.delete(0,tk.END)                 # delete from entries
        self._entToDate.insert(0,d)                      # and add now
        self._entToTime.delete(0,tk.END)
        self._entToTime.insert(0,t)

    def browse(self):
        """ open a file browsing dialog for selector file """
        fpath = tkFD.askopenfilename(title="Open Selector File",
                                     filetypes=[("Text Files","*.txt"),
                                                ("Selector Files","*.sel")],
                                     parent=self)
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
            if mac and re.match(MACADDR,mac) is None:
                self.err("Invalid Input","MAC addr {0} is not valid".format(mac))
                return False
            mac = self._entSensorSpoof.get().upper()
            if mac and re.match(MACADDR,mac) is None:
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
            if not parsechlist(self._entSignalCh.get(),'scan'):
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
            if mac and re.match(MACADDR,mac) is None:
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
                    if re.match(MACADDR,s.strip()) is None:
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
                                          ('Recon',gui.lenpix(12),str),
                                          ('Surveillance',gui.lenpix(12),str),
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

        # TODO: could this get extremely large?
        #       use difference (ls,sids) to remove items no longer in the table
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
            recon = s['recon']
            surveil = s['surveillance']
            nF = s['fcnt']
            if sid in ls: # session is present
                # check for changes (id and start are not checked0
                cur = self._tree.set(sid)
                if cur['Host'] != host: self._tree.set(sid,'Host',host)
                if cur['Kernel'] != kern: self._tree.set(sid,'Kernel',kern)
                if cur['Stop'] != stop: self._tree.set(sid,'Stop',stop)
                if cur['GPSD'] != devid: self._tree.set(sid,'GPSD',devid)
                if cur['Recon'] != recon: self._tree.set(sid,'Recon',recon)
                if cur['Surveillance'] != surveil: self._tree.set(sid,'Surveillance',surveil)
                if cur['Frames'] != nF: self._tree.set(sid,'Frames',nF)
            else:         # session not present
                self._tree.insert('','end',iid=sid,values=(sid,host,kern,start,stop,
                                                           devid,recon,coll,nF))

    def treerc(self,event):
        """ show delete context menu for the specified item """
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
        """ delete specified entry(s) """
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

# Storage->Nidus-->Config
class NidusConfigPanel(gui.ConfigPanel):
    """ Display Nidus Configuration Panel """
    def __init__(self,tl,chief):
        gui.ConfigPanel.__init__(self,tl,chief,"Configure Nidus")

    def _makegui(self,frm):
        """ set up entry widgets """
        # Storage Configuration
        frmSS = ttk.LabelFrame(frm,text='Storage')
        frmSS.grid(row=0,column=0,sticky='nwse')
        ttk.Label(frmSS,text='Host: ').grid(row=0,column=0,sticky='w')
        self._entHost = ttk.Entry(frmSS,width=15)
        self._entHost.grid(row=0,column=1,sticky='e')
        ttk.Label(frmSS,text=' ').grid(row=0,column=2) # separator
        ttk.Label(frmSS,text='Port: ').grid(row=0,column=3,sticky='w')
        self._entPort = ttk.Entry(frmSS,width=5)
        self._entPort.grid(row=0,column=4,sticky='w')
        ttk.Label(frmSS,text='DB: ').grid(row=1,column=0,sticky='w')
        self._entDB = ttk.Entry(frmSS,width=10)
        self._entDB.grid(row=1,column=1,sticky='w')
        ttk.Label(frmSS,text='User: ').grid(row=1,column=3,sticky='w')
        self._entUser = ttk.Entry(frmSS,width=10)
        self._entUser.grid(row=1,column=4,sticky='e')
        ttk.Label(frmSS,text=' ').grid(row=1,column=5) # separator
        ttk.Label(frmSS,text='PWD: ').grid(row=1,column=6,sticky='w')
        self._entPWD = ttk.Entry(frmSS,width=10)
        self._entPWD.grid(row=1,column=7,sticky='w')

        # SSE Configuration
        frmS = ttk.LabelFrame(frm,text='SSE')
        frmS.grid(row=1,column=0,sticky='nwse')
        ttk.Label(frmS,text='Packets: ').grid(row=0,column=0,sticky='w')
        self._vsave = tk.IntVar()
        ttk.Checkbutton(frmS,text="Save",variable=self._vsave,command=self.cb).grid(row=0,column=1,sticky='w')
        self._vpriv = tk.IntVar()
        self._chkPriv = ttk.Checkbutton(frmS,text="Private",variable=self._vpriv)
        self._chkPriv.grid(row=0,column=2,sticky='e')
        ttk.Label(frmS,text='Path: ').grid(row=0,column=3,sticky='w')
        self._entPCAPPath = ttk.Entry(frmS,width=25)
        self._entPCAPPath.grid(row=0,column=4)
        ttk.Label(frmS,text="Max Size: ").grid(row=1,column=1,sticky='w')
        self._entMaxSz = ttk.Entry(frmS,width=4)
        self._entMaxSz.grid(row=1,column=2,sticky='w')
        ttk.Label(frmS,text="Max Files: ").grid(row=1,column=3,sticky='w')
        self._entMaxFiles = ttk.Entry(frmS,width=4)
        self._entMaxFiles.grid(row=1,column=4,columnspan=2,sticky='w')
        ttk.Label(frmS,text='Threads: ').grid(row=2,column=0,sticky='w')
        ttk.Label(frmS,text='Store: ').grid(row=2,column=1,sticky='w')
        self._entNumStore = ttk.Entry(frmS,width=2)
        self._entNumStore.grid(row=2,column=2,sticky='w')
        ttk.Label(frmS,text='Extract: ').grid(row=2,column=3,sticky='w')
        self._entNumExtract = ttk.Entry(frmS,width=2)
        self._entNumExtract.grid(row=2,column=4,sticky='w')

        # OUI Configuration
        frmO = ttk.Frame(frm)
        frmO.grid(row=2,column=0,sticky='nwse')
        ttk.Label(frmO,text='OUI Path: ').grid(row=0,column=0,sticky='w')
        self._entOUIPath = ttk.Entry(frmO,width=50)
        self._entOUIPath.grid(row=0,column=1,sticky='e')

    def cb(self):
        """ Save Checkbutton callback: disable/enable Save options as necessary """
        if self._vsave.get(): state = tk.NORMAL
        else: state = tk.DISABLED
        self._chkPriv.configure(state=state)
        self._entPCAPPath.configure(state=state)
        self._entMaxSz.configure(state=state)
        self._entMaxFiles.configure(state=state)

    def _initialize(self):
        """ insert values from config file into entry boxes """
        conf = ConfigParser.RawConfigParser()
        if not conf.read(wraith.NIDUSCONF):
            self.err("File Not Found","nidus.conf was not found")
            return

        # in case the conf file is invalid, set to empty if not present
        # storage server
        self._entHost.delete(0,tk.END)
        if conf.has_option('Storage','host'):
            self._entHost.insert(0,conf.get('Storage','host'))

        self._entPort.delete(0,tk.END)
        if conf.has_option('Storage','port'):
            self._entPort.insert(0,conf.get('Storage','port'))

        self._entDB.delete(0,tk.END)
        if conf.has_option('Storage','db'):
            self._entDB.insert(0,conf.get('Storage','db'))

        self._entUser.delete(0,tk.END)
        if conf.has_option('Storage','user'):
            self._entUser.insert(0,conf.get('Storage','user'))

        self._entPWD.delete(0,tk.END)
        if conf.has_option('Storage','pwd'):
            self._entPWD.insert(0,conf.get('Storage','pwd'))

        # SSE section
        try:
            save = int(conf.getboolean('SSE','save'))
            private = int(conf.getboolean('SSE','save_private'))
        except:
            save = 0
            private = 0
        self._entPCAPPath.delete(0,tk.END)
        if conf.has_option('SSE','save_path'):
            self._entPCAPPath.insert(0,conf.get('SSE','save_path'))
        self._entMaxSz.delete(0,tk.END)
        if conf.has_option('SSE','save_maxsize'):
            self._entMaxSz.insert(0,conf.get('SSE','save_maxsize'))
        self._entMaxFiles.delete(0,tk.END)
        if conf.has_option('SSE','save_maxfiles'):
            self._entMaxFiles.insert(0,conf.get('SSE','save_maxfiles'))
        self._entNumStore.delete(0,tk.END)
        if conf.has_option('SSE','store_threads'):
            self._entNumStore.insert(0,conf.get('SSE','store_threads'))
        else: self._entNumStore.insert(0,'2')
        self._entNumExtract.delete(0,tk.END)
        if conf.has_option('SSE','extract_threads'):
            self._entNumExtract.insert(0,conf.get('SSE','extract_threads'))
        else: self._entNumExtract.insert(0,'2')

        # disable/enable as needed
        if save: state = tk.NORMAL
        else: state = tk.DISABLED
        self._chkPriv.configure(state=state)
        self._entPCAPPath.configure(state=state)
        self._entMaxSz.configure(state=state)
        self._entMaxFiles.configure(state=state)

        # OUI section
        self._entOUIPath.delete(0,tk.END)
        if conf.has_option('OUI','path'):
            self._entOUIPath.insert(0,conf.get('OUI','Path'))
        else: self._entOUIPath.insert(0,'/etc/aircrack-ng/airodump-ng-oui.txt')

    def _validate(self):
        """ validate entries """
        # storage server
        host = self._entHost.get()
        if re.match(IPADDR,host) is None and host != 'localhost':
            self.err("Invalid Input","Host {0} is not valid".format(host))
            return False
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

        # if not saving pcaps, we ignore pcap options
        if self._vsave.get():
            # for the pcap directory, convert to absolute path before checking existence
            pPCAP = self._entPCAPPath.get()
            if not os.path.isabs(pPCAP):
                pPCAP = os.path.abspath(os.path.join('nidus',pPCAP))
            if not os.path.exists(pPCAP):
                self.err("Invalid Input",
                         "PCAP directory {0} does not exist".format(pPCAP))
                return False
            try:
                if int(self._entMaxSz.get()) < 1:
                    self.err("Invalid Input","Max Size must be >= 1")
                    return False
            except ValueError:
                self.err("Invalid Input","Max Size must be an integer")
                return False
            try:
                if int(self._entMaxFiles.get()) < 1:
                    self.err("Invalid Input","Max Files must be >= 1")
                    return False
            except ValueError:
                self.err("Invalid Input","Max files must be an integer")
                return False
        try:
            st = int(self._entNumStore.get())
            if st < 1 or st > 10:
                self.err("Invalid Input","Number of store threads must be between 1 and 10")
                return False
        except ValueError:
            self.err("Invalid Input","Number of store threads must be an integer")
            return False
        try:
            et = int(self._entNumExtract.get())
            if et < 1 or et > 10:
                self.err("Invalid Input","Number of extract threads must be between 1 and 10")
                return False
        except ValueError:
            self.err("Invalid Input","Number of extract threads must be an integer")
            return False
        if not os.path.isfile(self._entOUIPath.get()):
            self.err("Invalid Input",
                     "OUI file {0} is invalid".format(self._entOUIPath.get()))
            return False
        return True

    def _write(self):
        """ write entry inputs to config file """
        fout = None
        try:
            cp = ConfigParser.ConfigParser()
            cp.add_section('SSE')
            cp.set('SSE','save','yes' if self._vsave.get() else 'no')
            cp.set('SSE','save_private','yes' if self._vpriv.get() else 'no')
            cp.set('SSE','save_path',self._entPCAPPath.get())
            cp.set('SSE','save_maxsize',self._entMaxSz.get())
            cp.set('SSE','save_maxfiles',self._entMaxFiles.get())
            cp.set('SSE','store_threads',self._entNumStore.get())
            cp.set('SSE','extract_threads',self._entNumExtract.get())
            cp.add_section('OUI')
            cp.set('OUI','path',self._entOUIPath.get())
            fout = open(wraith.NIDUSCONF,'w')
            cp.write(fout)
        except IOError as e:
            self.err("File Error","Error <{0}> writing to config file".format(e))
        except ConfigParser.Error as e:
            self.err("Configuration Error",
                     "Error <{0}> writing to config file".format(e))
        else:
            self.info('Success',"Changes will take effect on next start")
        finally:
            if fout: fout.close()

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

        # Recon Tab Configuration
        frmR = ttk.Frame(nb)
        ttk.Label(frmR,text='NIC: ').grid(row=0,column=0,sticky='nw')
        self._entReconNic = ttk.Entry(frmR,width=5)
        self._entReconNic.grid(row=0,column=1,sticky='nw')
        ttk.Label(frmR,text=' ').grid(row=0,column=2,sticky='w')
        ttk.Label(frmR,text='Spoof: ').grid(row=0,column=3,sticky='nw')
        self._entReconSpoof = ttk.Entry(frmR,width=17)
        self._entReconSpoof.grid(row=0,column=4,sticky='nw')
        ttk.Label(frmR,text='Desc: ').grid(row=1,column=0,sticky='nw')
        self._entReconDesc = tk.Text(frmR,width=42,height=3)
        self._entReconDesc.grid(row=1,column=1,columnspan=4,sticky='e')

        # ANTENNA SUB SECTION
        frmRA = ttk.LabelFrame(frmR,text='Antennas')
        frmRA.grid(row=2,column=0,columnspan=5,sticky='nwse')
        # ANTENNA SUBSECTION
        ttk.Label(frmRA,text="Number: ").grid(row=0,column=0,sticky='w')
        self._entReconAntNum = ttk.Entry(frmRA,width=2)
        self._entReconAntNum.grid(row=0,column=1,sticky='w')
        ttk.Label(frmRA,text='Gain: ').grid(row=1,column=0,sticky='w')
        self._entReconAntGain = ttk.Entry(frmRA,width=7)
        self._entReconAntGain.grid(row=1,column=1,sticky='w')
        ttk.Label(frmRA,text=" ").grid(row=1,column=2)
        ttk.Label(frmRA,text="Type: ").grid(row=1,column=3,sticky='e')
        self._entReconAntType = ttk.Entry(frmRA,width=15)
        self._entReconAntType.grid(row=1,column=4,sticky='e')
        ttk.Label(frmRA,text='Loss: ').grid(row=2,column=0,sticky='w')
        self._entReconAntLoss = ttk.Entry(frmRA,width=7)
        self._entReconAntLoss.grid(row=2,column=1,sticky='w')
        ttk.Label(frmRA,text=" ").grid(row=2,column=2)
        ttk.Label(frmRA,text="XYZ: ").grid(row=2,column=3,sticky='e')
        self._entReconAntXYZ = ttk.Entry(frmRA,width=15)
        self._entReconAntXYZ.grid(row=2,column=4,sticky='e')
        # SCAN PATTERN SUB SECTION
        frmRS = ttk.LabelFrame(frmR,text='Scan')
        frmRS.grid(row=3,column=0,columnspan=5,sticky='nwse')
        ttk.Label(frmRS,text="Dwell: ").grid(row=0,column=0,sticky='w')
        self._entReconScanDwell = ttk.Entry(frmRS,width=5)
        self._entReconScanDwell.grid(row=0,column=2,sticky='w')
        ttk.Label(frmRS,text=" ").grid(row=0,column=3)
        ttk.Label(frmRS,text="Start: ").grid(row=0,column=4,sticky='e')
        self._entReconScanStart = ttk.Entry(frmRS,width=3)
        self._entReconScanStart.grid(row=0,column=5,sticky='w')
        ttk.Label(frmRS,text="Scan: ").grid(row=1,column=0,sticky='w')
        self._entReconScanScan = ttk.Entry(frmRS,width=12)
        self._entReconScanScan.grid(row=1,column=2,sticky='w')
        ttk.Label(frmRS,text=" ").grid(row=1,column=3)
        ttk.Label(frmRS,text="Pass: ").grid(row=1,column=4,sticky='w')
        self._entReconScanPass = ttk.Entry(frmRS,width=12)
        self._entReconScanPass.grid(row=1,column=5,sticky='e')
        self._vrpause = tk.IntVar()
        ttk.Checkbutton(frmRS,text="Paused",variable=self._vrpause).grid(row=2,column=0,columnspan=2)
        nb.add(frmR,text='Recon')

        # Surveillance Tab Configuration
        frmC = ttk.Frame(nb)
        ttk.Label(frmC,text='NIC: ').grid(row=0,column=0,sticky='nw')
        self._entSurveilNic = ttk.Entry(frmC,width=5)
        self._entSurveilNic.grid(row=0,column=1,sticky='nw')
        ttk.Label(frmC,text=' ').grid(row=0,column=2,sticky='w')
        ttk.Label(frmC,text='Spoof: ').grid(row=0,column=3,sticky='wn')
        self._entSurveilSpoof = ttk.Entry(frmC,width=17)
        self._entSurveilSpoof.grid(row=0,column=4,sticky='nw')
        ttk.Label(frmC,text='Desc: ').grid(row=1,column=0,sticky='nw')
        self._entSurveilDesc = tk.Text(frmC,width=42,height=3)
        self._entSurveilDesc.grid(row=1,column=1,columnspan=4,sticky='e')

        # ANTENNA SUB SECTION
        frmCA = ttk.LabelFrame(frmC,text='Antennas')
        frmCA.grid(row=2,column=0,columnspan=5,sticky='nwse')
        # ANTENNA SUBSECTION
        ttk.Label(frmCA,text="Number: ").grid(row=0,column=0,sticky='w')
        self._entSurveilAntNum = ttk.Entry(frmCA,width=2)
        self._entSurveilAntNum.grid(row=0,column=1,sticky='w')
        ttk.Label(frmCA,text='Gain: ').grid(row=1,column=0,sticky='w')
        self._entSurveilAntGain = ttk.Entry(frmCA,width=7)
        self._entSurveilAntGain.grid(row=1,column=1,sticky='w')
        ttk.Label(frmCA,text=" ").grid(row=1,column=2)
        ttk.Label(frmCA,text="Type: ").grid(row=1,column=3,sticky='e')
        self._entSurveilAntType = ttk.Entry(frmCA,width=15)
        self._entSurveilAntType.grid(row=1,column=4,sticky='e')
        ttk.Label(frmCA,text='Loss: ').grid(row=2,column=0,sticky='w')
        self._entSurveilAntLoss = ttk.Entry(frmCA,width=7)
        self._entSurveilAntLoss.grid(row=2,column=1,sticky='w')
        ttk.Label(frmCA,text=" ").grid(row=2,column=2)
        ttk.Label(frmCA,text="XYZ: ").grid(row=2,column=3,sticky='e')
        self._entSurveilAntXYZ = ttk.Entry(frmCA,width=15)
        self._entSurveilAntXYZ.grid(row=2,column=4,sticky='e')
        # SCAN PATTERN SUB SECTION
        frmCS = ttk.LabelFrame(frmC,text='Scan Pattern')
        frmCS.grid(row=3,column=0,columnspan=5,sticky='nwse')
        ttk.Label(frmCS,text="Dwell: ").grid(row=0,column=0,sticky='w')
        self._entSurveilScanDwell = ttk.Entry(frmCS,width=5)
        self._entSurveilScanDwell.grid(row=0,column=2,sticky='w')
        ttk.Label(frmCS,text=" ").grid(row=0,column=3)
        ttk.Label(frmCS,text="Start: ").grid(row=0,column=4,sticky='e')
        self._entSurveilScanStart = ttk.Entry(frmCS,width=3)
        self._entSurveilScanStart.grid(row=0,column=5,sticky='w')
        ttk.Label(frmCS,text="Scan: ").grid(row=1,column=0,sticky='w')
        self._entSurveilScanScan = ttk.Entry(frmCS,width=12)
        self._entSurveilScanScan.grid(row=1,column=2,sticky='w')
        ttk.Label(frmCS,text=" ").grid(row=1,column=3)
        ttk.Label(frmCS,text="Pass: ").grid(row=1,column=4,sticky='w')
        self._entSurveilScanPass = ttk.Entry(frmCS,width=12)
        self._entSurveilScanPass.grid(row=1,column=5,sticky='e')
        self._vcpause = tk.IntVar()
        ttk.Checkbutton(frmCS,text="Paused",variable=self._vcpause).grid(row=2,column=0,columnspan=2)
        nb.add(frmC,text='Surveillance')

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
        frmM = ttk.Frame(nb)
        frmMS = ttk.LabelFrame(frmM,text='Storage')
        frmMS.grid(row=0,column=0,sticky='w')
        ttk.Label(frmMS,text=' Host: ').grid(row=0,column=0)
        self._entStoreHost = ttk.Entry(frmMS,width=15)
        self._entStoreHost.grid(row=0,column=1)
        ttk.Label(frmMS,text=' Port: ').grid(row=0,column=2)
        self._entStorePort = ttk.Entry(frmMS,width=5)
        self._entStorePort.grid(row=0,column=3)
        frmML = ttk.LabelFrame(frmM,text='Local')
        frmML.grid(row=1,column=0,sticky='w')
        ttk.Label(frmML,text="Region: ").grid(row=0,column=0,sticky='w')
        self._entRegion = ttk.Entry(frmML,width=3)
        self._entRegion.grid(row=0,column=1,sticky='w')
        ttk.Label(frmML,text=" C2C: ").grid(row=0,column=2,sticky='w')
        self._entC2CPort = ttk.Entry(frmML,width=5)
        self._entC2CPort.grid(row=0,column=3,sticky='w')
        nb.add(frmM,text='Misc.')

    def _initialize(self):
        """ insert values from config file into entry boxes """
        cp = ConfigParser.RawConfigParser()
        if not cp.read(wraith.IYRICONF):
            self.err("File Not Found","File iyri.conf was not found")
            return

        # start by reading the recon radio details
        self._entReconNic.delete(0,tk.END)
        if cp.has_option('Recon','nic'):
            self._entReconNic.insert(0,cp.get('Recon','nic'))
        self._entReconSpoof.delete(0,tk.END)
        if cp.has_option('Recon','spoof'):
            self._entReconSpoof.insert(0,cp.get('Recon','spoof'))
        self._entReconDesc.delete(1.0,tk.END)
        if cp.has_option('Recon','desc'):
            self._entReconDesc.insert(tk.END,cp.get('Recon','desc'))
        self._entReconAntNum.delete(0,tk.END)
        if cp.has_option('Recon','antennas'):
            self._entReconAntNum.insert(0,cp.get('Recon','antennas'))
        self._entReconAntGain.delete(0,tk.END)
        if cp.has_option('Recon','antenna_gain'):
            self._entReconAntGain.insert(0,cp.get('Recon','antenna_gain'))
        self._entReconAntType.delete(0,tk.END)
        if cp.has_option('Recon','antenna_type'):
            self._entReconAntType.insert(0,cp.get('Recon','antenna_type'))
        self._entReconAntLoss.delete(0,tk.END)
        if cp.has_option('Recon','antenna_loss'):
            self._entReconAntLoss.insert(0,cp.get('Recon','antenna_loss'))
        self._entReconAntXYZ.delete(0,tk.END)
        if cp.has_option('Recon','antenna_xyz'):
            self._entReconAntXYZ.insert(0,cp.get('Recon','antenna_xyz'))
        self._entReconScanDwell.delete(0,tk.END)
        if cp.has_option('Recon','dwell'):
            self._entReconScanDwell.insert(0,cp.get('Recon','dwell'))
        self._entReconScanStart.delete(0,tk.END)
        if cp.has_option('Recon','scan_start'):
            self._entReconScanStart.insert(0,cp.get('Recon','scan_start'))
        self._entReconScanScan.delete(0,tk.END)
        if cp.has_option('Recon','scan'):
            self._entReconScanScan.insert(0,cp.get('Recon','scan'))
        self._entReconScanPass.delete(0,tk.END)
        if cp.has_option('Recon','pass'):
            self._entReconScanPass.insert(0,cp.get('Recon','pass'))
        self._vrpause.set(0)
        if cp.has_option('Recon','paused'):
            if cp.getboolean('Recon','paused'): self._vrpause.set(1)

        # then the surveillance radio details
        self._entSurveilNic.delete(0,tk.END)
        if cp.has_option('Surveillance','nic'):
            self._entSurveilNic.insert(0,cp.get('Surveillance','nic'))
        self._entSurveilSpoof.delete(0,tk.END)
        if cp.has_option('Surveillance','spoof'):
            self._entSurveilSpoof.insert(0,cp.get('Surveillance','spoof'))
        self._entSurveilDesc.delete(1.0,tk.END)
        if cp.has_option('Surveillance','desc'):
            self._entSurveilDesc.insert(tk.END,cp.get('Surveillance','desc'))
        self._entSurveilAntNum.delete(0,tk.END)
        if cp.has_option('Surveillance','antennas'):
            self._entSurveilAntNum.insert(0,cp.get('Surveillance','antennas'))
        self._entSurveilAntGain.delete(0,tk.END)
        if cp.has_option('Surveillance','antenna_gain'):
            self._entSurveilAntGain.insert(0,cp.get('Surveillance','antenna_gain'))
        self._entSurveilAntType.delete(0,tk.END)
        if cp.has_option('Surveillance','antenna_type'):
            self._entSurveilAntType.insert(0,cp.get('Surveillance','antenna_type'))
        self._entSurveilAntLoss.delete(0,tk.END)
        if cp.has_option('Surveillance','antenna_loss'):
            self._entSurveilAntLoss.insert(0,cp.get('Surveillance','antenna_loss'))
        self._entSurveilAntXYZ.delete(0,tk.END)
        if cp.has_option('Surveillance','antenna_xyz'):
            self._entSurveilAntXYZ.insert(0,cp.get('Surveillance','antenna_xyz'))
        self._entSurveilScanDwell.delete(0,tk.END)
        if cp.has_option('Surveillance','dwell'):
            self._entSurveilScanDwell.insert(0,cp.get('Surveillance','dwell'))
        self._entSurveilScanStart.delete(0,tk.END)
        if cp.has_option('Surveillance','scan_start'):
            self._entSurveilScanStart.insert(0,cp.get('Surveillance','scan_start'))
        self._entSurveilScanScan.delete(0,tk.END)
        if cp.has_option('Surveillance','scan'):
            self._entSurveilScanScan.insert(0,cp.get('Surveillance','scan'))
        self._entSurveilScanPass.delete(0,tk.END)
        if cp.has_option('Surveillance','pass'):
            self._entSurveilScanPass.insert(0,cp.get('Surveillance','pass'))
        self._vcpause.set(0)
        if cp.has_option('Surveillance','paused'):
            if cp.getboolean('Surveillance','paused'): self._vcpause.set(1)

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

    def _validate(self):
        """ validate entries """
        # start with the recon radio details
        nic = self._entReconNic.get()
        if not nic:
            self.err("Invalid Recon Input","Radio nic must be specified")
            return False
        elif not nic in iwt.wifaces():
            self.warn("Not Found","Recon radio may not be wireless")
        spoof = self._entReconSpoof.get().upper()
        if spoof and re.match(MACADDR,spoof) is None:
            self.err("Invalid Recon Input","Spoofed MAC addr %s is not valid")
            return False

        # process antennas, if # > 0 then force validation of all antenna widgets
        if self._entReconAntNum.get():
            try:
                nA = int(self._entReconAntNum.get())
                if nA:
                    try:
                        if len(map(float,self._entReconAntGain.get().split(','))) != nA:
                            raise IyriConfigException("Number of gain is invalid")
                    except ValueError:
                        raise IyriConfigException("Gain must be float or list of floats")
                    if len(self._entReconAntType.get().split(',')) != nA:
                        raise IyriConfigException("Number of types is invalid")
                    try:
                        if len(map(float,self._entReconAntLoss.get().split(','))) != nA:
                            raise IyriConfigException("Number of loss is invalid")
                    except:
                        raise IyriConfigException("Loss must be float or list of floats")
                    try:
                        xyzs = self._entReconAntXYZ.get().split(',')
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
                self.err("Invalid Recon Input","Number of antennas must be numeric")
                return False
            except IyriConfigException as e:
                self.err("Invalid Recon Input",e)
                return False

        # process scan patterns
        try:
            float(self._entReconScanDwell.get())
        except:
            self.err("Invalid Recon Input","Scan dwell must be float")
            return False
        start = self._entReconScanStart.get()
        try:
            if start:
                if ':' in start: ch,chw = start.split(':')
                else:
                    ch = start
                    chw = None
                ch = int(ch)
                if chw and not chw in iw.IW_CHWS:
                    raise RuntimeError("Specified channel width is not valid")
        except ValueError:
            self.err("Invalid Recon Input","Scan start must be integer")
            return False
        except Exception as e:
            self.err("Invalid Recon Input",e)
            return False
        try:
            parsechlist(self._entReconScanScan.get(),'scan')
            parsechlist(self._entReconScanPass.get(),'pass')
        except ValueError as e:
            self.err("Invalid Recon Input",e)
            return False

        # then surveillance radio details
        nic = self._entSurveilNic.get()
        if nic:
            if not nic in iwt.wifaces(): self.warn("Not Found","Radio may not be wireless")
            spoof = self._entSurveilSpoof.get().upper()
            if spoof and re.match(MACADDR,spoof) is None:
                self.err("Invalid Surveillance Input","Spoofed MAC address is not valid")
                return False

            # process the antennas - if antenna number is > 0 then force validation of
            # all antenna widgets
            if self._entSurveilAntNum.get():
                try:
                    nA = int(self._entSurveilAntNum.get())
                    if nA:
                        try:
                            if len(map(float,self._entSurveilAntGain.get().split(','))) != nA:
                                raise IyriConfigException("Number of gain is invalid")
                        except ValueError:
                            raise IyriConfigException("Gain must be float or list of floats")
                        if len(self._entSurveilAntType.get().split(',')) != nA:
                            raise IyriConfigException("Number of types is invalid")
                        try:
                            if len(map(float,self._entSurveilAntLoss.get().split(','))) != nA:
                                raise IyriConfigException("Number of loss is invalid")
                        except:
                            raise IyriConfigException("Loss must be float or list of floats")
                        try:
                            xyzs = self._entSurveilAntXYZ.get().split(',')
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
                    self.err("Invalid Surveillance Input","Number of antennas must be numeric")
                    return False
                except IyriConfigException as e:
                    self.err("Invalid Surveillance Input",e)
                    return False

            # process scan patterns
            try:
                float(self._entSurveilScanDwell.get())
            except:
                self.err("Invalid Surveillance Input", "Scan dwell must be float")
                return False
            start = self._entSurveilScanStart.get()
            try:
                if start:
                    if ':' in start: ch,chw = start.split(':')
                    else:
                        ch = start
                        chw = None
                    ch = int(ch)
                    if chw and not chw in iw.IW_CHWS:
                        raise RuntimeError("Specified channel width is not valid")
            except ValueError:
                self.err("Invalid Surveillance Input", "Scan start must be integer")
                return False
            except Exception as e:
                self.err("Invalid Surveillance Input",e)
                return False
            try:
                parsechlist(self._entSurveilScanScan.get(),'scan')
                parsechlist(self._entSurveilScanPass.get(),'pass')
            except ValueError as e:
                self.err("Invalid Surveillance Input",e)
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
            if re.match(GPSDID,self._entDevID.get().upper()) is None:
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
        host = self._entStoreHost.get()
        if re.match(IPADDR,host) is None and host != 'localhost':
            self.err("Invalid Storage Input","Host is not a valid address")
        port = self._entStorePort.get()
        try:
            port = int(port)
            if port < 1024 or port > 65535: raise RuntimeError("")
        except ValueError:
            self.err("Invalid Storage Input","Host Port must be a number between 1024 and 65535")
            return False
        region = self._entRegion.get()
        if region and len(region) != 2:
            self.err("Invalid Local Input","Region must be 2 characters")
            return False
        port = self._entC2CPort.get()
        try:
            port = int(port)
            if port < 1024 or port > 65535: raise RuntimeError("")
        except:
            self.err("Invalid Local Input","C2C Port must be a number between 1024 and 65535")
            return False

        return True

    def _write(self):
        """ write entry inputs to config file """
        fout = None
        try:
            cp = ConfigParser.ConfigParser()
            cp.add_section('Recon')
            cp.set('Recon','nic',self._entReconNic.get())
            cp.set('Recon','paused','on' if self._vrpause.get() else 'off')
            if self._entReconSpoof.get(): cp.set('Recon','spoof',self._entReconSpoof.get())

            nA = self._entReconAntNum.get()
            if nA:
                cp.set('Recon','antennas',self._entReconAntNum.get())
                cp.set('Recon','antenna_gain',self._entReconAntGain.get())
                cp.set('Recon','antenna_loss',self._entReconAntLoss.get())
                cp.set('Recon','antenna_type',self._entReconAntType.get())
                cp.set('Recon','antenna_xyz',self._entReconAntXYZ.get())
            desc = self._entReconDesc.get(1.0,tk.END).strip()
            if desc: cp.set('Recon','desc',desc)
            cp.set('Recon','dwell',self._entReconScanDwell.get())
            cp.set('Recon','scan',self._entReconScanScan.get())
            cp.set('Recon','pass',self._entReconScanPass.get())
            cp.set('Recon','scan_start',self._entReconScanStart.get())
            if self._entSurveilNic.get():
                cp.add_section('Surveillance')
                cp.set('Surveillance','nic',self._entSurveilNic.get())
                cp.set('Surveillance','paused','on' if self._vcpause.get() else 'off')
                if self._entSurveilSpoof.get():
                    cp.set('Surveillance','spoof',self._entSurveilSpoof.get())
                nA = self._entSurveilAntNum.get()
                if nA:
                    cp.set('Surveillance','antennas',self._entSurveilAntNum.get())
                    cp.set('Surveillance','antenna_gain',self._entSurveilAntGain.get())
                    cp.set('Surveillance','antenna_loss',self._entSurveilAntLoss.get())
                    cp.set('Surveillance','antenna_type',self._entSurveilAntType.get())
                    cp.set('Surveillance','antenna_xyz',self._entSurveilAntXYZ.get())
                desc = self._entSurveilDesc.get(1.0,tk.END).strip()
                if desc: cp.set('Surveillance','desc',desc)
                cp.set('Surveillance','dwell',self._entSurveilScanDwell.get())
                cp.set('Surveillance','scan',self._entSurveilScanScan.get())
                cp.set('Surveillance','pass',self._entSurveilScanPass.get())
                cp.set('Surveillance','scan_start',self._entSurveilScanStart.get())
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
            region = self._entRegion.get()
            c2cport = self._entC2CPort.get()
            if region or c2cport:
                cp.add_section('Local')
                if region: cp.set('Local','region',region)
                if c2cport: cp.set('Local','C2C',c2cport)
            fout = open(wraith.IYRICONF,'w')
            cp.write(fout)
        except IOError as e:
            self.err("File Error",
                     "Error <{0}> writing to config file".format(e))
        except ConfigParser.Error as e:
            self.err("Configuration Error",
                     "Error <{0}> writing to config file".format(e))
        else:
            self.info('Success',"Restart for changes to take effect")
        finally:
            if fout: fout.close()

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
        self.logo = ImageTk.PhotoImage(Image.open("widgets/icons/splash.png"))
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