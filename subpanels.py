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
#import psycopg2 as psql                    # postgresql api
import psycopg2.extras as pextras          # cursors and such
import ConfigParser                        # config file parsing
import wraith                              # version info & constants
import wraith.widgets.panel as gui         # graphics suite
from wraith.radio import iw                # wireless interface details
from wraith.radio import iwtools as iwt    # interface details
from wraith.radio import mpdu              # for 802.11 types/subtypes
from wraith.dyskt.dyskt import parsechlist # channelist validity check
from wraith.utils import timestamps        # valid data/time
from wraith.utils import landnav           # lang nav utilities

# Validation reg. exp.
IPADDR = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$") # re for ip addr
MACADDR = re.compile("^([0-9A-F]{2}:){5}([0-9A-F]{2})$")    # re for mac addr (capital letters only)
GPSDID = re.compile("^[0-9A-F]{4}:[0-9A-F]{4}$")            # re for gps device id (capital letss only)

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
        self.txtHost = ttk.Entry(frmS,width=15)
        self.txtHost.grid(row=0,column=1,sticky='e')
        ttk.Label(frmS,text=' ').grid(row=0,column=2) # separator
        ttk.Label(frmS,text='Port: ').grid(row=0,column=3,sticky='w')
        self.txtPort = ttk.Entry(frmS,width=5)
        self.txtPort.grid(row=0,column=4,sticky='w')
        ttk.Label(frmS,text='DB: ').grid(row=1,column=0,sticky='w')
        self.txtDB = ttk.Entry(frmS,width=10)
        self.txtDB.grid(row=1,column=1,sticky='w')
        ttk.Label(frmS,text='User: ').grid(row=1,column=3,sticky='w')
        self.txtUser = ttk.Entry(frmS,width=10)
        self.txtUser.grid(row=1,column=4,sticky='e')
        ttk.Label(frmS,text='PWD: ').grid(row=4,column=0,sticky='w')
        self.txtPWD = ttk.Entry(frmS,width=10)
        self.txtPWD.grid(row=4,column=1,sticky='w')

        # Policy Configuration
        frmP = ttk.LabelFrame(frm,text='Policy')
        frmP.grid(row=1,column=0,sticky='nswe')

        # polite
        ttk.Label(frmP,text="Polite:").grid(row=0,column=0,sticky='w')
        self.ptype = tk.IntVar(self)
        self.rdoPoliteOn = ttk.Radiobutton(frmP,text='On',variable=self.ptype,value=1)
        self.rdoPoliteOn.grid(row=0,column=1,sticky='w')
        self.rdoPoliteOff = ttk.Radiobutton(frmP,text='Off',variable=self.ptype,value=0)
        self.rdoPoliteOff.grid(row=1,column=1,sticky='w')

        # separator label
        ttk.Label(frmP,text=" ").grid(row=0,column=2)

        # shutdown
        ttk.Label(frmP,text="Shutdown:").grid(row=0,column=3,sticky='w')
        self.stype = tk.IntVar(self)
        self.rdoShutdownAuto = ttk.Radiobutton(frmP,text='Auto',variable=self.stype,value=1)
        self.rdoShutdownAuto.grid(row=0,column=4,sticky='w')
        self.rdoShutdownManual = ttk.Radiobutton(frmP,text='Manual',variable=self.stype,value=0)
        self.rdoShutdownManual.grid(row=1,column=4,sticky='w')

    def _initialize(self):
        """ insert values from config file into entry boxes """
        conf = ConfigParser.RawConfigParser()
        if not conf.read(wraith.WRAITHCONF):
            self.err("File Not Found","File wraith.conf was not found")
            return

        # in case the conf file is invalid, set to empty if not present
        self.txtHost.delete(0,tk.END)
        if conf.has_option('Storage','host'):
            self.txtHost.insert(0,conf.get('Storage','host'))

        self.txtPort.delete(0,tk.END)
        if conf.has_option('Storage','port'):
            self.txtPort.insert(0,conf.get('Storage','port'))

        self.txtDB.delete(0,tk.END)
        if conf.has_option('Storage','db'):
            self.txtDB.insert(0,conf.get('Storage','db'))

        self.txtUser.delete(0,tk.END)
        if conf.has_option('Storage','user'):
            self.txtUser.insert(0,conf.get('Storage','user'))

        self.txtPWD.delete(0,tk.END)
        if conf.has_option('Storage','pwd'):
            self.txtPWD.insert(0,conf.get('Storage','pwd'))

        if conf.has_option('Policy','polite') and conf.get('Policy','polite').lower() == 'off':
            self.ptype.set(0)
        else:
            self.ptype.set(1)

        if conf.has_option('Policy','shutdown') and conf.get('Policy','shutdown').lower() == 'manual':
            self.stype.set(0)
        else:
            self.stype.set(1)

    def _validate(self):
        """ validate entries """
        host = self.txtHost.get()
        if re.match(IPADDR,host) is None and host != 'localhost':
            self.err("Invalid Input","Host %s is not valid" % host)
            return False
        port = self.txtPort.get()
        try:
            port = int(port)
            if port < 1024 or port > 65535: raise RuntimeError("")
        except:
            self.err("Invalid Input","Port must be a number between 1024 and 65535")
            return False
        if len(self.txtDB.get()) < 1 or len(self.txtDB.get()) > 15:
            self.err("Invalid Input","DB name must be between 1 and 15 characters")
            return False
        if len(self.txtUser.get()) < 1 or len(self.txtUser.get()) > 15:
            self.err("Invalid Input","User name must be between 1 and 15 characters")
            return False
        if len(self.txtPWD.get()) < 1 or len(self.txtPWD.get()) > 15:
            self.err("Invalid Input","Password must be between 1 and 15 characters")
            return False
        return True

    def _write(self):
        """ write entry inputs to config file """
        fout = None
        try:
            cp = ConfigParser.ConfigParser()
            cp.add_section('Storage')
            cp.set('Storage','host',self.txtHost.get())
            cp.set('Storage','port',self.txtPort.get())
            cp.set('Storage','db',self.txtDB.get())
            cp.set('Storage','user',self.txtUser.get())
            cp.set('Storage','pwd',self.txtUser.get())
            cp.add_section('Policy')
            cp.set('Policy','polite','on' if self.ptype else 'off')
            cp.set('Policy','shutdown','auto' if self.stype else 'manual')
            fout = open(wraith.WRAITHCONF,'w')
            cp.write(fout)
            fout.close()
        except IOError as e:
            self.err("File Error","Error <%s> writing to config file" % e)
        except ConfigParser.Error as e:
            self.err("Configuration Error","Error <%s> writing to config file" % e)
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
        self.txtLatLon = ttk.Entry(frmGeo,width=15)
        self.txtLatLon.grid(row=0,column=1,sticky='w')
        ttk.Label(frmGeo,text=' MGRS: ').grid(row=0,column=2,sticky='w')
        self.txtMGRS = ttk.Entry(frmGeo,width=15)
        self.txtMGRS.grid(row=0,column=3,sticky='w')
        ttk.Button(frmGeo,text='Convert',width=8,command=self.convertgeo).grid(row=0,column=4)
        # create the power frame
        frmPwr = ttk.LabelFrame(self,text='Power')
        frmPwr.grid(row=1,column=0,sticky='n')
        # add widgets to the power frame
        ttk.Label(frmPwr,text="dBm: ").grid(row=0,column=0)
        self.txtdBm = ttk.Entry(frmPwr,width=8)
        self.txtdBm.grid(row=0,column=1)
        ttk.Label(frmPwr,text=" mBm: ").grid(row=0,column=2)
        self.txtmBm = ttk.Entry(frmPwr,width=8)
        self.txtmBm.grid(row=0,column=3)
        ttk.Label(frmPwr,text=" mW: ").grid(row=0,column=4)
        self.txtmW = ttk.Entry(frmPwr,width=8)
        self.txtmW.grid(row=0,column=5)
        ttk.Button(frmPwr,text='Convert',width=8,command=self.convertpwr).grid(row=0,column=6)
        frmBtns = ttk.Frame(self,borderwidth=0)
        frmBtns.grid(row=2,column=0,sticky='n')
        ttk.Button(frmBtns,text='OK',width=6,command=self.delete).grid(row=0,column=0)
        ttk.Button(frmBtns,text='Clear',width=6,command=self.clear).grid(row=0,column=1)

    def convertgeo(self):
        """convert geo from lat/lon to mgrs or vice versa """
        # copied from LOBster
        m = self.txtMGRS.get()
        ll = self.txtLatLon.get()
        if m and ll: self.err('Error',"One field must be empty")
        else:
            if m:
                try:
                    ll = self._mgrs.toLatLon(m)
                    self.txtLatLon.insert(0,"%.3f %.3f" % (ll[0],ll[1]))
                except:
                    self.err('Error',"MGRS is not valid")
            elif ll:
                try:
                    ll = ll.split()
                    m = self._mgrs.toMGRS(ll[0],ll[1])
                    self.txtMGRS.insert(0,m)
                except:
                    self.err('Error',"Lat/Lon is not valid")

    def convertpwr(self):
        """ convert dBm to mW or vice versa """
        d = self.txtdBm.get()
        w = self.txtmW.get()
        m = self.txtmBm.get()
        if d and not (m or w):
            try:
                w = math.pow(10,(float(d)/10.0))
                m = 100 * float(d)
                self.txtmW.insert(0,'%.3f' % w)
                self.txtmBm.insert(0,'%.3f' % m)
            except:
                self.err('Error',"dBm is not valid")
        elif w and not (m or d):
            try:
                d = 10*math.log10(float(w))
                m = 100 * d
                self.txtdBm.insert(0,'%.3f' % d)
                self.txtmBm.insert(0,'%.3f' % m)
            except:
                self.err('Error',"dBm is not valid")
        elif m and not (d or m):
            try:
                d = float(m) / 100
                w = math.pow(10,(float(d)/10.0))
                self.txtdBm.insert(0,'%.3f' % d)
                self.txtmW.insert(0,'%.3f' % w)
            except:
                self.err('Error',"mBm is not valid")
        else: self.err('Error',"Two fields must be empty")

    def clear(self):
        """ clear all entries """
        self.txtLatLon.delete(0,tk.END)
        self.txtMGRS.delete(0,tk.END)
        self.txtdBm.delete(0,tk.END)
        self.txtmBm.delete(0,tk.END)
        self.txtmW.delete(0,tk.END)

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
                ttk.Label(frmEnt,text=" %s: " % input[c][0]).grid(row=r,column=c*2,sticky='w')
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
        for i in xrange(len(self._entries)):
            if self._entries[i].get():
                formula = formula.replace('$%d' % i,"%s('%s')" % (self._inputs[i][2],self._entries[i].get()))
            else:
                self.err('Error',"All entries must be filled in")
                return

        # attempt to calculate
        try:
            self._ans.set("%s %s" % (str(eval(formula)),self._meas))
        except ValueError as e:
            self.err("Invalid Input","%s is not a valid input" % e.message.split(':')[1].strip())
        except Exception as e:
            self.err('Error',e)

    def clear(self):
        """ clear all entries """
        for entry in self._entries: entry.delete(0,tk.END)
        self._ans.set('')

