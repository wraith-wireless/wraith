#!/usr/bin/env python

""" iyri: Wraith Sensor

Iyri is a 802.11 sensor consisting of an optional surveillance radio, a mandatory
reconnaissance radio and a Collator which relays collected data to the backend
database. Iryi collects/stores data in the form of raw 802.11 packets, along with
any geolocational data (if a gps device is present).

REVISIONS:
dyskt 0.1.4
 includes: dyskt 0.0.8, radio 0.0.4, collate 0.0.8, pf 0.0.6, dysktd, dyskt.conf,
  dyskt.log.conf dyskt
 changes:
  - consolidates radio related processes, sniffer and tuner, into a the RadioController
    class
   o cleans up the interprocess communication and minimizes the number of
     shared communication objects and the number of sub process
   o radio class now subclasses mp.Process

dyskt 0.1.5
 desc: utilizes a new internal communication SOP to streamline and simplify
  interprocess communications
 includes: dyskt 0.0.10 internal 0.0.1 rto 0.0.11, rdoctl 0.0.5
  dyskt.conf dyskt.log.conf dysktd
 changes:
  - streamlined inter-process communication methods/objects
   o replaced internal communcation (messages to RTO) Pipes with a single Queue
   o removed the Queue used by children to communicate with DySKT and made
    each connection dual-ended
  - scan pattern config modified
   o added band and width specification to scan and pass configuration
   o added optional initial channel and channel width
  - modified gps processing
   o removed pf.py and pushed gps polling as a thread into rto
 - removed signal handling as a means to pass commands
   o need to code command interface
 - added mac spoofing cability on start of each radio
 - added platform/system details
 - added regulatory domain setting/resetting capability to sensor
 - modified antenna specification to support more than 1 antenna
 - removed internal.py and the Report class, using just a simple Tuple instead
 - modified gps poller to send front line trace even in cases of static gps
   configuration. Determine if:
    a) this will slow down RTO processing of frames
    b) if it will result in unneccessary db storage or traffic
 - check specified nic for wireless capabilities/presence during conf processing
 - fixed issue with radio being reset after initialization errors
 - compresssed/encrypted comms with Nidus
   o uses secure socket layer to send data to Nidus
   o zlib library to compress frames (hardcoded to 14K and 1 sec delay)

dyskt 0.1.6
 desc: added command interface through a socket
 includes: dyskt 0.0.11 rto 0.0.12 rdoctl 0.0.8 dyskt.conf dyskt.log.conf dysktd
 changes:
  - added pause option on start (per radio)
  - dysktd manually removes created pidfile on exit & now configure to run as root
  - added command socket capabilities (see dyskt.py for c2c protocol)
   o allows for state, pause, scan, hold, listen commands
   o need to add functionality to txpwr and spoof
  - gpsd will only send 1 frontline trace if static
  - added timeout in RadioController to radio socket (in the event of no wireless
    traffic)
  - fixed two programmer errors
    o frames were not being sent in the event of error/stoppage. Added
     sending of bulked frames when radio goes to paused state as well
    o possibility of a never-ending scan on same channel when receiving tokens
     from DySKT

 iyri 0.2.0
  desc: Utilizes a "circular buffer" IOT remove the inherent inefficiency from
   passing frame(s) through multiple connections and functions including the
   inefficiency involved in making frequent copies of the frame(s). Because
   python does not have a "PACKET_MMAP" flag for sockets (at least not that I
   can find), the circular buffer is created by wrapping a multiprocessing.Array
   of bytes with a memoryview and using the socket.recv_from method to 'put'
   frames onto the "buffer". Children then utilize shared access to the "buffer"
   to process the frames accordingly.
  includes: iyri 0.1.0 collator 0.1.0 rdoctl 0.1.0 iyri.conf iyri.log.conf iyrid
  changes:
   - no longer passes data to storage manager, rather writes directly to db
   - uses a memoryview to hold captured frames in a circular buffer
"""
__name__ = 'iyri'
__license__ = 'GPL v3.0'
__version__ = '0.2.0'
__date__ = 'September 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'
