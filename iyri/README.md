# Iyri: 802.11 Sensor

## 1 DESCRIPTION:
Iyri is a 802.11 sensor and processor.

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
