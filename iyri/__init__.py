#!/usr/bin/env python

""" iyri: Wraith 802.11 Sensor

Iyri is a 802.11 sensor consisting of a mandatory radio (Abad) and an optional
radio (Shama). While Abad can receive/collect and transmit, Shama only receives.
Iyri relays collected data to the backend database nidus, collects/stores data
from raw 802.11 packets and any geolocational data (if a gps device is present).

REVISIONS:
 0.0.x
  desc: kismet client
 0.1.x
  desc: all data forwarded to Nidus process
 0.2.0
  desc: Proof of Concept. (1) Renamed as former concept of operations no longer
   applied. (2) Utilizes a "circular buffer" (memoryview) IOT remove the inherent
   inefficiency from passing frame(s) as strings through multiple connections &
   functions including the inefficiency involved in making frequent string copies
   of the frame(s). Because python does not have a "PACKET_MMAP" flag for sockets
   (at least not that I can find), the circular buffer is created by wrapping a
   MP Array of bytes with a memoryview and using the socket.recv_from method to
   'put' frames onto the "buffer". Children then utilize shared access to the
   "buffer" to process the frames accordingly. (3) Removed the client-server
   approach. Nidus is no longer used as the data processor/storage manager and
   iyri now process and stores directly all collected data
  includes: iyri 0.1.0 collate 0.1.2 constants 0.0.1 gpsctl 0.0.1 rdoctl 0.1.0
   thresh 0.0.4 iyrid iyri.conf iyri.log.conf iyrid
  changes:
   - Uses a process for the GPSController rather than a thread
   - uses a memoryview to hold captured frames in a circular buffer
   - pushed both processing of frames and data management (db writes) into the
     sensor i.e. no longer passes data to storage manager
   - replaced string tokens (!TKN!) with numeric constants
   - writing raw frames
    o removed seperate 'writer' process, writes handled by thresher
    o removed writing raw frames to file, stored in db (have to use psycopg2 Binary
 0.2.1
  desc: Adds some "intelligent". Collator will add threshers IOT to avoid race
   condition introduced by circular buffer where frames are being overwritten
   before they are processed and remove threshers when possible to remove
   overhead of unecessary processes.
  includes: iyri 0.1.0 collate 0.1.2 constants 0.0.1 gpsctl 0.0.1 rdoctl 0.1.0
   thresh 0.0.4 iyrid iyri.conf iyri.log.conf iyrid
  changes:
   - Threshers created when workload exceeds specified threshhold and killed when
    workloads fall below specified threshhold
    o based on constants MIN_TRESH, MAX_THRESH and WRK_THRESH
   - removed artifacts hanging around from previous revisions

"""
__name__ = 'iyri'
__license__ = 'GPL v3.0'
__version__ = '0.2.1'
__date__ = 'October 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'