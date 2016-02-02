# Iyri v 0.2.1: 802.11 Sensor

## 1 DESCRIPTION:
Iyri is a 802.11 sensor and processor. It can be configured to work with one or two wireless network interface cards (hereafter referred to as radios). It consists of a mandatory radio (Abad) which can receive or transmit and an optional radio (Shama) for receiving only. Additionally, Iyri allows for an optional GPS device. Iryi will parse data from the radio(s) (in the form of raw frames) as well as GPS data (locational and device), wireless nic information and system/platform information and store this data in a Postgresql database (nidus). 
 * Iyri requires root to run although one can configure iyrid to run as local user after the raw socket has been bound
 * Iyri can be configured at startup using iyri.conf and allows for control during operation over netcat, telnet etc or programmatically over a socket. 
 * Iyri can be started as service with iyrid (sudo service iyrid start) or via python (sudo python iyri.py)
 * Iyri logs informational messages and warnings/errors to /var/log/wraith/iyri.log
 * Each radio can be configured/controlled to run in scan, listen, hold, pause modes

NOTE: It is recommended to only use the Shama radio for collection during times Abad is transmitting as using both radios at the same time to scan can result in dropped packets. If traffic is spare though, both radios can be used. 

## 3. Setup, Configuration and Control

### a. Dependencies: 
 * linux (tested on 3.13.x kernel)
 * Python 2.7
 * iw 3.17 located at /usr/sbin/iw
 * postgresql 9.x
 * pyscopg > 2.6
 * mgrs 1.1
 * macchanger 1.7.0
 * dateutil 2.3

### b. Setup
At present, Iyri, like Wraith, must be manually installed. See Configuration.txt in the Wraith directory to setup nidus, the Postgresql database. To setup Iyri: 

### i. Install the following dependencies:
 * Timestamp conversion: dateutil v2.3 at https://pypi.python.org/pypi/python-dateutil
 * Postgresql DB API: psycopg2 v2.5.4 at https://pypi.python.org/pypi/psycopg2
 * Lat/Lon conversion: mgrs v1.1 https://pypi.python.org/packages/source/m/mgrs/mgrs-1.1.0.tar.gz
   - may require python-setuptools
 * Spoofed Mac Addresses macchanger v1.7.0  http://www.gnu.org/software/macchanger
 * iw: parses the output as produced by v3.17 https://www.kernel.org/pub/software/network/iw/iw-3.17.tar.xz

### ii. Python Files
Iyri requires all files in the iyri directory as well as those in the utils and wifi directories. Iyri currently uses a oui text file stored in data directory - this can be configured (see below) to utilze any directory you choose

### iii. Configure System
Before first use, the logging and service need to be set up. 
* Configure iyrid
```shell
sudo cp ...pathtowraith.../iyri/iyrid /etc/init.d/iyri
cd /etc/init.d
sudo chown root:root iyrid
sudo chmod 755 iyrid
```
You should use sys-rc-conf or chkconfig and verfiy that iyrid is not configured to run on boot
* Configure Logging
```shell
cd /var/logs
mkdir wraith
sudo chown <user>:adm wraith
chmod 750 wraith
cd wraith
touch iyri.log
```
It is recommended to run iyri as a service

### c. Configuration
Using iyri.conf, there are several configurations that can be made prior to running Iyri. Any changes to iyri.conf will not be reflected until Iyri is restarted.

#### i. Defining Source(s)
Radios are definied in the Abad (required) section and Shama (optional) section. Each radio will have the following configuration options. 

 * nic: the wireless nic to use i.e. wlan0, ath0 etc
 * paused: (optional) start in paused mode or scan (default) mode
 * spoof: (optional) spoofed mac address to use
 * record: (optional) writes raw frames (default) to database or only writes parsed data
 * Antenna Definition (optional) information currently stored in the database with the hope that in future versions it can be used to aid geolocation among other things but at present is only used to highlight different radio/antenna configurations and their collection results.
   - antennas: number of antennas
   - gain: gain in dBi
   - type: examples include omni, patch, yagi
   - loss: loss in dBm from cables etc
   - xyz: currently still in testing mode, defines the rotation of the antenna along three axis (see iyri.conf for descriptions of each axis).
 * desc: brief desc of the radio
 * Scan routine defines the initial scan routine to follow
  - dwell: time to stay on each channel in seconds. At present the radio will stay on each channel for the same time but I hope to add adaptive dwells to future versions where the dwell times for each channel will change according to the amount of traffic on the channel.
  - scan: channels to scan. See below for channel list specifications
  - pass: channels not to scan. Any channels specified in pass will override scan specifications. See below for channel list specifications
  - scan_start (optional): the first channel. defined as 'ch:width' where channel is numeric and width is oneof {None,HT20,HT40-,HT40+}

##### a. Channel List Definition:
Scan and pass configurations are specified by channel lists. Channel lists are defined as channels:widths where channels can be defined:
 * A single channel or empty. Empty specifies all channels in scan and no channels in pass
 * a list of ',' seperated channels i.e 1,6,11
 * a range defined lower-upper i.e. 1-14
 * a band preceded by a 'B' i.e. B.24 or B5
and widths can be HT, NOHT, ALL (or empty for all). Examples:
 * scan = --> scan all channels and all widths
 * scan = 1,6,11:NOHT --> scan channels 1, 6 and 11 at width = 20
 * scan = B2.4:ALL --> scan ISM channels at all widths

#### ii. Defining GPS
GPS can be defined as a device with polling fixed = no or a static location fixed = yes. 
 * fixed: use a hardcoded lat/lon or use a device and poll
 * port: port the gps device is listening to
 * devid: the device id of the gps (of the form XXXX:XXXX)
 * poll: poll time in seconds
 * epx: minimum ellipitical error to accept. inf specifies that everything is accepted
 * epy: minimum ellipitical error to accept. inf specifies that everything is accepted
 * lat: (if fixed = yes) hardcoded latitude
 * lon: (if fixed = yes) hardcoded longitude
 * alt: (if fixed = yes) hardcoded elevation
 * heading: (if fixed = yes) hardcoded direction

#### iii. Defining Storage
Determines DB location and DB parameters.
 * host: address of DB
 * port: port DB is listening to
 * db: name of DB
 * user: user account Iyri will use
 * pwd: password for user account

#### iv. Defining Local Parameters
Miscellaneous parameters
 * region: two-alphanumeric sequence specifying regulatory domain to use
 * C2C; port for c2c service to listen on
 * OUI: path of oui file (soon to be removed)
 * maxt: maximum number of threshers to allow. A suggested value. 

### d. Control (C2C)
Iyri defines a simplistic command and control service where users can use a socket via netcat or telnet to send basic commands to the sensor. Iyri will only allow one connection to the C2C at a time. No authentication is present, just connect to the address and port. Messages to the sensor must be in the following format:

!\<id\> \<cmd\> \<radio\> [params]\\n
 
where:
 * id is an unique (for the current session) integer
 * cmd is oneof {state|scan|hold|listen|pause|txpwr|spoof}
 * radio is oneof {both|all|abad|shama} where both enforces abad and shama radios and all only enforces shama if present
 * params are:
  - of the format channel:width if cmd is listen
  - of the format pwr:option if cmd is txpwr where pwr is dBm and option is oneof {fixed|auto|limit}
  - a mac address if cmd is spoof

Iyri will notify the client if the cmd specified by id is valid or invalid with:

OK \<id\> [\001output\001]

ERR \<id> \001Reason for Failure\001

## 4. Architecture
