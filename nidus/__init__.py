#!/usr/bin/env python

""" nidus: SocketServer collecting data from Wasp sensors

Uses Python SocketServer with Threaded mixin to get & store Wasp collected data

nidus 0.0.4
 desc: implements datastorage writes to db. ATT it is assumed that nidus will be/has
  the potential to be a bottleneck requiring massive amounts of data to be received
  and processed. It is hoped the builtin SocketServer.TCPServer with ThreadingMixIn
  will be sufficient to handle a single-system setup. The slowest (relatively)
  process will be the submission, processing and storing of frames.
 includes: nidus 0.0.3, nmp 0.0.2, nidusdb 0.1.1 nidus.sql 0.0.9, simplepcap 0.0.1
  nidus.conf nidus.log.conf
 changes:
  - extends failure method to handle situations where nidus is shutdown unexpectantly
  - no longer attempts to store all packets in the data store
     o frames are saved to file
     o frames are parsed and portions are stored in the data store
  - SSE (Save Store Extract) is multithreaded which has helped alleviate delay
    from sensor exiting to nidus closing session records
      o 1 thread per radio for saving and number of threads for storing, extracting
        are specified in the configuration file
      o the database connection is attempted in the __init__ function
      o threads will create a cursor each time an item is processed (see
        psycopg2 for details on lightweight cursors)
  - implements 'privacy' feature whereby saving frames can be configured to only
    save layer 1 and layer 2 (including encryption from layer 3)
  - modified frame submission (running into issues where a frame id had to be
    created IOT individual threads [i.e. Save,Extract] did not insert a record
    referenceing a frame that did not exist):
     o the frame record is inserted in the submitframe function so that each thread
       will have the primary key of that frame.
     o tasks are only put respective queues if there is something for the SSE
       thread to process. i.e. if the MPDU failed to parse, extract threads will
       not be tasked with processing an empty MPDU

TODO:
1) Should we return messages? i.e instead of just closing pipe for no running server etc
2) need constraints either through postgresql (preferred) or nidusdb - one example
   for each geo inserted verify first that the ts is within the period defined for
   the corresponding sensor
3) Optimize datastore storage and retrieval
4) identify postgresql server not running prior to request handler
7) encrypted socket connection from wasp to nidus?
8) secured (hashed) username/password from to datastore
10) how/when to partition table to offload older records
12) nidusdb.py
  - in SSE Threads handle errors in some way to at least let nidusdb know thread
    is quitting
  - ensure only one radio submit per radio is allowed
  - during setsensor ensure a new session for a sensor is not created if one already
    exists
"""
__name__ = 'datastore'
__license__ = 'GPL'
__version__ = '0.0.4'
__date__ = 'September 2014'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@hushmail.com'
__status__ = 'Development'