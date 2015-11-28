![](widgets/icons/wraith-banner.png?raw=true)
# WRAITH: Wireless Reconnaissance And Intelligent Target Harvesting.

> "You knew that I reap where I have not sown and gather where I scattered no seed."

## 1 DESCRIPTION:
Attack vectors, rogue devices, interfering networks are best visualized and identified
over time. Current tools i.e. Kismet, Aircrack-ng and Wireshark are excellent tools
but none are completely suitable for collecting and analyzing the 802.11 environment
over a period of time without that is, implementing a custom interface.

While originally intending to develop such a custom interface to one or more Kismet
based sensors, Wraith evolved. Kismet did not offer enough information, Wireshark
offered too much. Wraith is an attempt to develop a toolsuite that eases the
collection, collation and analysis of temporal 802.11 data in order to provide
administrators with the ability to view their network(s) from a bird's eye view and
drill down as necessary to a single device. Wraith allows the user to decide what
data to view, how to view it and 'when' to view it.

## 2. REQUIREMENTS: 
 * linux (preferred 3.x kernel, tested on 3.13.0-65)
   - NOTE: some cards i.e. rosewill usb nics were not fully supported through iw
     on earlier 3.13.x kernels
 * Python 2.7
 * iw 3.17
 * postgresql 9.x (tested on 9.3.5)
 * pyscopg 2.6
 * mgrs 1.1
 * macchanger 1.7.0

## 3. MODULES: Currently consists of three components/modules

###  a. Wifi (v 0.0.5): 802.11 network interface objects and functions

Objects/functions to manipulate wireless nics and parse 802.11 captures.
Partial support of 802.11-2012

#### Standards
* Currently Supported: 802.11a\b\g
* Partially Supported: 802.11n
* Not Supported: 802.11s\y\u\ac\ad\af

### b. Iryi (v 0.2.0) : Wraith Sensor

Iryi is a 802.11 sensor consisting of an optional radio (shama), a mandatory
radio (abad) and a Collator which relays collected data to the backend database.
802.11 packets are stored in a circular buffer, parsed and inserted in the database.
Any geolocational data is also stored (if a gps device is present).

NOTE:
In earlier versions < 0.1.x, Iyri did not handle database writes/updates. Rather
this was handled by a an additional module colocated with the database (on the same
system) that the sensor would pass data to. It was with great relunctance that I
removed this 'mediator', and moved database functionality directly to the sensor,
primarily as it would restrict wraith to a single platform i.e. expanding to a
central database and multiple sensors will be very difficult. However, there were two primary reasons for doing so:
* I wanted to push more autonomy and intelligence into the sensor which would
  require the sensor to parse out radiotap and mpdu (no point in doing this twice)
* frames were being passed through multiple connection, queues and sockets before
  they eventually made their way to the mediator causing a major delay in processing

### d. wraith-rt: GUI

In progress gui. Currently configured to provide start/stop of services, display
and editing of configuration files, some manipulation of backened storage.

## 4. ARCHITECTURE/HEIRARCHY: Brief Overview of the project file structure

* wraith/               Top-level package
 - \_\_init\_\_.py      initialize the top-level
 - wraith-rt.py         the main Panel gui
 - subpanels.py         child panels
 - wraith.conf          gui configuration file
 - LICENSE              software license
 - README.md            this file
 - CONFIGURE.txt        setup details
 - TODO                 todos for each subpackage
 * widgets              gui subpackage
     *  icons           icons folder
     -  \_\_init\_\_.py initialize widgets subpackage
     -  panel.py        defines Panel and subclasses for gui
 * utils                utility functions
    -  \_\_init\_\_.py  initialize utils subpackage
    - bits.py           bitmask functions
    - timestamps.py     timestamp conversion functions
    - landnav.py        land navigation utilities
    - cmdline.py        various cmdline utilities for testing processes
    - simplepcap.py     pcap writer
    - brine.py          support for pickling connection objects
 *  wifi                subpackage for wifi related
     - \_\_init\_\_.py  initialize radio subpackage
     - iwtools.py       iwconfig, ifconfig interface and nic utilities
     - iw.py            iw 3.17 interface
     - radiotap.py      radiotap parsing
     - mpdu.py          IEEE 802.11 MAC (MPDU) parsing
     - dott1u.py        contstants for 802.11u (not currently used)
     - channels.py      802.11 channel, freq utilities
     - mcs.py           mcs index functions
     - oui.py           oui/manuf related functions
 * nidus                database schema
     - \_\_init\_\_.py  initialize nidus subpackage
     - nidus.sql        database definition
 *  iyri                subpackage for wraith sensor
     - \_\_init\_\_.py  initialize iyri package
     - iyri.conf        configuration file for iyri
     - iyri.log.conf    configuration file for iyri logging
     - iyri.py          primary module
     - constants.py     defines several constants used by iryi
     - gpsctl.py        GPS device handler
     - rdoctl.py        radio controler with tuner, sniffer
     - collate.py       data collation and forwarding
     - thresh.py        Thresher process for parsing/writing frames
     - iyrid            iyri daemon
 * deprecated
     - wraith.0.0.4.tar.gz client/version server