class InterfacePanel(gui.TabularPanel):
    """
     a singular panel which display information pertaining to the "program",
     cannot be closed by the user only by the MasterPanel
    """
    def __init__(self,tl,chief):
        gui.TabularPanel.__init__(self,tl,chief,"Interfaces",5,
                                  [('PHY',gui.lenpix('w')*5),
                                   ('NIC',gui.lenpix('w')*5),
                                   ('MAC',gui.lenpix('w')*15),
                                   ('Mode',gui.lenpix('managed')),
                                   ('Driver',gui.lenpix('w')*10),
                                   ('Chipset',gui.lenpix('w')*15)],
                                  "widgets/icons/sensor.png",False)

        # configure tree to show headings but not 0th column
        self.tree['show'] = 'headings'

        # start our poll function
        self.update()
        self.after(500,self.poll)

    def update(self):
        """ lists interfaces """
        # delete any entries
        self.tree.delete(*self.tree.get_children())

        # then get all entries
        for nic in iwt.wifaces():
            (phy,w) = iw.dev(nic)
            d = iwt.getdriver(nic)
            c = iwt.getchipset(d)
            self.tree.insert('','end',iid=nic,values=(phy,nic,w[0]['addr'],w[0]['type'],d,c))

    def _shutdown(self): pass
    def reset(self): pass

    def poll(self):
        """ checks for new interfaces """
        self.update()
        self.after(500,self.poll)

