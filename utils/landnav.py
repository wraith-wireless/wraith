#!/usr/bin/env python

""" landnav.py: land navigation utilities """

__name__ = 'landnav'
__license__ = 'GPL v3.0'
__version__ = '0.3.2'
__date__ = 'November 2013'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

import mpl_toolkits.basemap.pyproj as pyproj
import mgrs
import math

# GLOBALS
_GEOD = pyproj.Geod(ellps='WGS84')
_MGRS = mgrs.MGRS()

def validMGRS(location):
    """ attempts to convert mgrs location to lat lon, returns false on failure """
    try:
        _MGRS.toLatLon(location)
    except:
        return False
    else:
        return True

def convertazimuth(fNorth,tNorth,azimuth,dd):
    """
     converts an azimuth from one north to another
     fNorth,tNorth are one of {'true','grid','magnetic'}
     azimuth is 0 <-> 360
     dd is the declination diagram, a dict of the form:
      {'decl'->angledir,'g2m':grid to magnetic angle'g2t':grid to true angle}
     NOTE: no error checking is done on validity of parameters
    """
    if dd['decl'] == 'easterly':
        # mag to grid, add g2m, grid to mag subtract g2m
        # mag to true, add (g2m-g2t), true to mag, subtract (g2m-g2t)
        # true to grid, add g2t, grid to true, subtract g2t  
        if fNorth == 'magnetic':
            if tNorth == 'grid': return (azimuth + dd['g2m']) % 360
            else: return (azimuth + (dd['g2m'] - dd['g2t'])) % 360
        elif fNorth == 'true':
            if tNorth == 'grid': return (azimuth + dd['g2t']) % 360
            else: return (azimuth - (dd['g2m']-dd['g2t'])) % 360
        else:
             # fNorth is grid
            if tNorth == 'magnetic': return (azimuth - dd['g2m']) % 360
            else: return (azimuth - dd['g2t']) % 360
    elif dd['decl'] == 'westerly':
        # do the opposite of above
        if fNorth == 'magnetic':
            if tNorth == 'grid': return (azimuth - dd['g2m']) % 360
            else: return (azimuth - (dd['g2m']-dd['g2t'])) % 360
        elif fNorth == 'true':
            if tNorth == 'grid': return (azimuth - dd['g2t']) % 360
            else: return (azimuth + (dd['g2m']-dd['g2t'])) % 360
        else: # fNorth is grid
            if tNorth == 'magnetic': return (azimuth + dd['g2m']) % 360
            else: return (azimuth + dd['g2t']) % 360

def dist(sp,ep):
    """
     determines the distance (in meters) between pts sp and ep and the bearing
     from sp to ep sp and ep must be in mgrs coordinates
    """
    try:
        (sLat,sLon) = _MGRS.toLatLon(sp)
        (eLat,eLon) = _MGRS.toLatLon(ep)
        a,a2,d = _GEOD.inv(sLon,sLat,eLon,eLat)
    except:
        raise ValueError, "Invalid MGRS point"
    else:
        return d,a
            
def terminus(pt,lob,dist):
    """
     determines the end point and back azimuth given a distance in meters from 
     the collection site location and this lob
       pt is a mgrs coordinate
       lob is a degree (True North)
       dist is in meters
     returns the tuple lat,lon,mgrs,backazimuth
    """
    # convert site mgrs to (lat,lon) determine end point and convert back to
    # mgrs before returning
    (lat,lon) = _MGRS.toLatLon(pt)
    lon2,lat2,baz = _GEOD.fwd(lon,lat,lob,dist)
    return lat2,lon2,_MGRS.toMGRS(lat2,lon2),(baz%360)

