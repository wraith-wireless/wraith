#!/usr/bin/env python
""" wraith-rt.py - defines the wraith gui

 TODO:
  1) make tkMessageBox,tkFileDialog and tkSimpleDialog derive match
    main color scheme
  4) move display of log panel to after intializiation() so that
     wraith panel is 'first', leftmost panel - will have to figure out
     how to save messages from init to later
  8) need to periodically recheck state -> status of postgres,nidusd and dyskt
  9) get log panel to scroll automatically
 10) add labels to frames
"""

__name__ = 'wraith-rt'
__license__ = 'GPL v3.0'
__version__ = '0.0.3'
__revdate__ = 'February 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import os                                  # file info etc
import re                                  # reg. exp.
import time                                # sleeping, timestamps
import psycopg2 as psql                    # postgresql api
import Tix                                 # Tix gui stuff
import tkMessageBox as tkMB                # info dialogs
from PIL import Image,ImageTk              # image input & support
import ConfigParser                        # config file parsing
import wraith                              # version info
import wraith.widgets.panel as gui         # graphics suite
from wraith.utils import bits              # bitmask functions
from wraith.utils import cmdline           # command line stuff
#from wraith.utils.timestamps import ts2iso # ts conversion
from wraith.radio.iwtools import wifaces   # check nic validity

#### CONSTANTS

_BINS_ = "ABCDEFG"                     # data bin ids
NIDUSLOG = '/var/log/wraith/nidus.log' # path to nidus log
DYSKTLOG = '/var/log/wraith/dyskt.log' # path to dyskt log
NIDUSPID = '/var/run/nidusd.pid'       # path to nidus pidfile
DYSKTPID = '/var/run/dysktd.pid'       # path to dyskt pidfile

# Validation reg. exp.
IPADDR = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$") # reg exp for ip addr
MACADDR = re.compile("^([0-9A-F]{2}:){5}([0-9A-F]{2})$")    # reg exp for mac addr (capital letters only)

################################################################################
# CHILD PANELS
################################################################################

class DataBinPanel(gui.SimplePanel):
    """ DataBinPanel - displays a set of data bins for retrieved data storage """
    def __init__(self,toplevel,chief):
        gui.SimplePanel.__init__(self,toplevel,chief,"Databin","widgets/icons/databin.png")

    def donothing(self): pass

    def _body(self):
        """ creates the body """
        self._bins = {}
        frm = Tix.Frame(self)
        frm.pack(side=Tix.TOP,expand=False)

        # add the bin buttons
        for b in _BINS_:
            try:
                self._bins[b] = {'img':ImageTk.PhotoImage(Image.open('widgets/icons/bin%s.png'%b))}
            except:
                self._bins[b] = {'img':None}
                self._bins[b]['btn'] = Tix.Button(frm,text=b,command=self.donothing)
            else:
                self._bins[b]['btn'] = Tix.Button(frm,image=self._bins[b]['img'],command=self.donothing)
            self._bins[b]['btn'].grid(row=0,column=_BINS_.index(b),sticky=Tix.W)

class AboutPanel(gui.SimplePanel):
    """ AboutPanel - displays a simple About Panel """
    def __init__(self,toplevel,chief):
        gui.SimplePanel.__init__(self,toplevel,chief,"About Wraith","widgets/icons/about.png")

    def _body(self):
        frm = Tix.Frame(self)
        frm.pack(side=Tix.TOP,fill=Tix.BOTH,expand=True)
        self.logo = ImageTk.PhotoImage(Image.open("widgets/icons/wraith-banner.png"))
        Tix.Label(frm,bg="white",image=self.logo).grid(row=0,column=0,sticky=Tix.N)
        Tix.Label(frm,
                  text="wraith-rt %s" % wraith.__version__,
                  fg="white",
                  font=("Roman",16,'bold')).grid(row=1,column=0,sticky=Tix.N)
        Tix.Label(frm,
                  text="Wireless assault, reconnaissance, collection and exploitation toolkit",
                  fg="white",
                  font=("Roman",8,'bold')).grid(row=2,column=0,sticky=Tix.N)

