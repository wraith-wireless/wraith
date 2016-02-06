#!/usr/bin/env python

""" oui.py: oui/manuf related functions
"""

#__name__ = 'oui'
__license__ = 'GPL v3.0'
__version__ = '0.0.3'
__date__ = 'September 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import urllib2,os,sys,time
import argparse as ap
from wraith.utils.timestamps import ts2iso

def parseoui(path=None):
    """
     parse oui.txt file
     :param path: path of oui text file
     :returns: oui dict {oui:manuf} for each oui in path or empty dict
    """
    fin = None
    ouis = {}
    try:
        fin = open(path)
        for line in fin.readlines()[1:]:
            oui,manuf = line.strip().split('\t')
            ouis[oui.lower()] = manuf[0:100]
        fin.close()
    except: pass
    finally:
        if fin and not fin.closed: fin.close()
    return ouis

def manufacturer(oui,mac):
    """
     returns the manufacturer of the mac address if exists, otherwise 'unknown'
     :param oui: oui dict
     :param mac: hw addr to search up
     :returns: manufacturer
    """
    try:
        return oui[mac[:8]]
    except KeyError:
        return "unknown"

def fetch(path=None,verbose=False):
    """
     retrieves oui.txt from IEEE and writes to data file
     :param path: fullpath of oui.txt
     :param verbose: write updates to stdout
    """
    # determine if data path is legit
    if path is None:
        ouipath = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               os.path.abspath('../data/oui.txt'))
    else:
        ouipath = path
    if not os.path.isdir(os.path.dirname(ouipath)):
        print "Path to data is incorrect {0}".format(ouipath)
        sys.exit(1)

    # fetch oui file from ieee
    fout = None
    #pattern = r'^([-|\w]*)   \(hex\)\t\t(.*)\r'

    # set up url request
    ouiurl = 'http://standards-oui.ieee.org/oui.txt'
    req = urllib2.Request(ouiurl)
    req.add_header('User-Agent',"wraith-rt +https://github.com/wraith-wireless/wraith/")
    try:
        # retrieve the oui file and parse out generated date
        if verbose: print 'Fetching ', ouiurl
        res = urllib2.urlopen(req)
        if verbose: print "Parsing OUI file"

        if verbose: print "Opening data file {0} for writing".format(ouipath)
        fout = open(ouipath,'w')
        gen = ts2iso(time.time()) # use current time as the first line
        fout.write(gen+'\n')

        # pull out ouis
        t = time.time()
        cnt = 0
        for l in res:
            if '(hex)' in l:
                # extract oui and manufacturer
                oui,manuf = l.split('(hex)')
                oui = oui.strip().replace('-',':')
                manuf = manuf.strip()
                if manuf.startswith("IEEE REGISTRATION AUTHORITY"):
                    manuf = "IEEE REGISTRATION AUTHORITY"

                # write to file & update count
                fout.write('{0}\t{1}\n'.format(oui,manuf))
                cnt += 1
                if verbose: print "{0}:\t{1}\t{2}".format(cnt,oui,manuf)
        print "Wrote {0} OUIs in {1:.3} secs".format(cnt,time.time()-t)
    except urllib2.URLError as e:
        print "Error fetching oui file: {0}".format(e)
    except IOError as e:
        print "Error opening output file {0}".format(e)
    except Exception as e:
        print "Error parsing oui file: {0}".format(e)
    finally:
        if fout: fout.close()

if __name__ == '__main__':
    # create arg parser and parse command line args
    print "OUI Fetch {0}".format(__version__)
    argp = ap.ArgumentParser(description="IEEE OUI fetch and parse")
    argp.add_argument('-p','--path',help="Path to write parsed file")
    argp.add_argument('-v','--verbose',action='store_true',help="Display operations to stdout")
    argp.add_argument('--version',action='version',version="OUI Fetch {0}".format(__version__))
    args = argp.parse_args()
    verbose = args.verbose
    path = args.path

    # esecute
    fetch(path,verbose)