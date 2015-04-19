#!/usr/bin/env python
""" subpanels.py - defines the subpanels called by the wraith Master panel """

__name__ = 'subpanels'
__license__ = 'GPL v3.0'
__version__ = '0.0.3'
__revdate__ = 'March 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import os                                  # file info etc
import re                                  # reg. exp.
import Tkinter as tk                       # gui constructs
import ttk                                 # ttk widgets
import mgrs                                # for mgrs2latlon conversions etc
import math                                # for conversions, calculations
from PIL import Image,ImageTk              # image input & support
import ConfigParser                        # config file parsing
import wraith                              # version info & constants
import wraith.widgets.panel as gui         # graphics suite
from wraith.radio.iw import IW_CHWS        # channel width list
from wraith.radio.iwtools import wifaces   # check nic validity
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

    def _body(self,frm):
        """ creates the body """
        # create the location frame
        frmGeo = ttk.LabelFrame(frm,text='Location')
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
        frmPwr = ttk.LabelFrame(frm,text='Power')
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
        frmBtns = ttk.Frame(frm,borderwidth=0)
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
                                   ('RF (MHz)',4,'float')],
                         'answer':("17.3*(math.sqrt(($0*$1)/($2/1000)*($0+$1)))",'m'),
                         'rc':[3]},
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

    def _body(self,frm):
        """ creates the body """
        # entries frame
        frmEnt = ttk.Frame(frm,borderwidth=0)
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
        frmAns = ttk.Frame(frm,borderwidth=0)
        frmAns.grid(row=1,column=0,sticky='n')
        ttk.Label(frmAns,text="Answer: ").grid(row=0,column=0)
        ttk.Label(frmAns,width=20,textvariable=self._ans).grid(row=0,column=1)
        frmBtns = ttk.Frame(frm,borderwidth=0)
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

# View->DataBin
class DatabinPanel(gui.SimplePanel):
    """ DatabinPanel - displays a set of data bins for retrieved data storage """
    def __init__(self,tl,chief):
        self._bins = {}
        gui.SimplePanel.__init__(self,tl,chief,"Databin","widgets/icons/db.png")

    def donothing(self): pass

    def _body(self,frm):
        """ creates the body """
        # add the bin buttons
        # NOTE: for whatever reason, trying to creat individual viewquery functions
        # for each bin b results in issues, if the button w/ function call is
        # created directly in the loop. But, if a function is called that creates
        # the button w/ function, there is no issue
        for b in wraith.BINS: self._makebin(frm,b)

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

    def viewquery(self,b):
        """ shows query panel for bin b """
        # notify user if not connected to database
        #if not self._chief.isconnected:
        #    self.err("Disconnected","Will not be able to retrieve any records. Connect and try again")
        #    return

        panel = self.getpanels('query%s' % b,False)
        if not panel:
            t = tk.Toplevel()
            pnl = QueryPanel(t,self,"Query [bin %s]" % b,b)
            self.addpanel(pnl.name,gui.PanelRecord(t,pnl,'niduslog'))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