class WraithConfigPanel(gui.ConfigPanel):
    """ Display Wraith Configuration Panel """
    def __init__(self,toplevel,chief):
        gui.ConfigPanel.__init__(self,toplevel,chief,"Configure Wraith")

    def _makegui(self,frm):
        """ set up entry widgets """
        # Storage Configuration
        frmS = Tix.Frame(frm,borderwidth=2,relief='sunken')
        frmS.pack(side=Tix.TOP,fill=Tix.BOTH,expand=True)
        Tix.Label(frmS,text='STORAGE').grid(row=0,column=0,columnspan=2,sticky=Tix.W)
        Tix.Label(frmS,text='Host: ').grid(row=1,column=0,sticky=Tix.W)
        self.txtHost = Tix.Entry(frmS,width=15)
        self.txtHost.grid(row=1,column=1,sticky=Tix.E)
        Tix.Label(frmS,text='DB: ').grid(row=2,column=0,sticky=Tix.W)
        self.txtDB = Tix.Entry(frmS,width=15)
        self.txtDB.grid(row=2,column=1,sticky=Tix.E)
        Tix.Label(frmS,text='User: ').grid(row=3,column=0,sticky=Tix.W)
        self.txtUser = Tix.Entry(frmS,width=15)
        self.txtUser.grid(row=3,column=1,sticky=Tix.E)
        Tix.Label(frmS,text='PWD: ').grid(row=4,column=0,sticky=Tix.W)
        self.txtPWD = Tix.Entry(frmS,width=15)
        self.txtPWD.grid(row=4,column=1,sticky=Tix.E)

        # Policy Configuration
        frmP = Tix.Frame(frm,borderwidth=2,relief='sunken')
        frmP.pack(side=Tix.TOP,fill=Tix.BOTH,expand=True)
        Tix.Label(frmP,text='POLICY').grid(row=0,column=0,sticky=Tix.W)

        # polite
        Tix.Label(frmP,text="Polite:").grid(row=1,column=0,sticky=Tix.W)
        self.ptype = Tix.IntVar(self)
        self.rdoPoliteOn = Tix.Radiobutton(frmP,text='On',
                                           variable=self.ptype,value=1)
        self.rdoPoliteOn.grid(row=1,column=1,sticky=Tix.W)
        self.rdoPoliteOff = Tix.Radiobutton(frmP,text='Off',
                                            variable=self.ptype,value=0)
        self.rdoPoliteOff.grid(row=2,column=1,sticky=Tix.W)

        # separator label
        Tix.Label(frmP,text=" ").grid(row=1,column=2)

        # shutdown
        Tix.Label(frmP,text="Shutdown:").grid(row=1,column=3,sticky=Tix.W)
        self.stype = Tix.IntVar(self)
        self.rdoShutdownAuto = Tix.Radiobutton(frmP,text='Auto',
                                               variable=self.stype,value=1)
        self.rdoShutdownAuto.grid(row=1,column=4,sticky=Tix.W)
        self.rdoShutdownManual = Tix.Radiobutton(frmP,text='Manual',
                                                 variable=self.ptype,value=0)
        self.rdoShutdownManual.grid(row=2,column=4,sticky=Tix.W)

    def _initialize(self):
        """ insert values from config file into entry boxes """
        conf = ConfigParser.RawConfigParser()
        if not conf.read('wraith.conf'):
            tkMB.showerror("File Not Found","File wraith.conf was not found",
                           parent=self)
            return

        # in case the conf file is invalid, set to empty if not present
        self.txtHost.delete(0,Tix.END)
        if conf.has_option('Storage','host'):
            self.txtHost.insert(0,conf.get('Storage','host'))
        else: self.txtHost.insert(0,'')

        self.txtDB.delete(0,Tix.END)
        if conf.has_option('Storage','db'):
            self.txtDB.insert(0,conf.get('Storage','db'))
        else: self.txtDB.insert(0,'')

        self.txtUser.delete(0,Tix.END)
        if conf.has_option('Storage','user'):
            self.txtUser.insert(0,conf.get('Storage','user'))
        else: self.txtUser.insert(0,'')

        self.txtPWD.delete(0,Tix.END)
        if conf.has_option('Storage','pwd'):
            self.txtPWD.insert(0,conf.get('Storage','pwd'))
        else: self.txtPWD.insert(0,'')

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
            tkMB.showerror("Invalid Input",
                           "Host %s is not valid" % host,
                           parent=self)
            return False
        if len(self.txtDB.get()) < 1 or len(self.txtDB.get()) > 15:
            tkMB.showerror("Invalid Input",
                           "DB name must be between 1 and 15 characters",
                           parent=self)
            return False
        if len(self.txtUser.get()) < 1 or len(self.txtUser.get()) > 15:
            tkMB.showerror("Invalid Input",
                           "User name must be between 1 and 15 characters",
                           parent=self)
            return False
        if len(self.txtPWD.get()) < 1 or len(self.txtPWD.get()) > 15:
            tkMB.showerror("Invalid Input",
                           "Password must be between 1 and 15 characters",
                           parent=self)
            return False
        return True

    def _write(self):
        """ write entry inputs to config file """
        try:
            conf = ConfigParser.ConfigParser()

            # storage section
            conf.add_section('Storage')
            conf.set('Storage','host',self.txtHost.get())
            conf.set('Storage','db',self.txtDB.get())
            conf.set('Storage','user',self.txtUser.get())
            conf.set('Storage','pwd',self.txtUser.get())

            # policy section
            conf.add_section('Policy')
            conf.set('Policy','polite','on' if self.ptype else 'off')
            conf.set('Policy','shutdown','auto' if self.stype else 'manual')

            fout = open('wraith.conf','w')
            conf.write(fout)
            fout.close()
        except IOError as e:
            tkMB.showerror("File Error",
                           "Error <%s> writing to config file" % e,
                           parent=self)
        except ConfigParser.Error as e:
            tkMB.showerror("Configuration Error",
                           "Error <%s> writing to config file" % e,
                           parent=self)
        else:
            tkMB.showinfo('Success',
                          "Restart for changes to take effect",
                          parent=self)