# View->DataBin
class DatabinPanel(gui.SimplePanel):
    """ DatabinPanel - displays a set of data bins for retrieved data storage """
    def __init__(self,tl,chief,conn):
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
        try:
            self._bins[b] = {'img':ImageTk.PhotoImage(Image.open('widgets/icons/bin%s.png'%b))}
        except:
            self._bins[b] = {'img':None}
            self._bins[b]['btn'] = ttk.Button(frm,text=b,command=self.donothing)
        else:
            self._bins[b]['btn'] = ttk.Button(frm,image=self._bins[b]['img'],
                                              command=lambda:self.viewquery(b))
        self._bins[b]['btn'].grid(row=0,column=wraith.BINS.index(b),sticky='w')

    def notifyclose(self,name):
        """ close the associated bin's cursor """
        self._curs[name].close()
        gui.SimplePanel.notifyclose(self,name)

    def viewquery(self,b):
        """ shows query panel for bin b """
        # notify user if not connected to database
        if not self._chief.isconnected:
            self.warn("Disconnected","Cannot retrieve any records. Connect and try again")
            return

        panel = self.getpanels('query%s' % b,False)
        if not panel:
            curs = None
            try:
                curs = self._conn.cursor(cursor_factory=pextras.DictCursor)
            except:
                self.err("Unspecified Error","Cannot connect to database")
            else:
                t = tk.Toplevel()
                pnl = QueryPanel(t,self,"Query [bin %s]" % b,b,curs)
                self.addpanel(pnl.name,gui.PanelRecord(t,pnl,'query%s' % b))
                self._curs['query%s'%b] = curs
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

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
    def __init__(self,tl,parent,ttl,b,curs):
        """
         tl: Toplevel
         parent: our master panel
         ttl: title
         b: databin querying for
         curs: cursor for our queries
        """
        gui.SlavePanel.__init__(self,tl,parent,ttl,'widgets/icons/bin%s.png'%b,False)
        self._bin = b
        self._curs = curs
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
        self.trSession = ttk.Treeview(frmLS)
        self.trSession.grid(row=0,column=0,sticky='nwse')
        self.trSession.config(height=8)
        self.trSession.config(selectmode='extended')
        self.trSession['show'] = 'headings'
        vscroll = ttk.Scrollbar(frmLS,orient=tk.VERTICAL,command=self.trSession.yview)
        vscroll.grid(row=0,column=1,sticky='ns')
        self.trSession['yscrollcommand'] = vscroll.set
        # configure session tree's headers
        hdrs = ['ID','Host','Start','Frames']
        hdrlens = [gui.lenpix('000'),gui.lenpix('HOST'),
                   gui.lenpix('DDMMYY HHMM'),gui.lenpix('0000')]
        self.trSession['columns'] = hdrs
        for i in xrange(len(hdrs)):
            self.trSession.column(i,width=hdrlens[i],anchor=tk.CENTER)
            self.trSession.heading(i,text=hdrs[i])
        self._getsessions() # fill the session tree
        frmRP = ttk.LabelFrame(frmR,text='Period')
        frmRP.grid(row=0,column=0,sticky='nwse')
        ttk.Label(frmRP,text='YYYY-MM-DD').grid(row=0,column=1,sticky='ne')
        ttk.Label(frmRP,text='HH:MM:SS').grid(row=0,column=2,sticky='ne')
        ttk.Label(frmRP,text='From: ').grid(row=1,column=0,sticky='w')
        self.txtFromDate = ttk.Entry(frmRP,width=10)
        self.txtFromDate.grid(row=1,column=1,sticky='e')
        self.txtFromTime = ttk.Entry(frmRP,width=9)
        self.txtFromTime.grid(row=1,column=2,sticky='e')
        ttk.Button(frmRP,text='Now',width=4,
                  command=self.fromnow).grid(row=1,column=3,sticky='w')
        ttk.Label(frmRP,text='To: ').grid(row=2,column=0,sticky='w')
        self.txtToDate = ttk.Entry(frmRP,width=10)
        self.txtToDate.grid(row=2,column=1,sticky='e')
        self.txtToTime = ttk.Entry(frmRP,width=9)
        self.txtToTime.grid(row=2,column=2,sticky='e')
        ttk.Button(frmRP,text='Now',width=4,command=self.tonow).grid(row=2,column=3,sticky='w')
        self.vcollate = tk.IntVar()
        chkCollate = ttk.Checkbutton(frmRP,text="Collate",variable=self.vcollate).grid(row=3,column=0,sticky='nwse')

        # filter on frame
        frmFO = ttk.LabelFrame(frmR,text="Filter On")
        frmFO.grid(row=1,column=0,sticky='nwse')
        filters = ['Sensor','Signal','Traffic']
        self.vfilteron = []
        for i in xrange(3):
            self.vfilteron.append(tk.IntVar())
            ttk.Checkbutton(frmFO,text=filters[i],variable=self.vfilteron[i]).grid(row=0,column=i,sticky='w')

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
        self.txtSensorHost = ttk.Entry(frmSL,width=17)
        self.txtSensorHost.grid(row=1,column=1,sticky='e')
        self.vnothost = tk.IntVar()
        ttk.Checkbutton(frmSL,variable=self.vnothost).grid(row=1,column=2,sticky='w')
        ttk.Label(frmSL,text='NIC: ').grid(row=2,column=0,sticky='w')
        self.txtSensorNic = ttk.Entry(frmSL,width=10)
        self.txtSensorNic.grid(row=2,column=1,sticky='e')
        self.vnotnic = tk.IntVar()
        ttk.Checkbutton(frmSL,variable=self.vnotnic).grid(row=2,column=2,sticky='w')
        ttk.Label(frmSL,text='MAC: ').grid(row=3,column=0,sticky='w')
        self.txtSensorMac = ttk.Entry(frmSL,width=17)
        self.txtSensorMac.grid(row=3,column=1,sticky='e')
        self.vnotmac = tk.IntVar()
        ttk.Checkbutton(frmSL,variable=self.vnotmac).grid(row=3,column=2,sticky='w')
        ttk.Label(frmSL,text='Spoof: ').grid(row=4,column=0,sticky='w')
        self.txtSensorSpoof = ttk.Entry(frmSL,width=17)
        self.txtSensorSpoof.grid(row=4,column=1,sticky='e')
        self.vnotspoof = tk.IntVar()
        ttk.Checkbutton(frmSL,variable=self.vnotspoof).grid(row=4,column=2,sticky='w')
        ttk.Label(frmSL,text='STDs: ').grid(row=5,column=0,sticky='w')
        self.txtSensorStd = ttk.Entry(frmSL,width=5)
        self.txtSensorStd.grid(row=5,column=1,sticky='e')
        self.vnotstd = tk.IntVar()
        ttk.Checkbutton(frmSL,variable=self.vnotstd).grid(row=5,column=2,sticky='w')
        ttk.Label(frmSL,text='Driver: ').grid(row=6,column=0,sticky='w')
        self.txtSensorDriver = ttk.Entry(frmSL,width=17)
        self.txtSensorDriver.grid(row=6,column=1,sticky='e')
        self.vnotdriver = tk.IntVar()
        ttk.Checkbutton(frmSL,variable=self.vnotdriver).grid(row=6,column=2,sticky='w')
        self.vrecon = tk.IntVar()
        ttk.Checkbutton(frmSL,text='Recon',variable=self.vrecon).grid(row=1,column=3,sticky='w')
        self.vcoll = tk.IntVar()
        ttk.Checkbutton(frmSL,text='Collection',variable=self.vcoll).grid(row=2,column=3,sticky='w')
        frmSRL = ttk.LabelFrame(frmSR,text='Location')
        frmSRL.grid(row=0,column=1,sticky='nwse')
        ttk.Label(frmSRL,text='Center PT: ').grid(row=1,column=5,sticky='w')
        self.txtCenterPT = ttk.Entry(frmSRL,width=15)
        self.txtCenterPT.grid(row=1,column=6,sticky='w')
        ttk.Label(frmSRL,text='Radius: (m)').grid(row=2,column=5,sticky='w')
        self.txtRadius = ttk.Entry(frmSRL,width=6)
        self.txtRadius.grid(row=2,column=6,sticky='w')
        self.vfixed = tk.IntVar()
        ttk.Checkbutton(frmSRL,text='Fixed',variable=self.vfixed).grid(row=3,column=5,sticky='w')
        self.vdynamic = tk.IntVar()
        ttk.Checkbutton(frmSRL,text='Dynamic',variable=self.vdynamic).grid(row=3,column=6,sticky='w')
        nb.add(frmS,text='Sensor')
        # signal tab
        frmSig = ttk.Frame(nb)
        frmSigParams = ttk.Frame(frmSig)
        frmSigParams.grid(row=0,column=0,sticky='nwse')
        ttk.Label(frmSigParams,text='Not').grid(row=0,column=2,sticky='w')
        ttk.Label(frmSigParams,text='Standard(s)').grid(row=1,column=0,sticky='w')
        self.txtSignalStd = ttk.Entry(frmSigParams,width=10)
        self.txtSignalStd.grid(row=1,column=1,sticky='e')
        self.vnotstd = tk.IntVar()
        ttk.Checkbutton(frmSigParams,variable=self.vnotstd).grid(row=1,column=2,sticky='w')
        ttk.Label(frmSigParams,text='Rate(s)').grid(row=2,column=0,sticky='w')
        self.txtSignalRate = ttk.Entry(frmSigParams,width=10)
        self.txtSignalRate.grid(row=2,column=1,sticky='e')
        self.vnotrate = tk.IntVar()
        ttk.Checkbutton(frmSigParams,variable=self.vnotrate).grid(row=2,column=2,sticky='w')
        ttk.Label(frmSigParams,text='Channel(s)').grid(row=3,column=0,sticky='w')
        self.txtSignalCh = ttk.Entry(frmSigParams,width=10)
        self.txtSignalCh.grid(row=3,column=1,sticky='e')
        self.vnotch = tk.IntVar()
        ttk.Checkbutton(frmSigParams,variable=self.vnotch).grid(row=3,column=2,sticky='w')
        # flags and channel flags are contained in separate frames
        # we want rows of 4 flags
        frmSigFlags = ttk.LabelFrame(frmSig,text='Flags')
        frmSigFlags.grid(row=1,column=0,sticky='nwse')
        self.vrtflags = []
        for i in xrange(len(RT_FLAGS)):
            self.vrtflags.append(tk.IntVar())
            chk = ttk.Checkbutton(frmSigFlags,text=RT_FLAGS[i],variable=self.vrtflags[i])
            chk.grid(row=(i / 4),column=(i % 4),sticky='w')
        ttk.Separator(frmSigFlags,orient=tk.VERTICAL).grid(row=0,column=4,rowspan=2,sticky='ns')
        self.vandorrtflags = tk.IntVar()
        ttk.Radiobutton(frmSigFlags,text='AND',variable=self.vandorrtflags,value=0).grid(row=0,column=5,sticky='w')
        ttk.Radiobutton(frmSigFlags,text='OR',variable=self.vandorrtflags,value=1).grid(row=1,column=5,sticky='w')
        frmSigChFlags = ttk.LabelFrame(frmSig,text="Channel Flags")
        frmSigChFlags.grid(row=2,column=0,sticky='nwse')
        self.vchflags = []
        for i in xrange(len(CH_FLAGS)):
            self.vchflags.append(tk.IntVar())
            chk = ttk.Checkbutton(frmSigChFlags,text=CH_FLAGS[i],variable=self.vchflags[i])
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
        self.vhtonly = tk.IntVar()
        ttk.Checkbutton(frmSigHT1,text="HT Only",variable=self.vhtonly).grid(row=0,column=0,sticky='nwse')
        self.vampdu = tk.IntVar()
        ttk.Checkbutton(frmSigHT1,text='AMPDU',variable=self.vampdu).grid(row=0,column=1,sticky='nwse')
        frmSigHTBW = ttk.Frame(frmSigHT)
        frmSigHTBW.grid(row=1,column=0,sticky='nwse')
        ttk.Label(frmSigHTBW,text='BW: ').grid(row=0,column=0,sticky='nwse')
        self.vbws = []
        for i in xrange(len(BW_FLAGS)):
            self.vbws.append(tk.IntVar())
            chk = ttk.Checkbutton(frmSigHTBW,text=BW_FLAGS[i],variable=self.vbws[i])
            chk.grid(row=0,column=i+1,sticky='w')
        frmSigHT2 = ttk.Frame(frmSigHT)
        frmSigHT2.grid(row=2,column=0)
        ttk.Label(frmSigHT2,text='GI: ').grid(row=0,column=0,sticky='nwse')
        self.vgis = [tk.IntVar(),tk.IntVar()]
        ttk.Checkbutton(frmSigHT2,text='Short',variable=self.vgis[0]).grid(row=0,column=1,sticky='nwse')
        ttk.Checkbutton(frmSigHT2,text='Long',variable=self.vgis[1]).grid(row=1,column=1,sticky='nwse')
        self.vformats = [tk.IntVar(),tk.IntVar()]
        ttk.Label(frmSigHT2,text='Format: ').grid(row=0,column=2,sticky='nwse')
        ttk.Checkbutton(frmSigHT2,text='Mixed',variable=self.vgis[0]).grid(row=0,column=3,sticky='nwse')
        ttk.Checkbutton(frmSigHT2,text='Greenfield',variable=self.vgis[1]).grid(row=1,column=3,sticky='nwse')
        frmSigHT3 = ttk.Frame(frmSigHT)
        frmSigHT3.grid(row=3,column=0,sticky='nwse')
        ttk.Label(frmSigHT3,text='MCS Index: ').grid(row=0,column=0,sticky='nwse')
        self.txtIndex = ttk.Entry(frmSigHT3,width=15)
        self.txtIndex.grid(row=0,column=1,sticky='nwse')
        nb.add(frmSig,text='Signal')
        # traffic
        frmT = ttk.Frame(nb)
        frmL = ttk.Frame(frmT)
        frmL.grid(row=0,column=0,sticky='nwse')
        self.trTypes = ttk.Treeview(frmL)
        self.trTypes.grid(row=0,column=0,sticky='nwse')
        self.trTypes.config(height=10)
        self.trTypes.config(selectmode='extended')
        self.trTypes['show'] = 'tree'
        vscroll = ttk.Scrollbar(frmL,orient=tk.VERTICAL,command=self.trTypes.yview)
        vscroll.grid(row=0,column=1,sticky='ns')
        self.trTypes['yscrollcommand'] = vscroll.set
        # fill the tree
        self.trTypes['columns'] = ('one',)
        self.trTypes.column('#0',stretch=0,width=15,anchor='w')
        self.trTypes.column('one',stretch=0,width=140,anchor='w')
        self.trTypes.insert('','end',iid='MGMT',values=('MGMT',))
        for mgmt in mpdu.ST_MGMT_TYPES:
            if mgmt == 'rsrv': continue
            self.trTypes.insert('MGMT','end',iid="%s.%s" % ('MGMT',mgmt),values=(mgmt,))
        self.trTypes.insert('','end',iid='CTRL',values=('CTRL',))
        for ctrl in mpdu.ST_CTRL_TYPES:
            if ctrl == 'rsrv': continue
            self.trTypes.insert('CTRL','end',iid="%s.%s" % ('CTRL',ctrl),values=(ctrl,))
        self.trTypes.insert('','end',iid='DATA',values=('DATA',))
        for data in mpdu.ST_DATA_TYPES:
            if data == 'rsrv': continue
            self.trTypes.insert('DATA','end',iid="%s.%s" % ('DATA',data),values=(data,))
        frmR = ttk.Frame(frmT)
        frmR.grid(row=0,column=1,sticky='nswe')
        frmRFC = ttk.LabelFrame(frmR,text="Frame Control Frames")
        frmRFC.grid(row=0,column=0,sticky='nwse')
        self.vfcflags = []
        for i in xrange(len(FC_FLAGS)):
            self.vfcflags.append(tk.IntVar())
            chk = ttk.Checkbutton(frmRFC,text=FC_FLAGS[i],variable=self.vfcflags[i])
            chk.grid(row=(i / 4),column=(i % 4),sticky='w')
        ttk.Separator(frmRFC,orient=tk.VERTICAL).grid(row=0,column=4,rowspan=2,sticky='ns')
        self.vandorfcflags = tk.IntVar()
        ttk.Radiobutton(frmRFC,text='AND',variable=self.vandorfcflags,value=0).grid(row=0,column=5,sticky='w')
        ttk.Radiobutton(frmRFC,text='OR',variable=self.vandorfcflags,value=1).grid(row=1,column=5,sticky='w')

        frmRA = ttk.LabelFrame(frmR,text='HW ADDR')
        frmRA.grid(row=1,column=0,sticky='nwse')
        ttk.Label(frmRA,text='Single: ').grid(row=0,column=0,sticky='nwse')
        self.txtHWAddr = ttk.Entry(frmRA,width=17)
        self.txtHWAddr.grid(row=0,column=1,sticky='nwse')
        ttk.Label(frmRA,text='File: ').grid(row=1,column=0,sticky='nwse')
        self.txtSelFile = ttk.Entry(frmRA,width=20)
        self.txtSelFile.grid(row=1,column=1,sticky='ne')
        ttk.Button(frmRA,text='Browse',width=6,command=self.browse).grid(row=1,column=2,sticky='nw')
        ttk.Button(frmRA,text='Clear',width=6,command=self.clearselfile).grid(row=1,column=3,sticky='nw')
        ttk.Label(frmRA,text='Limit To: ').grid(row=2,column=0)
        frmRAL = ttk.Frame(frmRA,border=0)
        frmRAL.grid(row=2,column=1,columnspan=3)
        self.vlimitto = []
        for i in xrange(4):
            self.vlimitto.append(tk.IntVar())
            chk = ttk.Checkbutton(frmRAL,text="ADDR %d" % (i+1),variable=self.vlimitto[i])
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
        self.menubar.add_separator()
        self.menubar.add_command(label='Quit',command=self.close)
        self.menubar.add_cascade(label='File',menu=self.mnuFile)
        try:
            self.master.config(menu=self.menubar)
        except AttributeError:
            self.master.tk.call(self.master,"config","-menu",self.menubar)

    # virtual implementations

    def _shutdown(self): pass
    def reset(self): pass
    def update(self): pass

    # menu callbacks

    def qrysave(self): pass

    def qryload(self): pass

    # button callbacks

    def query(self):
        """ queries db for specified data """
        if self._validate():
            pass

    def widgetreset(self):
        """ clears all user inputed data """
        # time periods
        for s in self.trSession.selection(): self.trSession.selection_remove(s)
        self.txtFromDate.delete(0,tk.END)
        self.txtFromTime.delete(0,tk.END)
        self.txtToDate.delete(0,tk.END)
        self.txtToTime.delete(0,tk.END)
        self.vcollate.set(0)
        # sensor
        self.txtSensorHost.delete(0,tk.END)
        self.vnothost.set(0)
        self.txtSensorNic.delete(0,tk.END)
        self.vnotnic.set(0)
        self.txtSensorMac.delete(0,tk.END)
        self.vnotmac.set(0)
        self.txtSensorSpoof.delete(0,tk.END)
        self.vnotspoof.set(0)
        self.txtSensorStd.delete(0,tk.END)
        self.vnotstd.set(0)
        self.txtSensorDriver.delete(0,tk.END)
        self.vnotdriver.set(0)
        self.vrecon.set(0)
        self.vcoll.set(0)
        self.txtCenterPT.delete(0,tk.END)
        self.txtRadius.delete(0,tk.END)
        self.vfixed.set(0)
        self.vdynamic.set(0)
        # signal
        self.txtSignalStd.delete(0,tk.END)
        self.vnotstd.set(0)
        self.txtSignalRate.delete(0,tk.END)
        self.vnotrate.set(0)
        self.txtSignalCh.delete(0,tk.END)
        self.vnotch.set(0)
        for chk in self.vrtflags: chk.set(0)
        self.vandorrtflags.set(0)
        for chk in self.vchflags: chk.set(0)
        self.vandorchflags.set(0)
        self.vhtonly.set(0)
        self.vampdu.set(0)
        for chk in self.vbws: chk.set(0)
        for chk in self.vgis: chk.set(0)
        for chk in self.vformats: chk.set(0)
        self.txtIndex.delete(0,tk.END)
        # traffic
        for s in self.trTypes.selection(): self.trTypes.selection_remove(s)
        for chk in self.vfcflags: chk.set(0)
        self.vandorfcflags.set(0)
        self.txtHWAddr.delete(0,tk.END)
        self.txtSelFile.delete(0,tk.END)
        for chk in self.vlimitto: chk.set(0)

    def fromnow(self):
        """assign now() to the from entries """
        d,t = timestamps.ts2iso(time.time()).split('T') # split isoformat on 'T'
        t = t[:8]                                       # drop the microseconds
        self.txtFromDate.delete(0,tk.END)               # delete from entries
        self.txtFromDate.insert(0,d)                    # and add now
        self.txtFromTime.delete(0,tk.END)
        self.txtFromTime.insert(0,t)

    def tonow(self):
        """ assign now() to the to entries """
        d,t = timestamps.ts2iso(time.time()).split('T') # split isoformat on 'T'
        t = t[:8]                                       # drop the microseconds
        self.txtToDate.delete(0,tk.END)                 # delete from entries
        self.txtToDate.insert(0,d)                      # and add now
        self.txtToTime.delete(0,tk.END)
        self.txtToTime.insert(0,t)

    def browse(self):
        """ open a file browsing dialog for selector file """
        fpath = tkFD.askopenfilename(title="Open Selector File",
                                     filetypes=[("Text Files","*.txt"),
                                                ("Selector Files","*.sel")],
                                     parent=self)
        self.clearselfile()
        self.txtSelFile.insert(0,fpath)

    def clearselfile(self):
        """ clear the selection file """
        self.txtSelFile.delete(0,tk.END)

    # private helper functions

    def _validate(self):
        """
         validates all entries
         NOTE: this does not validate for non-sensical queries i.e. those that
         will never return results
        """
        # period
        d = self.txtFromDate.get()
        if d and not timestamps.validdate(d):
            self.err("Invalid Input","From date is not valid")
            return False
        t = self.txtFromTime.get()
        if t and not timestamps.validtime(t):
            return False
        d = self.txtToDate.get()
        if d and not timestamps.validdate(d):
            self.err("Invalid Input","To date is not valid")
            return False
        t = self.txtToTime.get()
        if t and not timestamps.validtime(t):
            return False

        # only validate sensor entries if 'enabled'
        if self.vfilteron[0]:
            # allow all in host, nic, driver
            mac = self.txtSensorMac.get().upper()
            if mac and re.match(MACADDR,mac) is None:
                self.err("Invalid Input","MAC addr %s is not valid" % mac)
                return False
            mac = self.txtSensorSpoof.get().upper()
            if mac and re.match(MACADDR,mac) is None:
                self.err("Invalid Input","Spoof addr %s is not valid" % mac)
                return False
            stds = self.txtSensorStd.get().split(',')
            if stds and stds != ['']:
                for std in stds:
                    if not std in ['a','b','g','n','ac']:
                        self.err("Invalid Input","Invalid standard specifier %s" % std)
                        return False
            cp = self.txtCenterPT.get()
            if cp and not landnav.validMGRS(cp):
                self.err("Invalid Input","Center point is not a valid MGRS location")
                return False

        # # only validate signal entries if 'enabled'
        if self.vfilteron[1]:
            stds = self.txtSignalStd.get().split(',')
            if stds and stds != ['']:
                for std in stds:
                    if not std in ['a','b','g','n','ac']:
                        self.err("Invalid Input","Invalid standard specifier %s" % std)
                        return False
            rs = self.txtSignalRate.get().split(',')
            if rs and rs != ['']:
                try:
                    map(float,rs)
                except ValueError:
                    self.err("Invalid Input","Rate(s) must be numeric")
                    return False
            if not parsechlist(self.txtSignalCh.get(),'scan'):
                self.err("Invalid Input","Invalid channel(s0 specification")
                return False
            mis = self.txtIndex.get().split(',')
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
        if self.vfilteron[2]:
            mac = self.txtHWAddr.get().upper()
            if mac and re.match(MACADDR,mac) is None:
                self.err("Invalid Input","HW Addr %s is not valid" % mac)
                return False
            # check file path and file
            fin = None
            fpath = None
            try:
                fpath = self.txtSelFile.get()
                fin = open(fpath,'r')
                ss = fin.read().split(',')
                for s in ss:
                    if re.match(MACADDR,s.strip()) is None:
                        self.err("Invalid Input","Selector file %s has invalid data %s" % (fpath,s))
                        return False
            except IOError:
                self.err("Invalid Input","Select file %s does not exist" % fpath)
                return False
            else:
                if fin: fin.close()
        return True

    def _getsessions(self):
        """ retrieve all sessions and add to tree """
        sql1 = "SELECT session_id,hostname,ip,lower(period) FROM sensor;"
        sql2 = "SELECT count(id) FROM frame WHERE sid=%s;"
        self._curs.execute(sql1)
        ss = self._curs.fetchall()
        for s in ss:
            self._curs.execute(sql2,(s['session_id'],))
            fc = self._curs.fetchone()
            self.trSession.insert('','end',iid=str(s['session_id']),
                                  values=(s['session_id'],
                                  s['hostname'],
                                  s['lower'].strftime("%d%m%y %H%M%S"),
                                  fc['count']))

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
        self.txtHost = ttk.Entry(frmSS,width=15)
        self.txtHost.grid(row=0,column=1,sticky='e')
        ttk.Label(frmSS,text=' ').grid(row=0,column=2) # separator
        ttk.Label(frmSS,text='Port: ').grid(row=0,column=3,sticky='w')
        self.txtPort = ttk.Entry(frmSS,width=5)
        self.txtPort.grid(row=0,column=4,sticky='w')
        ttk.Label(frmSS,text='DB: ').grid(row=1,column=0,sticky='w')
        self.txtDB = ttk.Entry(frmSS,width=10)
        self.txtDB.grid(row=1,column=1,sticky='w')
        ttk.Label(frmSS,text='User: ').grid(row=1,column=3,sticky='w')
        self.txtUser = ttk.Entry(frmSS,width=10)
        self.txtUser.grid(row=1,column=4,sticky='e')
        ttk.Label(frmSS,text=' ').grid(row=1,column=5) # separator
        ttk.Label(frmSS,text='PWD: ').grid(row=1,column=6,sticky='w')
        self.txtPWD = ttk.Entry(frmSS,width=10)
        self.txtPWD.grid(row=1,column=7,sticky='w')

        # SSE Configuration
        frmS = ttk.LabelFrame(frm,text='SSE')
        frmS.grid(row=1,column=0,sticky='nwse')
        ttk.Label(frmS,text='Packets: ').grid(row=0,column=0,sticky='w')
        self.vsave = tk.IntVar()
        ttk.Checkbutton(frmS,
                        text="Save",
                        variable=self.vsave,
                        command=self.cb).grid(row=0,column=1,sticky='w')
        self.vprivate = tk.IntVar()
        self.chkPrivate = ttk.Checkbutton(frmS,text="Private",
                                          variable=self.vprivate)
        self.chkPrivate.grid(row=0,column=2,sticky='e')
        ttk.Label(frmS,text='Path: ').grid(row=0,column=3,sticky='w')
        self.txtPCAPPath = ttk.Entry(frmS,width=25)
        self.txtPCAPPath.grid(row=0,column=4)
        ttk.Label(frmS,text="Max Size: ").grid(row=1,column=1,sticky='w')
        self.txtMaxSz = ttk.Entry(frmS,width=4)
        self.txtMaxSz.grid(row=1,column=2,sticky='w')
        ttk.Label(frmS,text="Max Files: ").grid(row=1,column=3,sticky='w')
        self.txtMaxFiles = ttk.Entry(frmS,width=4)
        self.txtMaxFiles.grid(row=1,column=4,columnspan=2,sticky='w')
        ttk.Label(frmS,text='Threads: ').grid(row=2,column=0,sticky='w')
        ttk.Label(frmS,text='Store: ').grid(row=2,column=1,sticky='w')
        self.txtNumStore = ttk.Entry(frmS,width=2)
        self.txtNumStore.grid(row=2,column=2,sticky='w')
        ttk.Label(frmS,text='Extract: ').grid(row=2,column=3,sticky='w')
        self.txtNumExtract = ttk.Entry(frmS,width=2)
        self.txtNumExtract.grid(row=2,column=4,sticky='w')

        # OUI Configuration
        frmO = ttk.Frame(frm)
        frmO.grid(row=2,column=0,sticky='nwse')
        ttk.Label(frmO,text='OUI Path: ').grid(row=0,column=0,sticky='w')
        self.txtOUIPath = ttk.Entry(frmO,width=50)
        self.txtOUIPath.grid(row=0,column=1,sticky='e')

    def cb(self):
        """ Save Checkbutton callback: disable/enable Save options as necessary """
        if self.vsave.get(): state = tk.NORMAL
        else: state = tk.DISABLED
        self.chkPrivate.configure(state=state)
        self.txtPCAPPath.configure(state=state)
        self.txtMaxSz.configure(state=state)
        self.txtMaxFiles.configure(state=state)

    def _initialize(self):
        """ insert values from config file into entry boxes """
        conf = ConfigParser.RawConfigParser()
        if not conf.read(wraith.NIDUSCONF):
            self.err("File Not Found","nidus.conf was not found")
            return

        # in case the conf file is invalid, set to empty if not present
        # storage server
        self.txtHost.delete(0,tk.END)
        if conf.has_option('Storage','host'):
            self.txtHost.insert(0,conf.get('Storage','host'))

        self.txtPort.delete(0,tk.END)
        if conf.has_option('Storage','port'):
            self.txtPort.insert(0,conf.get('Storage','port'))

        self.txtDB.delete(0,tk.END)
        if conf.has_option('Storage','db'):
            self.txtDB.insert(0,conf.get('Storage','db'))

        self.txtUser.delete(0,tk.END)
        if conf.has_option('Storage','user'):
            self.txtUser.insert(0,conf.get('Storage','user'))

        self.txtPWD.delete(0,tk.END)
        if conf.has_option('Storage','pwd'):
            self.txtPWD.insert(0,conf.get('Storage','pwd'))

        # SSE section
        try:
            save = int(conf.getboolean('SSE','save'))
            private = int(conf.getboolean('SSE','save_private'))
        except:
            save = 0
            private = 0
        self.txtPCAPPath.delete(0,tk.END)
        if conf.has_option('SSE','save_path'):
            self.txtPCAPPath.insert(0,conf.get('SSE','save_path'))
        self.txtMaxSz.delete(0,tk.END)
        if conf.has_option('SSE','save_maxsize'):
            self.txtMaxSz.insert(0,conf.get('SSE','save_maxsize'))
        self.txtMaxFiles.delete(0,tk.END)
        if conf.has_option('SSE','save_maxfiles'):
            self.txtMaxFiles.insert(0,conf.get('SSE','save_maxfiles'))
        self.txtNumStore.delete(0,tk.END)
        if conf.has_option('SSE','store_threads'):
            self.txtNumStore.insert(0,conf.get('SSE','store_threads'))
        else: self.txtNumStore.insert(0,'2')
        self.txtNumExtract.delete(0,tk.END)
        if conf.has_option('SSE','extract_threads'):
            self.txtNumExtract.insert(0,conf.get('SSE','extract_threads'))
        else: self.txtNumExtract.insert(0,'2')

        # disable/enable as needed
        if save: state = tk.NORMAL
        else: state = tk.DISABLED
        self.chkPrivate.configure(state=state)
        self.txtPCAPPath.configure(state=state)
        self.txtMaxSz.configure(state=state)
        self.txtMaxFiles.configure(state=state)

        # OUI section
        self.txtOUIPath.delete(0,tk.END)
        if conf.has_option('OUI','path'):
            self.txtOUIPath.insert(0,conf.get('OUI','Path'))
        else: self.txtOUIPath.insert(0,'/etc/aircrack-ng/airodump-ng-oui.txt')

    def _validate(self):
        """ validate entries """
        # storage server
        host = self.txtHost.get()
        if re.match(IPADDR,host) is None and host != 'localhost':
            self.err("Invalid Input","Host %s is not valid" % host)
            return False
        port = self.txtPort.get()
        try:
            port = int(port)
            if port < 1024 or port > 65535: raise RuntimeError("")
        except:
            self.err("Invalid Input","Port must be a number between 1024 and 65535")
            return False
        if len(self.txtDB.get()) < 1 or len(self.txtDB.get()) > 15:
            self.err("Invalid Input","DB name must be between 1 and 15 characters")
            return False
        if len(self.txtUser.get()) < 1 or len(self.txtUser.get()) > 15:
            self.err("Invalid Input","User name must be between 1 and 15 characters")
            return False
        if len(self.txtPWD.get()) < 1 or len(self.txtPWD.get()) > 15:
            self.err("Invalid Input","Password must be between 1 and 15 characters")
            return False

        # if not saving pcaps, we ignore pcap options
        if self.vsave.get():
            # for the pcap directory, convert to absolute path before checking existence
            pPCAP = self.txtPCAPPath.get()
            if not os.path.isabs(pPCAP):
                pPCAP = os.path.abspath(os.path.join('nidus',pPCAP))
            if not os.path.exists(pPCAP):
                self.err("Invalid Input","PCAP directory %s does not exist" % pPCAP)
                return False
            try:
                if int(self.txtMaxSz.get()) < 1:
                    self.err("Invalid Input","Max Size must be >= 1")
                    return False
            except ValueError:
                self.err("Invalid Input","Max Size must be an integer")
                return False
            try:
                if int(self.txtMaxFiles.get()) < 1:
                    self.err("Invalid Input","Max Files must be >= 1")
                    return False
            except ValueError:
                self.err("Invalid Input","Max files must be an integer")
                return False
        try:
            st = int(self.txtNumStore.get())
            if st < 1 or st > 10:
                self.err("Invalid Input","Number of store threads must be between 1 and 10")
                return False
        except ValueError:
            self.err("Invalid Input","Number of store threads must be an integer")
            return False
        try:
            et = int(self.txtNumExtract.get())
            if et < 1 or et > 10:
                self.err("Invalid Input","Number of extract threads must be between 1 and 10")
                return False
        except ValueError:
            self.err("Invalid Input","Number of extract threads must be an integer")
            return False
        if not os.path.isfile(self.txtOUIPath.get()):
            self.err("Invalid Input","OUI file %s is not valid" % self.txtOUIPath.get())
            return False
        return True

    def _write(self):
        """ write entry inputs to config file """
        fout = None
        try:
            cp = ConfigParser.ConfigParser()
            cp.add_section('SSE')
            cp.set('SSE','save','yes' if self.vsave.get() else 'no')
            cp.set('SSE','save_private','yes' if self.vprivate.get() else 'no')
            cp.set('SSE','save_path',self.txtPCAPPath.get())
            cp.set('SSE','save_maxsize',self.txtMaxSz.get())
            cp.set('SSE','save_maxfiles',self.txtMaxFiles.get())
            cp.set('SSE','store_threads',self.txtNumStore.get())
            cp.set('SSE','extract_threads',self.txtNumExtract.get())
            cp.add_section('OUI')
            cp.set('OUI','path',self.txtOUIPath.get())
            fout = open(wraith.NIDUSCONF,'w')
            cp.write(fout)
            fout.close()
        except IOError as e:
            self.err("File Error","Error <%s> writing to config file" % e)
        except ConfigParser.Error as e:
            self.err("Configuration Error","Error <%s> writing to config file" % e)
        else:
            self.info('Success',"Changes will take effect on next start")
        finally:
            if fout: fout.close()

