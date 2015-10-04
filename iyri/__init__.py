#!/usr/bin/env python

""" iyri: Wraith 802.11 Sensor

Iyri is a 802.11 sensor consisting of a mandatory radio (Abad) and an optional
radio (Shama). While Abad can receive/collect and transmit, Shama will only receive.
Iyri relays collected data to the backend database nidus, collects/stores data
from raw 802.11 packets and any geolocational data (if a gps device is present).

REVISIONS:
 0.2.0
  desc: Renamed as former concept of operations no longer applied. Utilizes a
  "circular buffer" IOT remove the inherent inefficiency from
   passing frame(s) through multiple connections and functions including the
   inefficiency involved in making frequent string copies of the frame(s).
   Because python does not have a "PACKET_MMAP" flag for sockets (at least not
   that I can find), the circular buffer is created by wrapping a MP Array
   of bytes with a memoryview and using the socket.recv_from method to 'put'
   frames onto the "buffer". Children then utilize shared access to the "buffer"
   to process the frames accordingly.
  includes: iyri 0.1.0 collator 0.1.1 rdoctl 0.1.0 geo 0.0.1 iyri.conf iyri.log.conf
  iyrid
  changes:
   - no longer passes data to storage manager, rather writes directly to db
   - now uses a process for the  GPSController rather than a thread
   - uses a memoryview to hold captured frames in a circular buffer
"""
__name__ = 'iyri'
__license__ = 'GPL v3.0'
__version__ = '0.2.1'
__date__ = 'October 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'