# Databin->Query
class QueryPanel(gui.SlavePanel):
    """Display query for data panel """
    def __init__(self,tl,parent,ttl,b):
        """
         tl: Toplevel
         parent: our master panel
         ttl: title
         b: databin querying for
        """
        gui.SlavePanel.__init__(self,tl,parent,ttl,'widgets/icons/bin%s.png'%b,False)
        self._bin = b
        self._makegui()

    def _makegui(self):
        """ make the query gui """
        # three frames 1) data, 2) Filters, 3) buttons
        self.grid(sticky='nwse')

        # session/time frame
        # two subframes: 'left' Session(s) Frame has a tree view of sessions, 'right'
        # Period has entries to select from and to date/times. Additionally, below
        # the period subframe is a checkbox to enable data collation
        frmD = ttk.LabelFrame(self,text='Data',borderwidth=1)
        frmD.grid(row=0,column=0,sticky='nwse')
        frmDS = ttk.LabelFrame(frmD,text='Session(s)')
        frmDS.grid(row=0,column=0,rowspan=2,sticky='nwse')
        # make session tree w/ attached vertical scrollbar
        self.treeSession = ttk.Treeview(frmDS)
        self.treeSession.grid(row=0,column=0,sticky='nwse')
        self.treeSession.config(height=6)
        self.treeSession.config(selectmode='extended')
        self.treeSession['show'] = 'headings'
        vscroll = ttk.Scrollbar(frmDS,orient=tk.VERTICAL,command=self.treeSession.yview)
        vscroll.grid(row=0,column=1,sticky='ns')
        self.treeSession['yscrollcommand'] = vscroll.set
        # configure session tree's headers
        hdrs = ['ID','Host','From','To','Frames']
        self.treeSession['columns'] = hdrs
        for i in xrange(len(hdrs)):
            self.treeSession.column(i,width=gui.lenpix(hdrs[i])+10,anchor=tk.CENTER)
            self.treeSession.heading(i,text=hdrs[i])
        frmDP = ttk.LabelFrame(frmD,text='Period')
        frmDP.grid(row=0,column=1,sticky='nwse')
        ttk.Label(frmDP,text='DD-MON-YY').grid(row=0,column=1,sticky='ne')
        ttk.Label(frmDP,text='HH:MM:SS').grid(row=0,column=2,sticky='ne')
        ttk.Label(frmDP,text='From: ').grid(row=1,column=0,sticky='w')
        self.txtFromDate = ttk.Entry(frmDP,width=9)
        self.txtFromDate.grid(row=1,column=1,sticky='e')
        self.txtFromTime = ttk.Entry(frmDP,width=9)
        self.txtFromTime.grid(row=1,column=2,sticky='e')
        ttk.Label(frmDP,text='To: ').grid(row=2,column=0,sticky='w')
        self.txtToDate = ttk.Entry(frmDP,width=9)
        self.txtToDate.grid(row=2,column=1,sticky='e')
        self.txtToTime = ttk.Entry(frmDP,width=9)
        self.txtToTime.grid(row=2,column=2,sticky='e')
        self.cvar = tk.IntVar()
        self.chkCollate = ttk.Checkbutton(frmD,text="Collate",variable=self.cvar)
        self.chkCollate.grid(row=1,column=1,sticky='nw')

        # filters frame (For now, allow filters on Radio,Frame,Signal,Traffic,STA
        frmF = ttk.LabelFrame(self,text='Filters')
        frmF.grid(row=1,column=0,sticky='nwse')
        nb = ttk.Notebook(frmF)
        nb.grid(row=0,column=0,sticky='nwse')

        # Radio tab
        frmR = ttk.Frame(nb)
        nb.add(frmR,text='Radio')

        frmF = ttk.Frame(nb)
        nb.add(frmF,text='Frame')

        frmS = ttk.Frame(nb)
        nb.add(frmS,text='Signal')

        frmT = ttk.Frame(nb)
        nb.add(frmT,text='Traffic')

        frmSta = ttk.Frame(nb)
        nb.add(frmSta,text='Station')

        # 3 buttons query,reset and cancel
        frmB = ttk.Frame(self)
        frmB.grid(row=2,column=0,sticky='ns')
        ttk.Button(frmB,text='Query',width=6,command=self.query).grid(row=0,column=0)
        ttk.Button(frmB,text='Reset',width=6,command=self.widgetreset).grid(row=0,column=1)
        ttk.Button(frmB,text='Cancel',width=6,command=self.delete).grid(row=0,column=2)

    # virtual implementations

    def _shutdown(self): pass
    def reset(self): pass
    def update(self): pass

    # button callbacks

    def query(self):
        """ queries db for specified data """
        if self._validate():
            pass

    def widgetreset(self):
        """ clears all user inputed data """
        # clear all tree selections (selection_toggle? selection_remove?)
        self.txtFromDate.delete(0,tk.END)
        self.txtFromTime.delete(0,tk.END)
        self.txtToDate.delete(0,tk.END)
        self.txtToTime.delete(0,tk.END)
        self.cvar.set(0)

    # private helper functions

    def _validate(self):
        """ validates all entries """
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

        return True

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
        self.svar = tk.IntVar()
        self.chkSave = ttk.Checkbutton(frmS,text="Save",variable=self.svar,command=self.cb)
        self.chkSave.grid(row=0,column=1,sticky='w')
        self.pvar = tk.IntVar()
        self.chkPrivate = ttk.Checkbutton(frmS,text="Private",variable=self.pvar)
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
        if self.svar.get(): state = tk.NORMAL
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
        if self.svar.get():
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
            cp.set('SSE','save','yes' if self.svar.get() else 'no')
            cp.set('SSE','save_private','yes' if self.pvar.get() else 'no')
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
        self.gvar = tk.IntVar()
        self.chkFixed = ttk.Checkbutton(frmG,text="Fixed",variable=self.gvar,command=self.gpscb)
        self.chkFixed.grid(row=0,column=0,sticky='w')

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
        self.cvar = tk.IntVar()
        self.chkCollated = ttk.Checkbutton(frmMS,text='Collated',variable=self.cvar)
        self.chkCollated.grid(row=0,column=0,sticky='w')
        ttk.Label(frmMS,text=' Host: ').grid(row=0,column=1)
        self.txtStoreHost = ttk.Entry(frmMS,width=15)
        self.txtStoreHost.grid(row=0,column=2)
        ttk.Label(frmMS,text=' Port: ').grid(row=0,column=3)
        self.txtStorePort = ttk.Entry(frmMS,width=5)
        self.txtStorePort.grid(row=0,column=4)
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
        self.gvar.set(fixed)
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
        try:
            collated = int(cp.getboolean('Storage','collated'))
        except:
            collated = 0
        self.cvar.set(collated)
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
        elif not nic in wifaces():
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
                if chw and not chw in IW_CHWS:
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
            if not nic in wifaces(): self.warn("Not Found","Radio may not be wireless")
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
                    if chw and not chw in IW_CHWS:
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
        if self.gvar.get():
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
            fixed = self.gvar.get()
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
            cp.set('Storage','collated','yes' if self.cvar.get() else 'no')
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
        if self.gvar.get():
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

    def _body(self,frm):
        self.logo = ImageTk.PhotoImage(Image.open("widgets/icons/wraith-banner.png"))
        ttk.Label(frm,background='white',image=self.logo).grid(row=0,column=0,sticky='n')
        ttk.Label(frm,text="wraith-rt %s" % wraith.__version__,
                  font=("Roman",16,'bold')).grid(row=1,column=0,sticky='n')
        ttk.Label(frm,text="Wireless reconnaissance, collection, assault and exploitation toolkit",
                  font=("Roman",8,'bold')).grid(row=2,column=0,sticky='n')
        ttk.Label(frm,text="Copyright %s %s %s" % (COPY,
                                                   wraith.__date__.split(' ')[1],
                                                   wraith.__email__),
                  font=('Roman',8,'bold')).grid(row=3,column=0,sticky='n')