class NidusConfigPanel(gui.ConfigPanel):
    """ Display Nidus Configuration Panel """
    def __init__(self,toplevel,chief):
        gui.ConfigPanel.__init__(self,toplevel,chief,"Configure Nidus")

    def _makegui(self,frm):
        """ set up entry widgets """
        # SSE Configuration
        frmS = Tix.Frame(frm,borderwidth=2,relief='sunken')
        frmS.pack(side=Tix.TOP,fill=Tix.BOTH,expand=True)
        Tix.Label(frmS,text='SSE').grid(row=0,column=0,columnspan=2,sticky=Tix.W)
        Tix.Label(frmS,text='Packets: ').grid(row=1,column=0,sticky=Tix.W)
        self.svar = Tix.IntVar()
        self.chkSave = Tix.Checkbutton(frmS,text="Save",border=0,
                                       variable=self.svar,command=self.cb)
        self.chkSave.grid(row=1,column=1,sticky=Tix.W)
        self.pvar = Tix.IntVar()
        self.chkPrivate = Tix.Checkbutton(frmS,text="Private",border=0,
                                          variable=self.pvar)
        self.chkPrivate.grid(row=1,column=2,sticky=Tix.E)
        Tix.Label(frmS,text='Path: ').grid(row=1,column=3,sticky=Tix.W)
        self.txtPCAPPath = Tix.Entry(frmS,width=25)
        self.txtPCAPPath.grid(row=1,column=4)
        Tix.Label(frmS,text="Max Size: ").grid(row=2,column=1,sticky=Tix.W)
        self.txtMaxSz = Tix.Entry(frmS,width=4)
        self.txtMaxSz.grid(row=2,column=2,sticky=Tix.W)
        Tix.Label(frmS,text="Max Files: ").grid(row=2,column=3,sticky=Tix.W)
        self.txtMaxFiles = Tix.Entry(frmS,width=4)
        self.txtMaxFiles.grid(row=2,column=4,columnspan=2,sticky=Tix.W)
        Tix.Label(frmS,text='Threads: ').grid(row=3,column=0,sticky=Tix.W)
        Tix.Label(frmS,text='Store: ').grid(row=3,column=1,sticky=Tix.W)
        self.txtNumStore = Tix.Entry(frmS,width=2)
        self.txtNumStore.grid(row=3,column=2,sticky=Tix.W)
        Tix.Label(frmS,text='Extract: ').grid(row=3,column=3,sticky=Tix.W)
        self.txtNumExtract = Tix.Entry(frmS,width=2)
        self.txtNumExtract.grid(row=3,column=4,sticky=Tix.W)

        # OUI Configuration
        frmO = Tix.Frame(frm,borderwidth=2,relief='sunken')
        frmO.pack(side=Tix.TOP,fill=Tix.BOTH,expand=True)
        Tix.Label(frmO,text='OUI Path: ').grid(row=0,column=0,sticky=Tix.W)
        self.txtOUIPath = Tix.Entry(frmO,width=50)
        self.txtOUIPath.grid(row=0,column=1,sticky=Tix.E)

    def cb(self):
        """ Save Checkbutton callback: disable/enable Save options as necessary """
        if self.svar.get(): state = Tix.NORMAL
        else: state = Tix.DISABLED
        self.chkPrivate.configure(state=state)
        self.txtPCAPPath.configure(state=state)
        self.txtMaxSz.configure(state=state)
        self.txtMaxFiles.configure(state=state)

    def _initialize(self):
        """ insert values from config file into entry boxes """
        conf = ConfigParser.RawConfigParser()
        if not conf.read("nidus/nidus.conf"):
            tkMB.showerror("File Not Found",
                           "File nidus.conf was not found",
                           parent=self)
            return

        # in case the conf file is invalid, set to empty if not present
        # SSE section
        try:
            save = int(conf.getboolean('SSE','save'))
            private = int(conf.getboolean('SSE','save_private'))
        except:
            save = 0
            private  =0
        self.txtPCAPPath.delete(0,Tix.END)
        if conf.has_option('SSE','save_path'):
            self.txtPCAPPath.insert(0,conf.get('SSE','save_path'))
        else: self.txtPCAPPath.insert(0,'')
        self.txtMaxSz.delete(0,Tix.END)
        if conf.has_option('SSE','save_maxsize'):
            self.txtMaxSz.insert(0,conf.get('SSE','save_maxsize'))
        else: self.txtMaxSz.insert(0,'')
        self.txtMaxFiles.delete(0,Tix.END)
        if conf.has_option('SSE','save_maxfiles'):
            self.txtMaxFiles.insert(0,conf.get('SSE','save_maxfiles'))
        else: self.txtMaxFiles.insert(0,'')
        self.txtNumStore.delete(0,Tix.END)
        if conf.has_option('SSE','store_threads'):
            self.txtNumStore.insert(0,conf.get('SSE','store_threads'))
        else: self.txtNumStore.insert(0,'2')
        self.txtNumExtract.delete(0,Tix.END)
        if conf.has_option('SSE','extract_threads'):
            self.txtNumExtract.insert(0,conf.get('SSE','extract_threads'))
        else: self.txtNumExtract.insert(0,'2')

        # disable/enable as needed
        if save: state = Tix.NORMAL
        else: state = Tix.DISABLED
        self.chkPrivate.configure(state=state)
        self.txtPCAPPath.configure(state=state)
        self.txtMaxSz.configure(state=state)
        self.txtMaxFiles.configure(state=state)

        # OUI section
        self.txtOUIPath.delete(0,Tix.END)
        if conf.has_option('OUI','path'):
            self.txtOUIPath.insert(0,conf.get('OUI','Path'))
        else: self.txtOUIPath.insert(0,'/etc/aircrack-ng/airodump-ng-oui.txt')

    def _validate(self):
        """ validate entries """
        # if not saving pcaps, we ignore pcap options
        if self.svar.get():
            # for the pcap directory, convert to absolute path before checking existence
            pPCAP = self.txtPCAPPath.get()
            if not os.path.isabs(pPCAP):
                pPCAP = os.path.abspath(os.path.join('nidus',pPCAP))
            if not os.path.exists(pPCAP):
                tkMB.showerror("Invalid Input",
                               "PCAP directory %s does not exist" % pPCAP,
                               parent=self)
                return False
            try:
                sz = int(self.txtMaxSz.get())
                if sz < 1:
                    tkMB.showerror("Invalid Input",
                                   "Max Size must be >= 1",
                                   parent=self)
                    return False
            except ValueError:
                tkMB.showerror("Invalid Input",
                               "Max Size must be an integer",
                               parent=self)
                return False
            try:
                sz = int(self.txtMaxFiles.get())
                if sz < 1:
                    tkMB.showerror("Invalid Input",
                                   "Max Files must be >= 1",
                                   parent=self)
                    return False
            except ValueError:
                tkMB.showerror("Invalid Input",
                               "Max files must be an integer",
                               parent=self)
                return False
        try:
            st = int(self.txtNumStore.get())
            if st < 1 or st > 10:
                tkMB.showerror("Invalid Input",
                               "Number of store threads must be between 1 and 10",
                               parent=self)
                return False
        except ValueError:
            tkMB.showerror("Invalid Input",
                           "Number of store threads must be an integer",
                           parent=self)
            return False
        try:
            et = int(self.txtNumExtract.get())
            if et < 1 or et > 10:
                tkMB.showerror("Invalid Input",
                               "Number of extract threads must be between 1 and 10",
                               parent=self)
                return False
        except ValueError:
            tkMB.showerror("Invalid Input",
                           "Number of extract threads must be an integer",
                           parent=self)
            return False
        if not os.path.isfile(self.txtOUIPath.get()):
            tkMB.showerror("Invalid Input",
                           "OUI file %s is not valid" % self.txtOUIPath.get(),
                           parent=self)
            return False
        return True

    def _write(self):
        """ write entry inputs to config file """
        fout = None
        try:
            conf = ConfigParser.ConfigParser()

            # SSE section
            conf.add_section('SSE')
            conf.set('SSE','save','yes' if self.svar.get() else 'no')
            conf.set('SSE','save_private','yes' if self.pvar.get() else 'no')
            conf.set('SSE','save_path',self.txtPCAPPath.get())
            conf.set('SSE','save_maxsize',self.txtMaxSz.get())
            conf.set('SSE','save_maxfiles',self.txtMaxFiles.get())
            conf.set('SSE','store_threads',self.txtNumStore.get())
            conf.set('SSE','extract_threads',self.txtNumExtract.get())

            # OUI section
            conf.add_section('OUI')
            conf.set('OUI','path',self.txtOUIPath.get())

            fout = open('nidus/nidus.conf','w')
            conf.write(fout)
            fout.close()
        except IOError as e:
            tkMB.showerror("File Error",
                           "Error <%s> writing to config file" % e,
                           parent=self)
        except ConfigParser.Error as e:
            tkMB.showerror("Configuration Error",
                           "Error <%s> writing to config file" % e,
                           parent=self)
        else:
            tkMB.showinfo('Success',
                          "Changes will take effect on next start",
                          parent=self)

