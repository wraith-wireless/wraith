#!/usr/bin/env python

""" widgets: gui super classes

includes panel.py, the definition of gui super classes and the icons folder

widgets 0.0.3
 desc: gui description
 includes: icons folder, panel 0.13.7
 changes:
  - scrubbed and removed circular, redundant, confusing code
  - removed instances of pack gepmetry manager so only grid geometry is used
  - migrated to ttk
  - added sorting functionality to the internal treeview column headers at the
    TabularPanel class
  - added right mouse button binding to the internal treeview at the TabularPanel class
  - added critical section support at the DBPollingPanel
  - added busy/normal cursor display at the Panel class
"""
__name__ = 'utils'
__license__ = 'GPL v3.0'
__version__ = '0.0.2'
__date__ = 'March 2015'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Production'