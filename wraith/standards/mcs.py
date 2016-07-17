#!/usr/bin/env python

""" mcs.py: mcs index functions 

NOTE: does not support VHT/802.11ac
"""
__name__ = 'mcs'
__license__ = 'GPL v3.0'
__version__ = '0.0.2'
__date__ = 'July 2016'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

# modulation and coding rate Table 20-30 thru 20-35 Std (these repeat 0-7, 8-15 etc)
MCS_HT_INDEX = ["BPSK 1/2",
                "QPSK 1/2",
                "QPSK 3/4",
                "16-QAM 1/2",
                "16-QAM 3/4",
                "64-QAM 2/3",
                "64-QAM 3/4",
                "64-QAM 5/6"]

# mcs rates see tables 20-30 thru 20-37 of Std
# TODO: add up table 20-44
MCS_HT_RATES = [{20:{1:6.5,0:7.2},40:{1:13.5,0:15}},     # mcs index 0
                {20:{1:13,0:14.4},40:{1:27,0:30}},       # mcs index 1
                {20:{1:19.5,0:21.7},40:{1:40.5,0:45}},   # mcs index 2
                {20:{1:26,0:28.9},40:{1:54,0:60}},       # mcs index 3
                {20:{1:39,0:43.3},40:{1:81,0:90}},       # mcs index 4
                {20:{1:52,0:57.8},40:{1:108,0:120}},     # mcs index 5
                {20:{1:58.5,0:65},40:{1:121.5,0:135}},   # mcs index 6
                {20:{1:65,0:72.2},40:{1:135,0:150}},     # mcs index 7
                {20:{1:13,0:14.4},40:{1:27,0:30}},       # mcs index 8
                {20:{1:26,0:28.9},40:{1:54,0:60}},       # mcs index 9
                {20:{1:39,0:43.3},40:{1:81,0:90}},       # mcs index 10
                {20:{1:52,0:57.8},40:{1:108,0:120}},     # mcs index 11
                {20:{1:78,0:86.7},40:{1:162,0:180}},     # mcs index 12
                {20:{1:104,0:115.6},40:{1:216,0:240}},   # mcs index 13
                {20:{1:117,0:130.0},40:{1:243,0:270}},   # mcs index 14
                {20:{1:130,0:144.4},40:{1:270,0:300}},   # mcs index 15
                {20:{1:19.5,0:21.7},40:{1:40.5,0:45}},   # mcs index 16
                {20:{1:39,0:43.3},40:{1:81,0:90}},       # mcs index 17
                {20:{1:58.5,0:65},40:{1:121.5,0:135}},   # mcs index 18
                {20:{1:78,0:86.7},40:{1:162,0:180}},     # mcs index 19
                {20:{1:117,0:130},40:{1:243,0:270}},     # mcs index 20
                {20:{1:156,0:173.3},40:{1:324,0:360}},   # mcs index 21
                {20:{1:175.5,0:195},40:{1:364.5,0:405}}, # mcs index 22
                {20:{1:195,0:216.7},40:{1:405,0:450}},   # mcs index 23
                {20:{1:26,0:28.9},40:{1:54,0:60}},       # mcs index 24
                {20:{1:52,0:57.8},40:{1:108,0:120}},     # mcs index 25
                {20:{1:78,0:86.7},40:{1:162,0:180}},     # mcs index 26
                {20:{1:104,0:115.6},40:{1:216,0:240}},   # mcs index 27
                {20:{1:156,0:173.3},40:{1:324,0:360}},   # mcs index 28
                {20:{1:208,0:231.1},40:{1:432,0:480}},   # mcs index 29
                {20:{1:234,0:260},40:{1:486,0:540}},     # mcs index 30
                {20:{1:260,0:288.9},40:{1:540,0:600}}]   # mcs index 31

def mcs_coding(i):
    """
     given the mcs index i, returns a tuple (m=modulation & coding rate,s= # of
     spatial streams)

     :param i: mcs index
     :returns: tuple t = (modulation & coding rate,number of spatial streams)
    """
    if i < 0 or i > 31:
        raise ValueError("mcs index {0} must be 0 <= i <= 32".format(i))
    (m,n) = divmod(i,8)
    return MCS_HT_INDEX[n],m+1

def mcs_rate(i,w,gi):
    """
     given the mcs index i, channel width w and guard interval returns the data rate

     :param i: mcs index
     :param w: channel width
     :param gi: guard interval (0 for short, 1 for long)
     :returns: data rate
    """
    if i < 0 or i > 31: raise ValueError("mcs index {0} must be 0 <= i <= 32".format(i))
    if not(w == 20 or w == 40): raise ValueError("mcs width {0} must be 20 or 40".format(w))
    if gi < 0 or gi > 1: raise ValueError("mcs guard interval {0} must be 0:short or 1:long".format(gi))
    return MCS_HT_RATES[i][w][gi]

def mcs_width(i,dr):
    """
     given mcs index i & data rate dr, returns channel width and guard interval

     :param i: mcs index
     :param dr: data rate
     :returns: tuple t = (channel width,guard interval)
    """
    if i < 0 or i > 31: raise ValueError("mcs index {0} must be 0 <= i <= 32".format(i))
    for w in MCS_HT_RATES[i]:
        for gi in MCS_HT_RATES[i][w]:
            if MCS_HT_RATES[i][w][gi] == dr:
                return w,gi
    return None
