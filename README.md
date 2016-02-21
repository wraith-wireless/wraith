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
 * linux (tested on 3.13.x kernel)
   - NOTE: some cards i.e. rosewill usb nics were not fully supported through iw
     on earlier 3.13.x kernels
 * Python 2.7
 * iw 3.17
 * postgresql 9.x (tested on 9.3.5)
 * pyscopg > 2.6
 * mgrs 1.1

## 3. MODULES: Currently consists of three main components/modules: Wifi, Iyri and
the GUI and three secondary modules: utils, widgets, and nidus.

###  a. wifi (v 0.0.5): 802.11 network interface objects and functions

Objects/functions to manipulate wireless nics and parse 802.11 captures.

#### Standards
* Currently Supported: 802.11a\b\g
* Partially Supported: 802.11n
* Not Supported: 802.11s\y\u\ac\ad\af

### b. iryi (v 0.2.1): Wraith Sensor

Iryi is a 802.11 sensor consisting of an optional radio (shama), and a mandatory
radio (abad). 802.11 packets are stored in a circular buffer, parsed and inserted
in the database. Any geolocational data is also stored (if a gps device is present).

NOTE:
In earlier versions < 0.1.x, Iyri did not handle database writes/updates. Rather
this was handled by an additional module colocated on the same system as database
that the sensor would pass data to. It was with great relunctance that I removed
this 'mediator', and moved database functionality directly to the sensor, primarily
for two reasons:
 * it would restrict wraith to a single platform i.e. expanding to a central
  database and multiple sensors will be very difficult.
 * sensors could no longer be used on 'minimal' systems i.e. routers and other embedded
  systems
However, there were two primary reasons for doing so:
 * I wanted to push more autonomy and intelligence into the sensor which would
   require the sensor to parse out radiotap and mpdu (no point in doing this twice)
 * frames (as strings) were being passed through multiple connection, queues and
   sockets before they eventually made their way to the mediator causing a major
   delay in processing

### d. wraith-rt: GUI

At present the gui provides limited functionality and is very much in the
developlmental stage. The gui can be used to:
 * start/stop services: Postgresql, Iyri
 * configure Wraith, Iyri
 * view current sessions, current wirless nics and Iyri's log
 * fix database errors, delete all entries in database
 * RF math & land nav conversions, RF math calculations

### e. utils: utility functionality

Provides various functions used throughout wraith. See Architecture section for
further information.

### f. widgets: gui super classes

Defines a graphic suite based on Tkinter/ttk where a set of non-modal panels operate
under the control of a master panel and execute tasks, display information
independently of or in conjuction with this panel and other panels. (Think undocked
windows).

### g. nidus: database

Provides the Postgresql database schema, nidus.sql.

## 4. ARCHITECTURE/HEIRARCHY: Brief Overview of the project file structure

* wraith:               Top-level package
 - \_\_init\_\_.py      initialize the top-level
 - wraith-rt.py         the main Panel gui
 - subpanels.py         child panels
 - wraith.conf          gui configuration file
 - LICENSE              software license
 - README.md            this file
 - CONFIGURE.txt        setup details
 - TODO                 todos for each subpackage
 * widgets:             gui subpackage
     *  icons:          icons folder
     -  \_\_init\_\_.py initialize widgets subpackage
     -  panel.py        defines Panel and subclasses for gui
 * utils:                utility functions
    -  \_\_init\_\_.py  initialize utils subpackage
    - bits.py           bitmask functions
    - timestamps.py     timestamp conversion functions
    - landnav.py        land navigation utilities
    - cmdline.py        various cmdline utilities for testing processes
    - simplepcap.py     pcap writer
    - brine.py          support for pickling connection objects
    - valrep.py         validation and reporting functionality
 *  data:               data folder
    - oui.txt           tab seperated oui manufacturer file
 *  wifi:               subpackage for wifi related
     - \_\_init\_\_.py  initialize radio subpackage
     - interface:       initialize interface subpackage
        + iw.py         iw 3.17 interface
        + oui.py        oui/manuf related functions
        + radio.py      Radio consolidates iwtools.py, iw.py
        + sockios_h     definitions of the socket-level I/O control calls.
        + nl80211_h     nl82011 constants
        + if_h          inet definition
     - standards:       initialize standards subpackage
        + radiotap.py   radiotap parsing
        + mpdu.py       IEEE 802.11 MAC (MPDU) parsing
        + dott1u.py     contstants for 802.11u (not currently used)
        + channels.py   802.11 channel, freq utilities
        + mcs.py        mcs index functions
 * nidus:               database schema
     - \_\_init\_\_.py  initialize nidus subpackage
     - nidus.sql        database definition
 *  iyri:               subpackage for wraith sensor
     - \_\_init\_\_.py  initialize iyri package
     - iyri.conf        configuration file for iyri
     - iyri.log.conf    configuration file for iyri logging
     - iyri.py          primary module
     - constants.py     defines several constants used by iryi
     - gpsctl.py        GPS device handler
     - rdoctl.py        radio controler
     - tuner.py         radio scanner
     - collate.py       data collation and forwarding
     - thresh.py        Thresher process for parsing/writing frames
     - iyrid            iyri daemon