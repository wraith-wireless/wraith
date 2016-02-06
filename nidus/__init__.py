#!/usr/bin/env python

""" nidus: Backend Database Definition

0.0.7
 desc: database schema
 includes: nidus.sql 0.0.15
 changes:
  - added frame_raw and malformed tables
  - added ssids table for multiple ssids in mgmt frames
  - changed beacon_ts from type bytea to numeric(19)
  - relaxed constraints to allow for invalid packets to be stored
"""
__name__ = 'nidus'
__license__ = 'GPL v3.0'
__version__ = '0.0.7'
__date__ = 'September 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'
