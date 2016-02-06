#!/usr/bin/env python

""" iyri: Wraith 802.11 Sensor

Iyri is a 802.11 sensor consisting of a mandatory radio (Abad) and an optional
radio (Shama). While Abad can receive/collect and transmit, Shama only receives.
Iyri relays collected data to the backend database nidus, storing data data
from raw 802.11 packets and any geolocational data (if a gps device is present)
as well as data on the radios, gps device and platform.

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
   - replaced string tokens with numeric constants
   - writing raw frames
    o removed seperate 'writer' process, writes handled by thresher
    o removed writing raw frames to file, stored in db (have to use psycopg2 Binary
 0.2.1
  desc: Adds some "intelligence". Collator will add threshers IOT to avoid race
   condition introduced by circular buffer where frames are being overwritten
   before they are processed and remove threshers when possible to remove
   overhead of unecessary processes. The collator also maintains an internal
   buffer 'pulling' frames of the radio's buffers as soon as it is notified
  includes: iyri 0.1.1 constants 0.0.1 collate 0.1.4 gpsctl 0.0.3 rdoctl 0.1.1
   tuner 0.0.1 thresh 0.0.5 iyrid iyri.conf iyri.log.conf iyrid
  changes:
   - Threshers created when buffer exceeds a certain capacity (25% full) and
     killed when it fall below a certain capacity (10% full)
   - added internal buffer to collator
     o collator copies frames from radio(s) buffers to internal buffers
   - removed artifacts hanging around from previous revisions
   - moved some constants to conf file (after testing)
   - made the Tuner a process
   - fixed exiting errors with RadioController
   - stopping storing frames in buffer when radio is paused
   - fixed GPSController, on static location, it was quitting without iyri tracking
   - found & fixed several bugs such as iyri not shutting down on sub-process errors
   - reworked iyri execution loop and children exection loops:
     o iyri can process messages from children during shutdown phase
     o all children will notify iyri when they are finished
     o collator will delay poison pill to threshers until all outstanding frames
      have been processed
     o fixed c2c
"""
__name__ = 'iyri'
__license__ = 'GPL v3.0'
__version__ = '0.2.1'
__date__ = 'January 2016'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'