class DySKTConfigPanel(gui.ConfigPanel):
    """ Display Nidus Configuration Panel """
    def __init__(self,toplevel,chief):
        gui.ConfigPanel.__init__(self,toplevel,chief,"Configure DySKT")

    def _makegui(self,frm):
        """ set up entry widgets """
        # Recon Configuration
        frmR = Tix.Frame(frm,borderwidth=2,relief='sunken')
        frmR.pack(side=Tix.TOP,fill=Tix.BOTH,expand=True)
        Tix.Label(frmR,text='RECON').grid(row=0,column=0,columnspan=6,sticky=Tix.W)
        Tix.Label(frmR,text='NIC: ').grid(row=1,column=0,sticky=Tix.W+Tix.N)
        self.txtReconNic = Tix.Entry(frmR,width=5)
        self.txtReconNic.grid(row=1,column=1,sticky=Tix.W+Tix.N)
        rbtn = Tix.Button(frmR,text='Check',command=lambda:self.checknic(self.txtReconNic))
        rbtn.grid(row=1,column=2,sticky=Tix.W)
        Tix.Label(frmR,text='Spoof: ').grid(row=1,column=3,sticky=Tix.W+Tix.N)
        self.txtReconSpoof = Tix.Entry(frmR,width=17)
        self.txtReconSpoof.grid(row=1,column=4,sticky=Tix.W+Tix.N)
        Tix.Label(frmR,text='Desc: ').grid(row=2,column=0,sticky=Tix.W+Tix.N)
        self.txtReconDesc = Tix.Text(frmR,width=42,height=3)
        self.txtReconDesc.grid(row=2,column=1,columnspan=4,sticky=Tix.E)
        # ANTENNA SUB SECTION
        frmRA = Tix.Frame(frmR,borderwidth=2,relief='sunken')
        frmRA.grid(row=4,column=1,columnspan=4,sticky=Tix.N+Tix.W)
        Tix.Label(frmRA,text='ANTENNA(S)').grid(row=0,column=0,columnspan=2,sticky=Tix.W)
        Tix.Label(frmRA,text="Number: ").grid(row=1,column=0,sticky=Tix.W)
        self.txtReconAntNum = Tix.Entry(frmRA,width=2)
        self.txtReconAntNum.grid(row=1,column=1,sticky=Tix.W)
        Tix.Label(frmRA,text='Gain: ').grid(row=2,column=0,sticky=Tix.W)
        self.txtReconAntGain = Tix.Entry(frmRA,width=7)
        self.txtReconAntGain.grid(row=2,column=1,sticky=Tix.W)
        Tix.Label(frmRA,text=" ").grid(row=2,column=2)
        Tix.Label(frmRA,text="Type: ").grid(row=2,column=3,sticky=Tix.E)
        self.txtReconAntType = Tix.Entry(frmRA,width=15)
        self.txtReconAntType.grid(row=2,column=4,sticky=Tix.E)
        Tix.Label(frmRA,text='Loss: ').grid(row=3,column=0,sticky=Tix.W)
        self.txtReconAntLoss = Tix.Entry(frmRA,width=7)
        self.txtReconAntLoss.grid(row=3,column=1,sticky=Tix.W)
        Tix.Label(frmRA,text=" ").grid(row=3,column=2)
        Tix.Label(frmRA,text="XYZ: ").grid(row=3,column=3,sticky=Tix.E)
        self.txtReconAntXYZ = Tix.Entry(frmRA,width=15)
        self.txtReconAntXYZ.grid(row=3,column=4,sticky=Tix.E)
        # SCAN PATTERN SUB SECTION
        frmRS = Tix.Frame(frmR,borderwidth=2,relief='sunken')
        frmRS.grid(row=5,column=1,columnspan=4,sticky=Tix.N+Tix.W)
        Tix.Label(frmRS,text="SCAN PATTERN").grid(row=0,column=0,columnspan=5,sticky=Tix.W)
        Tix.Label(frmRS,text="Dwell: ").grid(row=1,column=0,sticky=Tix.W)
        self.txtReconScanDwell = Tix.Entry(frmRS,width=5)
        self.txtReconScanDwell.grid(row=1,column=2,sticky=Tix.W)
        Tix.Label(frmRS,text=" ").grid(row=1,column=3)
        Tix.Label(frmRS,text="Start: ").grid(row=1,column=4,sticky=Tix.E)
        self.txtReconScanStart = Tix.Entry(frmRS,width=3)
        self.txtReconScanStart.grid(row=1,column=5,sticky=Tix.W)

        Tix.Label(frmRS,text="Scan: ").grid(row=2,column=0,sticky=Tix.W)
        self.txtReconScanScan = Tix.Entry(frmRS,width=12)
        self.txtReconScanScan.grid(row=2,column=2,sticky=Tix.W)
        Tix.Label(frmRS,text=" ").grid(row=2,column=3)
        Tix.Label(frmRS,text="Pass: ").grid(row=2,column=4,sticky=Tix.W)
        self.txtReconScanPass = Tix.Entry(frmRS,width=12)
        self.txtReconScanPass.grid(row=2,column=5,sticky=Tix.E)
        # Collection Configuration
        frmC = Tix.Frame(frm,borderwidth=2,relief='sunken')
        frmC.pack(side=Tix.TOP,fill=Tix.BOTH,expand=True)

        # GPS Configuration
        frmG = Tix.Frame(frm,borderwidth=2,relief='sunken')
        frmG.pack(side=Tix.TOP,fill=Tix.BOTH,expand=True)

        # Storage Configuration
        frmS = Tix.Frame(frm,borderwidth=2,relief='sunken')
        frmS.pack(side=Tix.TOP,fill=Tix.BOTH,expand=True)

        # Local configuration
        frmL = Tix.Frame(frm,borderwidth=2,relief='sunken')
        frmL.pack(side=Tix.TOP,fill=Tix.BOTH,expand=True)

    def _initialize(self):
        """ insert values from config file into entry boxes """
        conf = ConfigParser.RawConfigParser()
        if not conf.read("wraith.conf"):
            tkMB.showerror("File Not Found","File wraith.conf was not found",parent=self)
            return

    def _validate(self):
        """ validate entries """
        return True

    def _write(self):
        """ write entry inputs to config file """
        fout = None
        try:
            conf = ConfigParser.ConfigParser()

            fout = open('dyskt/dyskt.conf','w')
            conf.write(fout)
            fout.close()
        except IOError as e:
            tkMB.showerror("File Error",
                           "Error <%s> writing to config file" % e,
                           parent=self)
        except ConfigParser.Error as e:
            tkMB.showerror("Configuration Error",
                           "Error <%s> writing to config file" % e,
                           parent=self)
        else:
            tkMB.showinfo('Success',
                          "Restart for changes to take effect",
                          parent=self)

    def checknic(self,txt):
        """ validates nic is a wireless network interface """
        nic = txt.get()
        if not nic: return
        if nic in wifaces():
            tkMB.showinfo('Found',"%s is a valid wireless NIC" % nic,parent=self)
        else:
            tkMB.showinfo("Not Found","%s is not present and/or a valid wireless NIC" % nic,parent=self)

###############################################################################
# WraithPanel - the main panel
###############################################################################

#### STATE DEFINITIONS
_STATE_INIT_   = 0
_STATE_STORE_  = 1
_STATE_CONN_   = 2
_STATE_NIDUS_  = 3
_STATE_DYSKT_  = 4
_STATE_EXIT_   = 5
_STATE_FLAGS_NAME_ = ['init','store','conn','nidus','dyskt','exit']
_STATE_FLAGS_ = {'init':(1 << 0),   # initialized properly
                 'store':(1 << 1),  # storage instance is running (i.e. postgresql)
                 'conn':(1 << 2),   # connected to storage instance
                 'nidus':(1 << 3),  # nidus storage manager running
                 'dyskt':(1 << 4),  # at least one sensor is collecting data
                 'exit':(1 << 5)}   # exiting/shutting down