# DySKT->Config
class DySKTConfigException(Exception): pass
class DySKTConfigPanel(gui.ConfigPanel):
    """ Display Nidus Configuration Panel """
    def __init__(self,tl,chief):
        gui.ConfigPanel.__init__(self,tl,chief,"Configure DySKT")

    def _makegui(self,frm):
        """ set up entry widgets """
        nb = ttk.Notebook(frm)
        nb.grid(row=0,column=0,sticky='nwse')

        # Recon Tab Configuration
        frmR = ttk.Frame(nb)
        ttk.Label(frmR,text='NIC: ').grid(row=0,column=0,sticky='nw')
        self.txtReconNic = ttk.Entry(frmR,width=5)
        self.txtReconNic.grid(row=0,column=1,sticky='nw')
        ttk.Label(frmR,text=' ').grid(row=0,column=2,sticky='w')
        ttk.Label(frmR,text='Spoof: ').grid(row=0,column=3,sticky='nw')
        self.txtReconSpoof = ttk.Entry(frmR,width=17)
        self.txtReconSpoof.grid(row=0,column=4,sticky='nw')
        ttk.Label(frmR,text='Desc: ').grid(row=1,column=0,sticky='nw')
        self.txtReconDesc = tk.Text(frmR,width=42,height=3)
        self.txtReconDesc.grid(row=1,column=1,columnspan=4,sticky='e')

        # ANTENNA SUB SECTION
        frmRA = ttk.LabelFrame(frmR,text='Antennas')
        frmRA.grid(row=2,column=0,columnspan=5,sticky='nwse')
        # ANTENNA SUBSECTION
        ttk.Label(frmRA,text="Number: ").grid(row=0,column=0,sticky='w')
        self.txtReconAntNum = ttk.Entry(frmRA,width=2)
        self.txtReconAntNum.grid(row=0,column=1,sticky='w')
        ttk.Label(frmRA,text='Gain: ').grid(row=1,column=0,sticky='w')
        self.txtReconAntGain = ttk.Entry(frmRA,width=7)
        self.txtReconAntGain.grid(row=1,column=1,sticky='w')
        ttk.Label(frmRA,text=" ").grid(row=1,column=2)
        ttk.Label(frmRA,text="Type: ").grid(row=1,column=3,sticky='e')
        self.txtReconAntType = ttk.Entry(frmRA,width=15)
        self.txtReconAntType.grid(row=1,column=4,sticky='e')
        ttk.Label(frmRA,text='Loss: ').grid(row=2,column=0,sticky='w')
        self.txtReconAntLoss = ttk.Entry(frmRA,width=7)
        self.txtReconAntLoss.grid(row=2,column=1,sticky='w')
        ttk.Label(frmRA,text=" ").grid(row=2,column=2)
        ttk.Label(frmRA,text="XYZ: ").grid(row=2,column=3,sticky='e')
        self.txtReconAntXYZ = ttk.Entry(frmRA,width=15)
        self.txtReconAntXYZ.grid(row=2,column=4,sticky='e')
        # SCAN PATTERN SUB SECTION
        frmRS = ttk.LabelFrame(frmR,text='Scan Pattern')
        frmRS.grid(row=3,column=0,columnspan=5,sticky='nwse')
        ttk.Label(frmRS,text="Dwell: ").grid(row=0,column=0,sticky='w')
        self.txtReconScanDwell = ttk.Entry(frmRS,width=5)
        self.txtReconScanDwell.grid(row=0,column=2,sticky='w')
        ttk.Label(frmRS,text=" ").grid(row=0,column=3)
        ttk.Label(frmRS,text="Start: ").grid(row=0,column=4,sticky='e')
        self.txtReconScanStart = ttk.Entry(frmRS,width=3)
        self.txtReconScanStart.grid(row=0,column=5,sticky='w')
        ttk.Label(frmRS,text="Scan: ").grid(row=1,column=0,sticky='w')
        self.txtReconScanScan = ttk.Entry(frmRS,width=12)
        self.txtReconScanScan.grid(row=1,column=2,sticky='w')
        ttk.Label(frmRS,text=" ").grid(row=1,column=3)
        ttk.Label(frmRS,text="Pass: ").grid(row=1,column=4,sticky='w')
        self.txtReconScanPass = ttk.Entry(frmRS,width=12)
        self.txtReconScanPass.grid(row=1,column=5,sticky='e')
        nb.add(frmR,text='Recon')

        # Collection Tab Configuration
        frmC = ttk.Frame(nb)
        ttk.Label(frmC,text='NIC: ').grid(row=0,column=0,sticky='nw')
        self.txtCollectionNic = ttk.Entry(frmC,width=5)
        self.txtCollectionNic.grid(row=0,column=1,sticky='nw')
        ttk.Label(frmC,text=' ').grid(row=0,column=2,sticky='w')
        ttk.Label(frmC,text='Spoof: ').grid(row=0,column=3,sticky='wn')
        self.txtCollectionSpoof = ttk.Entry(frmC,width=17)
        self.txtCollectionSpoof.grid(row=0,column=4,sticky='nw')
        ttk.Label(frmC,text='Desc: ').grid(row=1,column=0,sticky='nw')
        self.txtCollectionDesc = tk.Text(frmC,width=42,height=3)
        self.txtCollectionDesc.grid(row=1,column=1,columnspan=4,sticky='e')

        # ANTENNA SUB SECTION
        frmCA = ttk.LabelFrame(frmC,text='Antennas')
        frmCA.grid(row=2,column=0,columnspan=5,sticky='nwse')
        # ANTENNA SUBSECTION
        ttk.Label(frmCA,text="Number: ").grid(row=0,column=0,sticky='w')
        self.txtCollectionAntNum = ttk.Entry(frmCA,width=2)
        self.txtCollectionAntNum.grid(row=0,column=1,sticky='w')
        ttk.Label(frmCA,text='Gain: ').grid(row=1,column=0,sticky='w')
        self.txtCollectionAntGain = ttk.Entry(frmCA,width=7)
        self.txtCollectionAntGain.grid(row=1,column=1,sticky='w')
        ttk.Label(frmCA,text=" ").grid(row=1,column=2)
        ttk.Label(frmCA,text="Type: ").grid(row=1,column=3,sticky='e')
        self.txtCollectionAntType = ttk.Entry(frmCA,width=15)
        self.txtCollectionAntType.grid(row=1,column=4,sticky='e')
        ttk.Label(frmCA,text='Loss: ').grid(row=2,column=0,sticky='w')
        self.txtCollectionAntLoss = ttk.Entry(frmCA,width=7)
        self.txtCollectionAntLoss.grid(row=2,column=1,sticky='w')
        ttk.Label(frmCA,text=" ").grid(row=2,column=2)
        ttk.Label(frmCA,text="XYZ: ").grid(row=2,column=3,sticky='e')
        self.txtCollectionAntXYZ = ttk.Entry(frmCA,width=15)
        self.txtCollectionAntXYZ.grid(row=2,column=4,sticky='e')
        # SCAN PATTERN SUB SECTION
        frmCS = ttk.LabelFrame(frmC,text='Scan Pattern')
        frmCS.grid(row=3,column=0,columnspan=5,sticky='nwse')
        ttk.Label(frmCS,text="Dwell: ").grid(row=0,column=0,sticky='w')
        self.txtCollectionScanDwell = ttk.Entry(frmCS,width=5)
        self.txtCollectionScanDwell.grid(row=0,column=2,sticky='w')
        ttk.Label(frmCS,text=" ").grid(row=0,column=3)
        ttk.Label(frmCS,text="Start: ").grid(row=0,column=4,sticky='e')
        self.txtCollectionScanStart = ttk.Entry(frmCS,width=3)
        self.txtCollectionScanStart.grid(row=0,column=5,sticky='w')
        ttk.Label(frmCS,text="Scan: ").grid(row=1,column=0,sticky='w')
        self.txtCollectionScanScan = ttk.Entry(frmCS,width=12)
        self.txtCollectionScanScan.grid(row=1,column=2,sticky='w')
        ttk.Label(frmCS,text=" ").grid(row=1,column=3)
        ttk.Label(frmCS,text="Pass: ").grid(row=1,column=4,sticky='w')
        self.txtCollectionScanPass = ttk.Entry(frmCS,width=12)
        self.txtCollectionScanPass.grid(row=1,column=5,sticky='e')
        nb.add(frmC,text='Collection')

        # GPS Tab Configuration
        # use a checkbutton & two subframes to differentiate betw/ fixed & dyanmic
        frmG = ttk.Frame(nb)
        self.vfixed = tk.IntVar()
        ttk.Checkbutton(frmG,
                        text="Fixed",
                        variable=self.vfixed,
                        command=self.gpscb).grid(row=0,column=0,sticky='w')

        # separate dynamic and fixed
        frmGF = ttk.LabelFrame(frmG,text='Fixed')
        frmGF.grid(row=1,column=0,sticky='nw')
        ttk.Label(frmGF,text="Lat: ").grid(row=0,column=0,sticky='w')
        self.txtLat = ttk.Entry(frmGF,width=10)
        self.txtLat.grid(row=0,column=1,sticky='w')
        ttk.Label(frmGF,text="Lon: ").grid(row=1,column=0,sticky='w')
        self.txtLon = ttk.Entry(frmGF,width=10)
        self.txtLon.grid(row=1,column=1,sticky='w')
        ttk.Label(frmGF,text="Alt: ").grid(row=2,column=0,sticky='w')
        self.txtAlt = ttk.Entry(frmGF,width=5)
        self.txtAlt.grid(row=2,column=1,sticky='w')
        ttk.Label(frmGF,text="Heading: ").grid(row=3,column=0,sticky='w')
        self.txtHeading = ttk.Entry(frmGF,width=3)
        self.txtHeading.grid(row=3,column=1,sticky='w')
        frmGD = ttk.LabelFrame(frmG,text='Dynamic')
        frmGD.grid(row=1,column=2,sticky='ne')
        ttk.Label(frmGD,text="Port: ").grid(row=0,column=0,sticky='w')
        self.txtGPSPort = ttk.Entry(frmGD,width=5)
        self.txtGPSPort.grid(row=0,column=1,sticky='w')
        ttk.Label(frmGD,text="Dev ID: ").grid(row=1,column=0,sticky='w')
        self.txtDevID = ttk.Entry(frmGD,width=9)
        self.txtDevID.grid(row=1,column=1,sticky='w')
        ttk.Label(frmGD,text="Poll: ").grid(row=2,column=0,sticky='w')
        self.txtPoll = ttk.Entry(frmGD,width=5)
        self.txtPoll.grid(row=2,column=1,sticky='w')
        ttk.Label(frmGD,text="EPX: ").grid(row=3,column=0,sticky='w')
        self.txtEPX = ttk.Entry(frmGD,width=5)
        self.txtEPX.grid(row=3,column=1,sticky='w')
        ttk.Label(frmGD,text="EPY: ").grid(row=4,column=0,sticky='w')
        self.txtEPY = ttk.Entry(frmGD,width=5)
        self.txtEPY.grid(row=4,column=1,sticky='w')
        nb.add(frmG,text='GPS')

        # misc tab
        frmM = ttk.Frame(nb)
        frmMS = ttk.LabelFrame(frmM,text='Storage')
        frmMS.grid(row=0,column=0,sticky='w')
        ttk.Label(frmMS,text=' Host: ').grid(row=0,column=0)
        self.txtStoreHost = ttk.Entry(frmMS,width=15)
        self.txtStoreHost.grid(row=0,column=1)
        ttk.Label(frmMS,text=' Port: ').grid(row=0,column=2)
        self.txtStorePort = ttk.Entry(frmMS,width=5)
        self.txtStorePort.grid(row=0,column=3)
        frmML = ttk.LabelFrame(frmM,text='Local')
        frmML.grid(row=1,column=0,sticky='w')
        ttk.Label(frmML,text="Region: ").grid(row=0,column=0,sticky='w')
        self.txtRegion = ttk.Entry(frmML,width=3)
        self.txtRegion.grid(row=0,column=1,sticky='w')
        ttk.Label(frmML,text=" C2C: ").grid(row=0,column=2,sticky='w')
        self.txtC2CPort = ttk.Entry(frmML,width=5)
        self.txtC2CPort.grid(row=0,column=3,sticky='w')
        nb.add(frmM,text='Misc.')

    def _initialize(self):
        """ insert values from config file into entry boxes """
        cp = ConfigParser.RawConfigParser()
        if not cp.read(wraith.DYSKTCONF):
            self.err("File Not Found","File dyskt.conf was not found")
            return

        # start by reading the recon radio details
        self.txtReconNic.delete(0,tk.END)
        if cp.has_option('Recon','nic'):
            self.txtReconNic.insert(0,cp.get('Recon','nic'))
        self.txtReconSpoof.delete(0,tk.END)
        if cp.has_option('Recon','spoof'):
            self.txtReconSpoof.insert(0,cp.get('Recon','spoof'))
        self.txtReconDesc.delete(1.0,tk.END)
        if cp.has_option('Recon','desc'):
            self.txtReconDesc.insert(tk.END,cp.get('Recon','desc'))
        self.txtReconAntNum.delete(0,tk.END)
        if cp.has_option('Recon','antennas'):
            self.txtReconAntNum.insert(0,cp.get('Recon','antennas'))
        self.txtReconAntGain.delete(0,tk.END)
        if cp.has_option('Recon','antenna_gain'):
            self.txtReconAntGain.insert(0,cp.get('Recon','antenna_gain'))
        self.txtReconAntType.delete(0,tk.END)
        if cp.has_option('Recon','antenna_type'):
            self.txtReconAntType.insert(0,cp.get('Recon','antenna_type'))
        self.txtReconAntLoss.delete(0,tk.END)
        if cp.has_option('Recon','antenna_loss'):
            self.txtReconAntLoss.insert(0,cp.get('Recon','antenna_loss'))
        self.txtReconAntXYZ.delete(0,tk.END)
        if cp.has_option('Recon','antenna_xyz'):
            self.txtReconAntXYZ.insert(0,cp.get('Recon','antenna_xyz'))
        self.txtReconScanDwell.delete(0,tk.END)
        if cp.has_option('Recon','dwell'):
            self.txtReconScanDwell.insert(0,cp.get('Recon','dwell'))
        self.txtReconScanStart.delete(0,tk.END)
        if cp.has_option('Recon','scan_start'):
            self.txtReconScanStart.insert(0,cp.get('Recon','scan_start'))
        self.txtReconScanScan.delete(0,tk.END)
        if cp.has_option('Recon','scan'):
            self.txtReconScanScan.insert(0,cp.get('Recon','scan'))
        self.txtReconScanPass.delete(0,tk.END)
        if cp.has_option('Recon','pass'):
            self.txtReconScanPass.insert(0,cp.get('Recon','pass'))

        # then the collection radio details
        self.txtCollectionNic.delete(0,tk.END)
        if cp.has_option('Collection','nic'):
            self.txtCollectionNic.insert(0,cp.get('Collection','nic'))
        self.txtCollectionSpoof.delete(0,tk.END)
        if cp.has_option('Collection','spoof'):
            self.txtCollectionSpoof.insert(0,cp.get('Collection','spoof'))
        self.txtCollectionDesc.delete(1.0,tk.END)
        if cp.has_option('Collection','desc'):
            self.txtCollectionDesc.insert(tk.END,cp.get('Collection','desc'))
        self.txtCollectionAntNum.delete(0,tk.END)
        if cp.has_option('Collection','antennas'):
            self.txtCollectionAntNum.insert(0,cp.get('Collection','antennas'))
        self.txtCollectionAntGain.delete(0,tk.END)
        if cp.has_option('Collection','antenna_gain'):
            self.txtCollectionAntGain.insert(0,cp.get('Collection','antenna_gain'))
        self.txtCollectionAntType.delete(0,tk.END)
        if cp.has_option('Collection','antenna_type'):
            self.txtCollectionAntType.insert(0,cp.get('Collection','antenna_type'))
        self.txtCollectionAntLoss.delete(0,tk.END)
        if cp.has_option('Collection','antenna_loss'):
            self.txtCollectionAntLoss.insert(0,cp.get('Collection','antenna_loss'))
        self.txtCollectionAntXYZ.delete(0,tk.END)
        if cp.has_option('Collection','antenna_xyz'):
            self.txtCollectionAntXYZ.insert(0,cp.get('Collection','antenna_xyz'))
        self.txtCollectionScanDwell.delete(0,tk.END)
        if cp.has_option('Collection','dwell'):
            self.txtCollectionScanDwell.insert(0,cp.get('Collection','dwell'))
        self.txtCollectionScanStart.delete(0,tk.END)
        if cp.has_option('Collection','scan_start'):
            self.txtCollectionScanStart.insert(0,cp.get('Collection','scan_start'))
        self.txtCollectionScanScan.delete(0,tk.END)
        if cp.has_option('Collection','scan'):
            self.txtCollectionScanScan.insert(0,cp.get('Collection','scan'))
        self.txtCollectionScanPass.delete(0,tk.END)
        if cp.has_option('Collection','pass'):
            self.txtCollectionScanPass.insert(0,cp.get('Collection','pass'))

        # gps entries
        try:
            fixed = int(cp.getboolean('GPS','fixed'))
        except:
            fixed = 0
        self.vfixed.set(fixed)
        self.txtLat.delete(0,tk.END)
        if cp.has_option('GPS','lat'): self.txtLat.insert(0,cp.get('GPS','lat'))
        self.txtLon.delete(0,tk.END)
        if cp.has_option('GPS','lon'): self.txtLon.insert(0,cp.get('GPS','lon'))
        self.txtAlt.delete(0,tk.END)
        if cp.has_option('GPS','alt'): self.txtAlt.insert(0,cp.get('GPS','alt'))
        self.txtHeading.delete(0,tk.END)
        if cp.has_option('GPS','heading'): self.txtHeading.insert(0,cp.get('GPS','heading'))
        self.txtGPSPort.delete(0,tk.END)
        if cp.has_option('GPS','port'): self.txtGPSPort.insert(0,cp.get('GPS','port'))
        self.txtDevID.delete(0,tk.END)
        if cp.has_option('GPS','devid'): self.txtDevID.insert(0,cp.get('GPS','devid'))
        self.txtPoll.delete(0,tk.END)
        if cp.has_option('GPS','poll'): self.txtPoll.insert(0,cp.get('GPS','poll'))
        self.txtEPX.delete(0,tk.END)
        if cp.has_option('GPS','epx'): self.txtEPX.insert(0,cp.get('GPS','epx'))
        self.txtEPY.delete(0,tk.END)
        if cp.has_option('GPS','epy'): self.txtEPY.insert(0,cp.get('GPS','epy'))
        self.gpscb() # enable/disable entries

        # misc entries
        self.txtStoreHost.delete(0,tk.END)
        if cp.has_option('Storage','host'): self.txtStoreHost.insert(0,cp.get('Storage','host'))
        self.txtStorePort.delete(0,tk.END)
        if cp.has_option('Storage','port'): self.txtStorePort.insert(0,cp.get('Storage','port'))
        self.txtRegion.delete(0,tk.END)
        if cp.has_option('Local','region'): self.txtRegion.insert(0,cp.get('Local','region'))
        self.txtC2CPort.delete(0,tk.END)
        if cp.has_option('Local','C2C'): self.txtC2CPort.insert(0,cp.get('Local','C2C'))

    def _validate(self):
        """ validate entries """
        # start with the recon radio details
        nic = self.txtReconNic.get()
        if not nic:
            self.err("Invalid Recon Input","Radio nic must be specified")
            return False
        elif not nic in iwt.wifaces():
            self.warn("Not Found","Recon radio may not be wireless")
        spoof = self.txtReconSpoof.get().upper()
        if spoof and re.match(MACADDR,spoof) is None:
            self.err("Invalid Recon Input","Spoofed MAC addr %s is not valid")
            return False

        # process antennas, if # > 0 then force validation of all antenna widgets
        if self.txtReconAntNum.get():
            try:
                nA = int(self.txtReconAntNum.get())
                if nA:
                    try:
                        if len(map(float,self.txtReconAntGain.get().split(','))) != nA:
                            raise DySKTConfigException("Number of gain is invalid")
                    except ValueError:
                        raise DySKTConfigException("Gain must be float or list of floats")
                    if len(self.txtReconAntType.get().split(',')) != nA:
                        raise DySKTConfigException("Number of types is invalid")
                    try:
                        if len(map(float,self.txtReconAntLoss.get().split(','))) != nA:
                            raise DySKTConfigException("Number of loss is invalid")
                    except:
                        raise DySKTConfigException("Loss must be float or list of floats")
                    try:
                        xyzs = self.txtReconAntXYZ.get().split(',')
                        if len(xyzs) != nA:
                            raise DySKTConfigException("Number of xyz is invalid")
                        for xyz in xyzs:
                            xyz = xyz.split(':')
                            if len(xyz) != 3:
                                raise DySKTConfigException("XYZ must be three integers")
                            map(int,xyz)
                    except ValueError:
                        raise DySKTConfigException('XYZ must be integer')
            except ValueError:
                self.err("Invalid Recon Input","Number of antennas must be numeric")
                return False
            except DySKTConfigException as e:
                self.err("Invalid Recon Input",e)
                return False

        # process scan patterns
        try:
            float(self.txtReconScanDwell.get())
        except:
            self.err("Invalid Recon Input","Scan dwell must be float")
            return False
        start = self.txtReconScanStart.get()
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
            parsechlist(self.txtReconScanScan.get(),'scan')
            parsechlist(self.txtReconScanPass.get(),'pass')
        except ValueError as e:
            self.err("Invalid Recon Input",e)
            return False

        # then collection radio details
        nic = self.txtCollectionNic.get()
        if nic:
            if not nic in iwt.wifaces(): self.warn("Not Found","Radio may not be wireless")
            spoof = self.txtCollectionSpoof.get().upper()
            if spoof and re.match(MACADDR,spoof) is None:
                self.err("Invalid Colleciton Input","Spoofed MAC address is not valid")
                return False

            # process the antennas - if antenna number is > 0 then force validation of
            # all antenna widgets
            if self.txtCollectionAntNum.get():
                try:
                    nA = int(self.txtCollectionAntNum.get())
                    if nA:
                        try:
                            if len(map(float,self.txtCollectionAntGain.get().split(','))) != nA:
                                raise DySKTConfigException("Number of gain is invalid")
                        except ValueError:
                            raise DySKTConfigException("Gain must be float or list of floats")
                        if len(self.txtCollectionAntType.get().split(',')) != nA:
                            raise DySKTConfigException("Number of types is invalid")
                        try:
                            if len(map(float,self.txtCollectionAntLoss.get().split(','))) != nA:
                                raise DySKTConfigException("Number of loss is invalid")
                        except:
                            raise DySKTConfigException("Loss must be float or list of floats")
                        try:
                            xyzs = self.txtCollectionAntXYZ.get().split(',')
                            if len(xyzs) != nA:
                                raise DySKTConfigException("Number of xyz is invalid")
                            for xyz in xyzs:
                                xyz = xyz.split(':')
                                if len(xyz) != 3:
                                    raise DySKTConfigException("XYZ must be three integers")
                                map(int,xyz)
                        except ValueError:
                            raise DySKTConfigException("XYZ must be integer")
                except ValueError:
                    self.err("Invalid Collection Input","Number of antennas must be numeric")
                    return False
                except DySKTConfigException as e:
                    self.err("Invalid Collection Input",e)
                    return False

            # process scan patterns
            try:
                float(self.txtCollectionScanDwell.get())
            except:
                self.err("Invalid Collection Input", "Scan dwell must be float")
                return False
            start = self.txtCollectionScanStart.get()
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
                self.err("Invalid Collection Input", "Scan start must be integer")
                return False
            except Exception as e:
                self.err("Invalid Collection Input",e)
                return False
            try:
                parsechlist(self.txtCollectionScanScan.get(),'scan')
                parsechlist(self.txtCollectionScanPass.get(),'pass')
            except ValueError as e:
                self.err("Invalid Collection Input",e)
                return False

        # gps - only process enabled widgets
        if self.vfixed.get():
            # fixed is set
            try:
                float(self.txtLat.get())
                float(self.txtLon.get())
            except:
                self.err("Invalid GPS Input","Lat/Lon must be floats")
                return False
            try:
                float(self.txtAlt.get())
            except:
                self.err("Invalid GPS Input","Altitude must be a float")
                return False
            hdg = self.txtHeading.get()
            try:
                hdg = int(hdg)
                if hdg < 0 or hdg > 360: raise RuntimeError("")
            except:
                self.err("Invalid GPS Input","Heading must be an integer between 0 and 360")
                return False
        else:
            # dynamic is set
            port = self.txtGPSPort.get()
            try:
                port = int(port)
                if port < 1024 or port > 65535: raise RuntimeError("")
            except:
                self.err("Invalid GPS Input","Device port must be a number between 1024 and 65535")
                return False
            if re.match(GPSDID,self.txtDevID.get().upper()) is None:
                self.err("Invalid GPS Input","GPS Dev ID is invalid")
                return False
            try:
                if float(self.txtPoll.get()) < 0: raise RuntimeError("")
            except:
                self.err("Invalid GPS Input","Poll must be numeric and greater than 0")
                return False
            try:
                float(self.txtEPX.get())
                float(self.txtEPY.get())
            except:
                self.err("Invalid GPS Input","EPX/EPY must be numeric or 'inf'")
                return False

        # misc entries
        host = self.txtStoreHost.get()
        if re.match(IPADDR,host) is None and host != 'localhost':
            self.err("Invalid Storage Input","Host is not a valid address")
        port = self.txtStorePort.get()
        try:
            port = int(port)
            if port < 1024 or port > 65535: raise RuntimeError("")
        except ValueError:
            self.err("Invalid Storage Input","Host Port must be a number between 1024 and 65535")
            return False
        region = self.txtRegion.get()
        if region and len(region) != 2:
            self.err("Invalid Local Input","Region must be 2 characters")
            return False
        port = self.txtC2CPort.get()
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
            cp.set('Recon','nic',self.txtReconNic.get())
            if self.txtReconSpoof.get(): cp.set('Recon','spoof',self.txtReconSpoof.get())
            nA = self.txtReconAntNum.get()
            if nA:
                cp.set('Recon','antennas',self.txtReconAntNum.get())
                cp.set('Recon','antenna_gain',self.txtReconAntGain.get())
                cp.set('Recon','antenna_loss',self.txtReconAntLoss.get())
                cp.set('Recon','antenna_type',self.txtReconAntType.get())
                cp.set('Recon','antenna_xyz',self.txtReconAntXYZ.get())
            desc = self.txtReconDesc.get(1.0,tk.END).strip()
            if desc: cp.set('Recon','desc',desc)
            cp.set('Recon','dwell',self.txtReconScanDwell.get())
            cp.set('Recon','scan',self.txtReconScanScan.get())
            cp.set('Recon','pass',self.txtReconScanPass.get())
            cp.set('Recon','scan_start',self.txtReconScanStart.get())
            if self.txtCollectionNic.get():
                cp.add_section('Collection')
                cp.set('Collection','nic',self.txtCollectionNic.get())
                if self.txtCollectionSpoof.get():
                    cp.set('Collection','spoof',self.txtCollectionSpoof.get())
                nA = self.txtCollectionAntNum.get()
                if nA:
                    cp.set('Collection','antennas',self.txtCollectionAntNum.get())
                    cp.set('Collection','antenna_gain',self.txtCollectionAntGain.get())
                    cp.set('Collection','antenna_loss',self.txtCollectionAntLoss.get())
                    cp.set('Collection','antenna_type',self.txtCollectionAntType.get())
                    cp.set('Collection','antenna_xyz',self.txtCollectionAntXYZ.get())
                desc = self.txtCollectionDesc.get(1.0,tk.END).strip()
                if desc: cp.set('Collection','desc',desc)
                cp.set('Collection','dwell',self.txtCollectionScanDwell.get())
                cp.set('Collection','scan',self.txtCollectionScanScan.get())
                cp.set('Collection','pass',self.txtCollectionScanPass.get())
                cp.set('Collection','scan_start',self.txtCollectionScanStart.get())
            cp.add_section('GPS')
            fixed = self.vfixed.get()
            cp.set('GPS','fixed','yes' if fixed else 'no')
            if fixed:
                cp.set('GPS','lat',self.txtLat.get())
                cp.set('GPS','lon',self.txtLon.get())
                cp.set('GPS','alt',self.txtAlt.get())
                cp.set('GPS','heading',self.txtHeading.get())
            else:
                cp.set('GPS','port',self.txtGPSPort.get())
                cp.set('GPS','devid',self.txtDevID.get())
                cp.set('GPS','poll',self.txtPoll.get())
                cp.set('GPS','epx',self.txtEPX.get())
                cp.set('GPS','epy',self.txtEPY.get())
            cp.add_section('Storage')
            cp.set('Storage','host',self.txtStoreHost.get())
            cp.set('Storage','port',self.txtStorePort.get())
            region = self.txtRegion.get()
            c2cport = self.txtC2CPort.get()
            if region or c2cport:
                cp.add_section('Local')
                if region: cp.set('Local','region',region)
                if c2cport: cp.set('Local','C2C',c2cport)
            fout = open(wraith.DYSKTCONF,'w')
            cp.write(fout)
            fout.close()
        except IOError as e:
            self.err("File Error","Error <%s> writing to config file" % e)
        except ConfigParser.Error as e:
            self.err("Configuration Error","Error <%s> writing to config file" % e)
        else:
            self.info('Success',"Restart for changes to take effect")
        finally:
            if fout: fout.close()

    def gpscb(self):
        """ enable/disable gps entries as necessary """
        if self.vfixed.get():
            # fixed is on enable only fixed entries
            self.txtLat.configure(state=tk.NORMAL)
            self.txtLon.configure(state=tk.NORMAL)
            self.txtAlt.configure(state=tk.NORMAL)
            self.txtHeading.configure(state=tk.NORMAL)
            self.txtGPSPort.configure(state=tk.DISABLED)
            self.txtDevID.configure(state=tk.DISABLED)
            self.txtPoll.configure(state=tk.DISABLED)
            self.txtEPX.configure(state=tk.DISABLED)
            self.txtEPY.configure(state=tk.DISABLED)
        else:
            # fixed is off enable only dynamic entries
            self.txtLat.configure(state=tk.DISABLED)
            self.txtLon.configure(state=tk.DISABLED)
            self.txtAlt.configure(state=tk.DISABLED)
            self.txtHeading.configure(state=tk.DISABLED)
            self.txtGPSPort.configure(state=tk.NORMAL)
            self.txtDevID.configure(state=tk.NORMAL)
            self.txtPoll.configure(state=tk.NORMAL)
            self.txtEPX.configure(state=tk.NORMAL)
            self.txtEPY.configure(state=tk.NORMAL)

# Help-->About
class AboutPanel(gui.SimplePanel):
    """ AboutPanel - displays a simple About Panel """
    def __init__(self,tl,chief):
        gui.SimplePanel.__init__(self,tl,chief,"About Wraith","widgets/icons/about.png")

    def _body(self):
        self.logo = ImageTk.PhotoImage(Image.open("widgets/icons/splash.png"))
        ttk.Label(self,image=self.logo).grid(row=0,column=0,sticky='n')
        ttk.Label(self,text="wraith-rt %s" % wraith.__version__,
                  font=("Roman",16,'bold')).grid(row=1,column=0,sticky='n')
        ttk.Label(self,justify=tk.CENTER,
                  text="Wireless reconnaissance, collection,\nassault and exploitation toolkit",
                  font=("Roman",8,'bold')).grid(row=2,column=0,sticky='n')
        ttk.Label(self,text="Copyright %s %s %s" % (COPY,
                                                   wraith.__date__.split(' ')[1],
                                                   wraith.__email__),
                  font=('Roman',8,'bold')).grid(row=3,column=0,sticky='n')