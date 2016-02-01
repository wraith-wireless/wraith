# Iyri v 0.2.1: 802.11 Sensor

## 1 DESCRIPTION:
Iyri is a 802.11 sensor and processor. It can be configured to work with one or two wireless network interface cards (hereafter referred to as radios). It consists of a mandatory radio (Abad) which can receive or transmit and an optional radio (Shama) for receiving only. Additionally, Iyri allows for an optional GPS device. Iryi will parse data from the radio(s) (in the form of raw frames) as well as GPS data (locational and device), wireless nic information and system/platform information and store this data in a Postgresql database (nidus). 
 * Iyri requires root to run although one can configure iyrid to run as local user after the raw socket has been bound
 * Iyri can be configured at startup using iyri.conf and allows for control during operation over netcat, telnet etc or programmatically over a socket. 
 * Iyri can be started as service with iyrid (sudo service iyrid start) or via python (sudo python iyri.py)
 * Iyri logs informational messages and warnings/errors to /var/log/wraith/iyri.log
 * Each radio can be configured/controlled to run in scan, listen, hold, pause modes

NOTE: It is recommended to only use the Shama radio for collection during times Abad is transmitting as using both radios at the same time to scan can result in dropped packets. If traffic is spare though, both radios can be used. 

## 2. REQUIREMENTS: 
 * linux (tested on 3.13.x kernel)
 * Python 2.7
 * iw 3.17 located at /usr/sbin/iw
 * postgresql 9.x
 * pyscopg > 2.6
 * mgrs 1.1
 * macchanger 1.7.0
 * dateutil 2.3

## 3. Setup, Configuration and Control

### a. Setup
At present, Iyri, like Wraith, must be manually installed. See Configuration.txt in the Wraith directory to setup nidus, the Postgresql database and dependencies for Iyri.

### b. Configuration
Using iyri.conf, there are several configurations that can be made prior to running Iyri. Any changes to iyri.conf will not be reflected until Iyri is restarted.

#### i. Defining Source(s)
Radios are definied in the Abad (required) section and Shama (optional) section. Each radio will have the following configuration options. 

 * nic: the wireless nic to use i.e. wlan0, ath0 etc
 * paused: (optional) start in paused mode or scan (default) mode
 * spoof: (optional) spoofed mac address to use
 * record (optional) writes raw frames (default) to database or only writes parsed data
 * Antenna Definition (optional) information currently stored in the database with the hope that in future versions it can be used to aid geolocation among other things but at present is only used to highlight different radio/antenna configurations and their collection results.
   - antennas: number of antennas
   - gain: gain in dBi
   - type: examples include omni, patch, yagi
   - loss: loss in dBm from cables etc
   - xyz: currently still in testing mode, defines the rotation of the antenna along three axis (see iyri.conf for descriptions of each axis).
 * desc: brief desc of the radio
 * Scan routine defines the initial scan routine to follow
  - dwell: time to stay on each channel. At present the radio will stay on each channel for the same time but I hope to add adaptive dwells to future versions where the dwell times for each channel will change according to the amount of traffic on the channel.
  - scan: channels to scan
  - pass: channels not to scan. Any channels specified in pass will override scan specifications
  - scan_start: the first channel

### c. Control
