# Iyri: 802.11 Sensor

## 1 DESCRIPTION:
Iyri is a 802.11 sensor and processor. It consists of a mandatory radio (Abad) which can receive or transmit and an optional radio (Shama) for receiving only. Additionally, Iyri allows for an optional GPS device. Iryi will parse data from the radio(s) (in the form of raw frames) as well as GPS data (locational and device), wireless nic information and system/platform information and store this data in a Postgresql database (nidus). 
 * Iyri can be configured at startup using iyri.conf and allows for control during running over netcat, telnet etc or programmatically over a socket. 

NOTE: It is recommended to only use the Shama radio for collection during times Abad is transmitting as using both radios at the same time to scan can result in dropped packets. If traffic is spare though, both radios can be used. 

## 2. REQUIREMENTS: 
 * linux (tested on 3.13.x kernel)
   - NOTE: some cards i.e. rosewill usb nics were not fully supported through iw
     on earlier 3.13.x kernels
 * Python 2.7
 * iw 3.17 located at /usr/sbin/iw
 * postgresql 9.x
 * pyscopg > 2.6
 * mgrs 1.1
 * macchanger 1.7.0

## 3. Setup and Configuration