def findcut(p1,b1,p2,b2):
    """
     determines the cut, the intersection between two points p1 and p2 given bearings
     b1 and b2
     Points p1 and p2 must be mgrs
     Bearings b1 and b2 must be True North and in degrees between and 0 and 359.9999.....
     NOTE:
      if sin(angle1) or sin(angle2) = 0 there are infinite solutions
      if sin(angle1) * sin(angle2) < 0 the solution is ambiguous
     FROM Chris Veness at http://www.movable-type.co.uk/scripts/latlong.html
    """
    # convert to lat/lon
    (lat1,lon1) = _MGRS.toLatLon(p1)
    (lat2,lon2) = _MGRS.toLatLon(p2)

    # convert to radians
    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)
    b13 = math.radians(b1)
    b23 = math.radians(b2)
    
    dLat = lat2-lat1
    dLon = lon2-lon1

    # could use already predefined distance function in GEOD for this??    
    dist12 = 2 * math.asin(math.sqrt(math.sin(dLat/2)*math.sin(dLat/2) +\
                           math.cos(lat1)*math.cos(lat2)*math.sin(dLon/2)*math.sin(dLon/2)))
    if dist12 == 0: return None
    
    bA = math.acos((math.sin(lat2) - math.sin(lat1)*math.cos(dist12)) / (math.sin(dist12)*math.cos(lat1)))
    if math.isnan(bA): bA = 0
    bB = math.acos((math.sin(lat1) - math.sin(lat2)*math.cos(dist12)) / (math.sin(dist12)*math.cos(lat2)))
    
    if math.sin(lon2-lon1) > 0:
        b12 = bA
        b21 = 2 * math.pi - bB
    else:
        b12 = 2 * math.pi - bA
        b21 = bB
    
    alpha1 = (b13 - b12 + math.pi) % (2 * math.pi) - math.pi  # angle 2-1-3
    alpha2 = (b21 - b23 + math.pi) % (2 * math.pi) - math.pi  # angle 1-2-3

    # check solution outcomes
    if math.sin(alpha1) == 0 and math.sin(alpha2) == 0: return float('Inf') # infinite
    if math.sin(alpha1)*math.sin(alpha2) < 0: return float('NaN')           # ambiguous
    
    # take abs value here ?
    alpha3 = math.acos(-math.cos(alpha1) * math.cos(alpha2) + math.sin(alpha1) * math.sin(alpha2) * math.cos(dist12))
    dist13 = math.atan2(math.sin(dist12) * math.sin(alpha1) * math.sin(alpha2),
                        math.cos(alpha2) + math.cos(alpha1) * math.cos(alpha3))
    lat3 = math.asin(math.sin(lat1) * math.cos(dist13) + math.cos(lat1) * math.sin(dist13) * math.cos(b13))
    dLon13 = math.atan2(math.sin(b13) * math.sin(dist13) * math.cos(lat1),
                        math.cos(dist13) - math.sin(lat1) * math.sin(lat3))
    lon3 = lon1 + dLon13
    lon3 = (lon3 + 3 * math.pi) % (2 * math.pi) - math.pi
    
    return _MGRS.toMGRS(math.degrees(lat3),math.degrees(lon3))

def quadrant(p1,b1,p2,b2,err=3):
    """
     determines a quadrant, 4 points defining an area, which are the intersections
     between points p1 and p2 given bearings b1 and b2 with err degrees of error
     calculated in. For example, given an err of 3, the quadrant will be formed
     by b1+3 & b2+3, b1-3 & b2+3, b1-3 & b2+3, b1-3 & b2-3
     Points p1 and p2 must be tuples (lat,lon)
     Bearings b1 and b2 must be in degrees between and 0 and 359.9999.....
     NOTE:
      It is assumed that it has been found that b1 and b2 intersect
    """
    # get the error bearings
    b1Min = (b1-err) % 360
    b1Plus = (b1+err) % 360
    b2Min = (b2-err) % 360
    b2Plus = (b2+err) % 360
    
    # calcuate intersections for each
    q1 = findcut(p1,b1Min,p2,b2Min)
    q2 = findcut(p1,b1Min,p2,b2Plus)
    q3 = findcut(p1,b1Plus,p2,b2Min)
    q4 = findcut(p1,b1Plus,p2,b2Plus)
    
    return [q1,q2,q3,q4]