class WraithPanel(gui.MasterPanel):
    """ WraithPanel - master panel for wraith gui """
    def __init__(self,toplevel):
        # set up, initialize parent and then initialize the gui
        # our variables
        self._conf = None  # configuration
        self._state = 0    # bitmask state
        self._conn = None  # connection to data storage
        self._bSQL = False # postgresql was running on startup
        self._pwd = None   # sudo password (should we not save it?)

        # set up super
        gui.MasterPanel.__init__(self,toplevel,"Wraith  v%s" % wraith.__version__,
                                 [],True,"widgets/icons/wraith3.png")

#### PROPS

    @property
    def getstate(self): return self._state

    @property
    def getstateflags(self): return bits.bitmask_list(_STATE_FLAGS_,self._state)

#### OVERRIDES

    def _initialize(self):
        """ initialize gui, determine initial state """
        # configure panel & write initial message
        # have to manually enter the desired size, as the menu does not expand
        # the visibile portion automatically
        self.tk.wm_geometry("300x1+0+0")
        self.tk.resizable(0,0)
        self.logwrite("Wraith v%s" % wraith.__version__)

        # read in conf file, exit on error
        confMsg = self._readconf()
        if confMsg:
            self.logwrite("Configuration file is invalid. " + confMsg,gui.LOG_ERR)
            return

        # determine if postgresql is running
        if cmdline.runningprocess('postgres'):
            self.logwrite('PostgreSQL is running',gui.LOG_NOTE)
            self._bSQL = True

            # update state
            self._setstate(_STATE_STORE_)

            curs = None
            try:
                # attempt to connect and set state accordingly
                self._conn = psql.connect(host=self._conf['store']['host'],
                                          dbname=self._conf['store']['db'],
                                          user=self._conf['store']['user'],
                                          password=self._conf['store']['pwd'])

                # set to use UTC and enable CONN flag
                curs = self._conn.cursor()
                curs.execute("set time zone 'UTC';")
                self._conn.commit()
                self._setstate(_STATE_CONN_)
                self.logwrite("Connected to database",gui.LOG_NOTE)
            except psql.OperationalError as e:
                if e.__str__().find('connect') > 0:
                    self.logwrite("PostgreSQL is not running",gui.LOG_WARN)
                    self._setstate(_STATE_STORE_,False)
                elif e.__str__().find('authentication') > 0:
                    self.logwrite("Authentication string is invalid",gui.LOG_ERR)
                else:
                    self.logwrite("Unspecified DB error occurred",gui.LOG_ERR)
                    self._conn.rollback()
                self.logwrite("Not connected to database",gui.LOG_WARN)
            finally:
                if curs: curs.close()
        else:
            self.logwrite("PostgreSQL is not running",gui.LOG_WARN)
            self.logwrite("Not connected to database",gui.LOG_WARN)

        # nidus running?
        if cmdline.nidusrunning(NIDUSPID):
            self.logwrite("Nidus is running")
            self._setstate(_STATE_NIDUS_)
        else:
            self.logwrite("Nidus is not running",gui.LOG_WARN)

        if cmdline.dysktrunning(DYSKTPID):
            self.logwrite("DySKT is running")
            self._setstate(_STATE_DYSKT_)
        else:
            self.logwrite("DySKT is not running",gui.LOG_WARN)

        # set initial state to initialized
        self._setstate(_STATE_INIT_)

        # adjust menu options accordingly
        self._menuenable()

    def _shutdown(self):
        """ if connected to datastorage, closes connection """
        # set the state
        self._setstate(_STATE_EXIT_)

        # shutdown dyskt
        self._stopsensor()

        # shutdown storage
        self._stopstorage()

    def _makemenu(self):
        """ make the menu """
        self.menubar = Tix.Menu(self)

        # File Menu
        # all options will always be enabled
        self.mnuWraith = Tix.Menu(self.menubar,tearoff=0)
        self.mnuWraithGui = Tix.Menu(self.mnuWraith,tearoff=0)
        self.mnuWraithGui.add_command(label='Save',command=self.guisave)
        self.mnuWraithGui.add_command(label='Load',command=self.guiload)
        self.mnuWraith.add_cascade(label='Gui',menu=self.mnuWraithGui)
        self.mnuWraith.add_separator()
        self.mnuWraith.add_command(label='Configure',command=self.configwraith)
        self.mnuWraith.add_separator()
        self.mnuWraith.add_command(label='Exit',command=self.delete)

        # Tools Menu
        # all options will always be enabled
        self.mnuTools = Tix.Menu(self.menubar,tearoff=0)
        self.mnuToolsCalcs = Tix.Menu(self.mnuTools,tearoff=0)
        self.mnuTools.add_cascade(label="Calcuators",menu=self.mnuToolsCalcs)

        # View Menu
        # all options will always be enabled
        self.mnuView = Tix.Menu(self.menubar,tearoff=0)
        self.mnuView.add_command(label='Data Bins',command=self.viewdatabins)
        self.mnuView.add_separator()
        self.mnuView.add_command(label='Data',command=self.viewdata)

        # Storage Menu
        self.mnuStorage = Tix.Menu(self.menubar,tearoff=0)
        self.mnuStorage.add_command(label="Start All",command=self.storagestart)  # 0
        self.mnuStorage.add_command(label="Stop All",command=self.storagestop)    # 1
        self.mnuStorage.add_separator()                                           # 2
        self.mnuStoragePSQL = Tix.Menu(self.mnuStorage,tearoff=0)
        self.mnuStoragePSQL.add_command(label='Start',command=self.psqlstart)       # 0
        self.mnuStoragePSQL.add_command(label='Stop',command=self.psqlstop)         # 1
        self.mnuStoragePSQL.add_separator()                                         # 2
        self.mnuStoragePSQL.add_command(label='Connect',command=self.connect)       # 3
        self.mnuStoragePSQL.add_command(label='Disconnect',command=self.disconnect) # 4      # 1
        self.mnuStoragePSQL.add_separator()                                         # 5
        self.mnuStoragePSQL.add_command(label='Fix',command=self.psqlfix)           # 6
        self.mnuStoragePSQL.add_command(label='Delete All',command=self.psqldelall) # 7
        self.mnuStorage.add_cascade(label='PostgreSQL',menu=self.mnuStoragePSQL)  # 3
        self.mnuStorageNidus = Tix.Menu(self.mnuStorage,tearoff=0)
        self.mnuStorageNidus.add_command(label='Start',command=self.nidusstart)     # 0
        self.mnuStorageNidus.add_command(label='Stop',command=self.nidusstop)       # 1
        self.mnuStorageNidus.add_separator()                                        # 2
        self.mnuNidusLog = Tix.Menu(self.mnuStorageNidus,tearoff=0)
        self.mnuNidusLog.add_command(label='View',command=self.viewniduslog)         # 0
        self.mnuNidusLog.add_command(label='Clear',command=self.clearniduslog)       # 1
        self.mnuStorageNidus.add_cascade(label='Log',menu=self.mnuNidusLog)         # 3
        self.mnuStorageNidus.add_separator()                                        # 4
        self.mnuStorageNidus.add_command(label='Config',command=self.confignidus)   # 5
        self.mnuStorage.add_cascade(label='Nidus',menu=self.mnuStorageNidus)      # 4

        # DySKT Menu
        self.mnuDySKT = Tix.Menu(self.menubar,tearoff=0)
        self.mnuDySKT.add_command(label='Start',command=self.dysktstart)   # 0
        self.mnuDySKT.add_command(label='Stop',command=self.dysktstop)     # 1
        self.mnuDySKT.add_separator()                                      # 2
        self.mnuDySKT.add_command(label='Control',command=self.dysktctrl)  # 3            # 3
        self.mnuDySKT.add_separator()                                      # 4
        self.mnuDySKTLog = Tix.Menu(self.mnuDySKT,tearoff=0)
        self.mnuDySKTLog.add_command(label='View',command=self.viewdysktlog)   # 0
        self.mnuDySKTLog.add_command(label='Clear',command=self.cleardysktlog) # 1
        self.mnuDySKT.add_cascade(label='Log',menu=self.mnuDySKTLog)       # 5
        self.mnuDySKT.add_separator()                                      # 6
        self.mnuDySKT.add_command(label='Config',command=self.configdyskt) # 7

        # Help Menu
        self.mnuHelp = Tix.Menu(self.menubar,tearoff=0)
        self.mnuHelp.add_command(label='About',command=self.about)
        self.mnuHelp.add_command(label='Help',command=self.help)

        # add the menus
        self.menubar.add_cascade(label='Wraith',menu=self.mnuWraith)
        self.menubar.add_cascade(label="Tools",menu=self.mnuTools)
        self.menubar.add_cascade(label='View',menu=self.mnuView)
        self.menubar.add_cascade(label='Storage',menu=self.mnuStorage)
        self.menubar.add_cascade(label='DySKT',menu=self.mnuDySKT)
        self.menubar.add_cascade(label='Help',menu=self.mnuHelp)

