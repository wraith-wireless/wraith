#!/usr/bin/env python

""" suckt: Small Unit Capture/Kill Team (Wraith Sensor)

A suckt consists of an optional collection radio (i.e. spotter), a mandatory
reconnaissance radio (i.e. shooter)  and an RTO which relays collected data to
the data storage system (i.e. HQ). The suckt collects data in the form of raw
802.11 packets with both the reconnaissance and collection radios and forwards
that date along with any geolocational data (if a gps device is present) to higher.
The reconnaissance radio will also partake in assaults in directed to.

REVISIONS:
suckt 0.1.4
 includes: suckt 0.0.8, radio 0.0.4, collate 0.0.8, pf 0.0.6, sucktd, sucktd.conf,
  sucktd.log.conf suktd
 changes:
  - consolidates radio related processes, sniffer and tuner, into a the RadioController
    class
   o cleans up the interprocess communication and minimizes the number of
     shared communication objects and the number of sub process
   o radio class now subclasses mp.Process

suckt 0.1.5
 desc: utilizes a new internal communication SOP to streamline and simplify
  interprocess communications
 includes: suckt 0.0.10 internal 0.0.1 rto 0.0.9 (previously collator) rdoctl 0.0.4
  suckt.conf suckt.log.conf sucktd
 changes:
  - streamlined inter-process communication methods/objects
   o replaced interprocess Pipes with a single Queue
   o removed the Queue used by children to communicate with suckt and made
    each connection dual-ended
  - scan pattern config modified
   o added band and width specification to scan and pass configuration
   o added optional initial channel and channel width
  - modified gps processing
   o removed pf.py and pushed gps polling as a thread into rto
 - removed signal handling as a means to pass commands
   o need to code command interface

TODO:
     ** After testing remove set raw capability from python **
      3) implement adapt scan pattern
     26) pf identify/handle gps device failing or being removed
     31) add interface (tcpserver? or socket?) to allow finer control of pausing,
         holding, listening
          o better define hold, listen, pause
           - hold stop scanning on current channel
           - listen stop scanning on specified channel
           - pause stop scanning and recording
     34) uniquely identify a gps device with a permanent id w/out hardcoding
         in conf file
     37) add ability to 'filter' on one network, i.e. bssid or ssid?
     40) look into socket options (and pcapy code) to ensure best performance
"""
__name__ = 'suckt'
__license__ = 'GPL'
__version__ = '0.1.5'
__date__ = 'December 2014'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@hushmail.com'
__status__ = 'Development'
