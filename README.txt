WRAITH: Wireless assault, reconnaissance, collection and exploitation toolkit.

    You knew that I reap where I have not sown and gather where I scattered no seed?

MODULES: Currently consists of four components/modules

1) Radio: 802.11 network interface objects and functions

Objects/functions to manipulate wireless nics and parse 802.11 captures.
Partial support of 802.11-2012

Currently Supported
802.11a\b\g

Partially Supported
802.11n

Not Supported
802.11s\y\u\ac\ad\af

2) Suckt: Small Unit Capture/Kill Team (Wraith Sensor)

Suckt is a 802.11 sensor consisting of an optional collection radio (i.e.
spotter), a mandatory reconnaissance radio (i.e. shooter) and an RTO which relays
collected data to Nidus, the data storage system (i.e. HQ). Suckt collects data
in the form of raw 802.11 packets with the reconnaissance (and collection if present)
radios, forwarding that date along with any geolocational data (if a gps device
is present) to higher. The reconnaissance radio will also partake in assaults in
directed to.

3) Nidus: SocketServer collecting data from Wasp sensors

Nidus is the Data Storage manager processing data received from Suckt

4) gui: non-operational gui

REQUIREMENTS:
o linux (preferred 3.x kernel, tested on 3.13.0-43)
 - NOTE: some cards i.e. rosewill usb nics were not fully supported through iw
   on earlier kernels
o Python 2.7
o iw 3.17
o postgresql 9.x (tested on 9.3.5)
o pyscopg 2.5.3
o mgrs 1.1

ARCHITECTURE/HEIRARCHY:
wraith/                Top-level package
    __init__.py          this file - initialize the top-level (includes misc functions)
    wraith-rt.py         the gui
    LICENSE              software license
    README.txt           details
    CONFIGURE.txt        setup details
    widgets              gui subpackage
        icons            icons folder
        __init__.py      initialize widgets subpackage
        panel.py         defines Panel and subclasses for gui
    radio                subpackage for radio/radiotap
        __init__.py      initialize radio subpackage
        bits.py          bitmask related funcs, bit extraction functions
        iwtools.py       iwconfig, ifconfig interface and nic utilities
        iw.py            iw 3.17 interface
        radiotap.py      radiotap parsing
        mpdu.py          IEEE 802.11 MAC (MPDU) parsing
        infoelement.py   contstants for mgmt frames
        channels.py      802.11 channel, freq utilities
        mcs.py           mcs index functions
        oui.py           oui/manuf related functions
    suckt                subpackage for wraith sensor
        __init__.py      initialize suckt package
        suckt.conf       configuration file for wasp
        suckt.log.conf   configuration file for wasp logging
        suckt.py         primary module
        internal.py      defines the Report class
        rdoctl.py        radio controler with tuner, sniffer
        rto.py           data collation and forwarding
        sucktd           sucktd daemon
    nidus                subpackage for datamanager
        __init__.py      initialize nidus package
        nidus.conf       nidus configuration
        nidus.log.conf   nidus logging configuration
        nidus.py         nidus server
        nidusd           nidus daemon
        nmp.py           nidus protocol definition
        nidusdb.py       interface to storage system
        simplepcap.py    pcap writer
        nidus.sql        sql tables definition