#### MENU CALLBACKS

#### Wraith Menu
    def configwraith(self):
        """ display config file preference editor """
        panel = self.getpanels("preferences",False)
        if not panel:
            t = Tix.Toplevel()
            pnl = WraithConfigPanel(t,self)
            self.addpanel(pnl.name,gui.PanelRecord(t,pnl,"preferences"))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

#### View Menu

    def viewdatabins(self):
        """ display the data bins panel """
        panel = self.getpanels("databin",False)
        if not panel:
            t = Tix.Toplevel()
            pnl = DataBinPanel(t,self)
            self.addpanel(pnl.name,gui.PanelRecord(t,pnl,"databin"))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

    def viewdata(self):
        """ display data panel """
        self.unimplemented()

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
            self._psqlconnect()
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
            self._startpsql()
            self._updatestate()
            self._menuenable()

    def psqlstop(self):
        """ starts postgresql """
        # should not be enabled if postgresql is not running, but check anyway
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if flags['store'] and not flags['dyskt']:
            # do we have a password
            if not self._pwd:
                pwd = self._getpwd()
                if pwd is None:
                    self.logwrite("Password entry canceled. Cannot continue",
                                  gui.LOG_WARN)
                    return
                self._pwd = pwd
            self._stoppsql()
            self._updatestate()
            self._menuenable()

    def psqlfix(self):
        """
         fix any open-ended periods left over by errors. An error or kill -9
         may leave periods in certain tables as NULL-ended which will throw an
         error during insert of new records
        """
        # should not be enabled unless postgres is running, we are connected
        # and a sensor is not running, but check anyway
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if flags['store'] and flags['conn'] and not flags['dyskt']:
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
        if flags['store'] and flags['conn'] and not flags['dyskt']:
            ans = tkMB.askquestion('Delete Records','Delete all DB records?',
                                   parent=self)
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
                self.logwrite("Failed to delete records <%s: %s>" % (e.pgcode,e.pgerror),
                              gui.LOG_ERR)
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
            self._startnidus()
            self._updatestate()
            self._menuenable()

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
            self._stopnidus()
            self._updatestate()
            self._menuenable()

    def viewniduslog(self):
        """ display Nidus log """
        panel = self.getpanels('niduslog',False)
        if not panel:
            t = Tix.Toplevel()
            pnl = gui.TailLogPanel(t,self,"Nidus Log",0.2,NIDUSLOG)
            self.addpanel(pnl.name,gui.PanelRecord(t,pnl,"niduslog"))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

    def clearniduslog(self):
        """ clear nidus log """
        # prompt first
        finfo = os.stat(NIDUSLOG)
        if finfo.st_size > 0:
            ans = tkMB.askquestion("Clear Log","Clear contents of Nidus log?",
                                   parent=self)
            if ans == 'no': return
            lv = self.getpanel('niduslog')
            #if lv: lv.close()
            with open(NIDUSLOG,'w'): os.utime(NIDUSLOG,None)
            if lv: lv.reset()
            #self.viewniduslog()

    def confignidus(self):
        """ display nidus config file preference editor """
        panel = self.getpanels("nidusprefs",False)
        if not panel:
            t = Tix.Toplevel()
            pnl = NidusConfigPanel(t,self)
            self.addpanel(pnl.name,gui.PanelRecord(t,pnl,"nidusprefs"))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

#### DySKT Menu

    def dysktstart(self):
        """ starts DySKT sensor """
        self._startsensor()
        self._updatestate()
        self._menuenable()

    def dysktstop(self):
        """ stops DySKT sensor """
        self._stopsensor()
        self._updatestate()
        self._menuenable()

    def dysktctrl(self):
        """ displays DySKT Control Panel """
        self.unimplemented()

    def viewdysktlog(self):
        """ display DySKT log """
        panel = self.getpanels('dysktlog',False)
        if not panel:
            t = Tix.Toplevel()
            pnl = gui.TailLogPanel(t,self,"DySKT Log",0.2,DYSKTLOG)
            self.addpanel(pnl.name,gui.PanelRecord(t,pnl,'dysktlog'))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

    def cleardysktlog(self):
        """ clears the DySKT log """
        # prompt first
        finfo = os.stat(DYSKTLOG)
        if finfo.st_size > 0:
            ans = tkMB.askquestion("Clear Log","Clear contents of DySKT log?",
                                   parent=self)
            if ans == 'no': return
            with open(DYSKTLOG,'w'): pass
            lv = self.getpanel('dysktlog')
            if lv: lv.pnlreset()

    def configdyskt(self):
        """ display dyskt config file preference editor """
        panel = self.getpanels("dysktprefs",False)
        if not panel:
            t = Tix.Toplevel()
            pnl = DySKTConfigPanel(t,self)
            self.addpanel(pnl.name,gui.PanelRecord(t,pnl,"dysktprefs"))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

