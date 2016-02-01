# Iyri v 0.2.1: 802.11 Sensor

## 1 DESCRIPTION:
Iyri is a 802.11 sensor and processor. It can be configured to work with one or two wireless network interface cards (hereafter referred to as radios). It consists of a mandatory radio (Abad) which can receive or transmit and an optional radio (Shama) for receiving only. Additionally, Iyri allows for an optional GPS device. Iryi will parse data from the radio(s) (in the form of raw frames) as well as GPS data (locational and device), wireless nic information and system/platform information and store this data in a Postgresql database (nidus). 
 * Iyri requires root to run although one can configure iyrid to run as local user after the raw socket has been bound
 * Iyri can be configured at startup using iyri.conf and allows for control during operation over netcat, telnet etc or programmatically over a socket. 
 * Iyri can be started as service with iyrid (sudo service iyrid start) or via python (sudo python iyri.py)
 * Iyri logs informational messages and warnings/errors to /var/log/wraith/iyri.log

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

## 3. Setup and Configuration

### a. Setup
At present, Iyri, like Wraith, must be manually installed. 

### b. Configuration