#### HELP MENU

    def about(self):
        """ display the about panel """
        panel = self.getpanels("about",False)
        if not panel:
            t = Tix.Toplevel()
            pnl = AboutPanel(t,self)
            self.addpanel(pnl.name,gui.PanelRecord(t,pnl,"about"))
        else:
            panel[0].tk.deiconify()
            panel[0].tk.lift()

    def help(self):
        """ display the help panel """
        self.unimplemented()

#### MINION METHODS

    def showpanel(self,desc):
        """ opens a panel of type desc """
        if desc == 'log': self.viewlog()
        elif desc == 'databin': self.viewdatabins()
        else: raise RuntimeError, "WTF Cannot open %s" % desc

#### HELPER FUNCTIONS

    def _updatestate(self):
        """ reevaluates internal state """
        # state of nidus
        if cmdline.nidusrunning(NIDUSPID): self._setstate(_STATE_NIDUS_)
        else: self._setstate(_STATE_NIDUS_,False)

        # state of dyskt
        if cmdline.dysktrunning(DYSKTPID): self._setstate(_STATE_DYSKT_)
        else:  self._setstate(_STATE_DYSKT_,False)

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

    def _readconf(self):
        """ read in configuration file """
        conf = ConfigParser.RawConfigParser()
        if not conf.read("wraith.conf"): return "wraith.conf does not exist"

        self._conf = {}
        try:
            ## STORAGE
            self._conf['store'] = {'host':conf.get('Storage','host'),
                                   'db':conf.get('Storage','db'),
                                   'user':conf.get('Storage','user'),
                                   'pwd':conf.get('Storage','pwd')}

            ## POLICY
            self._conf['policy'] = {'polite':True,
                                   'shutdown':True}

            if conf.has_option('Policy','polite'):
                if conf.get('Policy','polite').lower() == 'off':
                    self._conf['policy']['polite'] = False
            if conf.has_option('Policy','shutdown'):
                if conf.get('Policy','shutdown').lower() == 'manual':
                    self._conf['ploicy']['shutdown'] = False

            # return no errors
            return ''
        except (ConfigParser.NoSectionError,ConfigParser.NoOptionError) as e:
            return e.__str__()

    def _menuenable(self):
        """ enable/disable menus as necessary """
        # get all flags
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)

        # adjust storage menu
        # easiest for storage is to disable all and then only enable relevant
        # always allow Nidus->config, Nidus->View Log
        self.mnuStorage.entryconfig(0,state=Tix.DISABLED)      # all start
        self.mnuStorage.entryconfig(1,state=Tix.DISABLED)      # all stop
        self.mnuStoragePSQL.entryconfig(0,state=Tix.DISABLED)  # psql start
        self.mnuStoragePSQL.entryconfig(1,state=Tix.DISABLED)  # psql stop
        self.mnuStoragePSQL.entryconfig(3,state=Tix.DISABLED)  # connect 2 psql
        self.mnuStoragePSQL.entryconfig(4,state=Tix.DISABLED)  # disconnect from psql
        self.mnuStoragePSQL.entryconfig(6,state=Tix.DISABLED)  # psql fix
        self.mnuStoragePSQL.entryconfig(7,state=Tix.DISABLED)  # psql delete all
        self.mnuStorageNidus.entryconfig(0,state=Tix.DISABLED) # nidus start
        self.mnuStorageNidus.entryconfig(1,state=Tix.DISABLED) # nidus stop
        self.mnuNidusLog.entryconfig(1,state=Tix.DISABLED)     # nidus log clear

        if flags['store']:
            # storage is running enable stop all, stop postgresql (if dyskt is
            # not running)
            self.mnuStorage.entryconfig(1,state=Tix.NORMAL)
            if not flags['dyskt']: self.mnuStoragePSQL.entryconfig(1,state=Tix.NORMAL)
        else:
            # storage is not running, enable start all, start postgresql
            self.mnuStorage.entryconfig(0,state=Tix.NORMAL)
            self.mnuStoragePSQL.entryconfig(0,state=Tix.NORMAL)

        if flags['nidus']:
            # nidus is running, enable stop all, stop nidus
            self.mnuStorage.entryconfig(1,state=Tix.NORMAL)
            self.mnuStorageNidus.entryconfig(1,state=Tix.NORMAL)
        else:
            # nidus is not running, enable start all & clear nidus log
            # enable start nidus only if postgres is running
            self.mnuStorage.entryconfig(0,state=Tix.NORMAL)
            self.mnuStorageNidus.entryconfig(0,state=Tix.NORMAL)
            self.mnuNidusLog.entryconfig(1,state=Tix.NORMAL)

        if flags['conn']:
            # connected to psql, enable stop all and disconnect
            # if no DysKT is running, enable fix psql and delete all
            self.mnuStorage.entryconfig(1,state=Tix.NORMAL)
            self.mnuStoragePSQL.entryconfig(4,state=Tix.NORMAL)
            if not flags['dyskt']:
                self.mnuStoragePSQL.entryconfig(6,state=Tix.NORMAL)  # psql fix
                self.mnuStoragePSQL.entryconfig(7,state=Tix.NORMAL)  # psql delete all
        else:
            # disconnected, enable start all, enable connect if postgres is running
            self.mnuStorage.entryconfig(0,state=Tix.NORMAL)
            if flags['store']: self.mnuStoragePSQL.entryconfig(3,state=Tix.NORMAL)

        # adjust dyskt menu
        if not flags['store'] and not flags['nidus']:
            # cannot start/stop/control dyskt unless nidus & postgres is running
            self.mnuDySKT.entryconfig(0,state=Tix.DISABLED)  # start
            self.mnuDySKT.entryconfig(1,state=Tix.DISABLED)  # stop
            self.mnuDySKT.entryconfig(3,state=Tix.DISABLED)  # ctrl panel
            self.mnuDySKTLog.entryconfig(1,state=Tix.NORMAL) # clear log
            self.mnuDySKT.entryconfig(7,state=Tix.NORMAL)    # configure
        else:
            if flags['dyskt']:
                # DySKT sensor is running
                self.mnuDySKT.entryconfig(0,state=Tix.DISABLED)    # start
                self.mnuDySKT.entryconfig(1,state=Tix.NORMAL)      # stop
                self.mnuDySKT.entryconfig(3,state=Tix.NORMAL)      # ctrl panel
                self.mnuDySKTLog.entryconfig(1,state=Tix.DISABLED) # clear log
                self.mnuDySKT.entryconfig(7,state=Tix.NORMAL)      # configure
            else:
                # DySKT sensor is not running
                self.mnuDySKT.entryconfig(0,state=Tix.NORMAL)    # start
                self.mnuDySKT.entryconfig(1,state=Tix.DISABLED)  # stop
                self.mnuDySKT.entryconfig(3,state=Tix.DISABLED)  # ctrl panel
                self.mnuDySKTLog.entryconfig(1,state=Tix.NORMAL) # clear log
                self.mnuDySKT.entryconfig(7,state=Tix.NORMAL)    # configure

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
        if not flags['store']: self._startpsql()

        # start nidus
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if not flags['nidus'] and flags['store']: self._startnidus()

        # connect to db
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if not flags['conn'] and flags['store']: self._psqlconnect()

    def _startpsql(self):
        """
         start postgresl server
         NOTE: 1) no state checking done here
               2) assumes sudo password is entered
        """
        # attempt to start psql
        try:
            self.logwrite("Starting PostgreSQL...",gui.LOG_NOTE)
            cmdline.service('postgresql',self._pwd)
            time.sleep(0.5)
            if not cmdline.runningprocess('postgres'): raise RuntimeError('unknown')
        except RuntimeError as e:
            self.logwrite("Error starting PostgreSQL: %s" % e,gui.LOG_ERR)
            return
        else:
            self.logwrite("PostgreSQL started")
            self._setstate(_STATE_STORE_)

    def _startnidus(self):
        """
         start nidus storage manager
         NOTE: 1) no state checking done here
               2) assumes sudo password is entered
        """
        # attempt to start nidus
        try:
            self.logwrite("Starting Nidus...",gui.LOG_NOTE)
            cmdline.service('nidusd',self._pwd)
            time.sleep(0.5)
            if not cmdline.nidusrunning(NIDUSPID): raise RuntimeError('unknown')
        except RuntimeError as e:
            self.logwrite("Error starting Nidus: %s" % e,gui.LOG_ERR)
        else:
            self.logwrite("Nidus Started")
            self._setstate(_STATE_NIDUS_)

    def _psqlconnect(self):
        """ connect to postgresql db: nidus """
        curs = None
        try:
            self.logwrite("Connecting to Nidus Datastore...",gui.LOG_NOTE)
            self._conn = psql.connect(host=self._conf['store']['host'],
                                      dbname=self._conf['store']['db'],
                                      user=self._conf['store']['user'],
                                      password=self._conf['store']['pwd'],)

            # set to use UTC and enable CONN flag
            curs = self._conn.cursor()
            curs.execute("set time zone 'UTC';")
            self._conn.commit()

            self.logwrite("Connected to datastore")
            self._setstate(_STATE_CONN_)
        except psql.OperationalError as e:
            if e.__str__().find('connect') > 0:
                self.logwrite("PostgreSQL is not running",gui.LOG_WARN)
                self._setstate(_STATE_STORE_,False)
            elif e.__str__().find('authentication') > 0:
                self.logwrite("Authentication string is invalid",gui.LOG_ERR)
            else:
                self.logwrite("Unspecified DB error occurred",gui.LOG_ERR)
                self._conn.rollback()
        finally:
            if curs: curs.close()

    def _stopstorage(self):
        """ stop posgresql db, nidus storage manager & disconnect """
        # if DySKT is running, prompt for clearance
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if flags['dyskt']:
            ans = tkMB.askquestion('DySKT Running','Quit and lose queued data?',parent=self)
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
            self._stopnidus()

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
            self._stoppsql()

    def _psqldisconnect(self):
        """ disconnect from postgresl """
        self.logwrite("Disconnecting from Nidus datastore...",gui.LOG_NOTE)
        self._conn.close()
        self._conn = None
        self._setstate(_STATE_CONN_,False)
        self.logwrite("Disconnected from Nidus datastore")

    def _stopnidus(self):
        """
         stop nidus storage manager.
          NOTE: 1) no state checking done here
                2) assumes sudo password is entered
        """
        try:
            self.logwrite("Shutting down Nidus...",gui.LOG_NOTE)
            cmdline.service('nidusd',self._pwd,False)
            while cmdline.nidusrunning(NIDUSPID):
                self.logwrite("Nidus still processing data...",gui.LOG_NOTE)
                time.sleep(1.0)
        except RuntimeError as e:
            self.logwrite("Error shutting down Nidus: %s" % e,gui.LOG_ERR)
        else:
            self._setstate(_STATE_NIDUS_,False)
            self.logwrite("Nidus shut down")

    def _stoppsql(self):
        """
         shut down posgresql.
         NOTE: 1) no state checking done here
               2) assumes sudo password is entered
        """
        try:
            self.logwrite("Shutting down PostgreSQL",gui.LOG_NOTE)
            cmdline.service('postgresql',self._pwd,False)
            while cmdline.runningprocess('postgres'):
                self.logwrite("PostgreSQL shutting down...",gui.LOG_NOTE)
                time.sleep(0.5)
        except RuntimeError as e:
            self.logwrite("Error shutting down PostgreSQL",gui.LOG_ERR)
        else:
            self._setstate(_STATE_STORE_,False)
            self.logwrite("PostgreSQL shut down")

    def _startsensor(self):
        """ starts the DySKT sensor """
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if flags['store'] and flags['nidus'] and not flags['dyskt']:
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
                self.logwrite("Starting DySKT...",gui.LOG_NOTE)
                cmdline.service('dysktd',self._pwd)
                time.sleep(0.5)
                if not cmdline.dysktrunning(DYSKTPID): raise RuntimeError('unknown')
            except RuntimeError as e:
                self.logwrite("Error starting DySKT: %s" % e,gui.LOG_ERR)
            else:
                self.logwrite("DySKT Started")
                self._setstate(_STATE_DYSKT_)

    def _stopsensor(self):
        """ stops the DySKT sensor """
        flags = bits.bitmask_list(_STATE_FLAGS_,self._state)
        if flags['dyskt']:
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
                self.logwrite("Shutting down DySKT...",gui.LOG_NOTE)
                cmdline.service('dysktd',self._pwd,False)
            except RuntimeError as e:
                self.logwrite("Error shutting down DySKT: %s" % e,gui.LOG_ERR)
            else:
                self._setstate(_STATE_DYSKT_,False)
                self.logwrite("DySKT shut down")

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

if __name__ == 'wraith-rt':
    t = Tix.Tk()
    t.option_add('*foreground','blue')                # normal fg color
    t.option_add('*background','black')               # normal bg color
    t.option_add('*activeBackground','black')         # bg on mouseover
    t.option_add('*activeForeground','blue')          # fg on mouseover
    t.option_add('*disabledForeground','gray')        # fg on disabled widget
    t.option_add('*disabledBackground','black')       # bg on disabled widget
    t.option_add('*troughColor','black')              # trough on scales/scrollbars
    WraithPanel(t).mainloop()