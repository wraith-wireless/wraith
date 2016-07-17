#!/usr/bin/env python

""" setup.py: install Wraith

Copyright (C) 2016  Dale V. Patterson (wraith.wireless@yandex.com)

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

Redistribution and use in source and binary forms, with or without modifications,
are permitted provided that the following conditions are met:
 o Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
 o Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
 o Neither the name of the orginal author Dale V. Patterson nor the names of any
   contributors may be used to endorse or promote products derived from this
   software without specific prior written permission.

"""

#__name__ = 'setup'
__license__ = 'GPLv3'
__version__ = '0.0.1'
__date__ = 'July 2016'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

from setuptools import setup, find_packages
import wraith

setup(name='wraith',
      version=wraith.__version__,
      description="Wireless Pentester Toolsuite",
      long_description="",
      url="",
      download_url="",
      author=wraith.__author__,
      author_email=wraith.__email__,
      maintainer=wraith.__maintainer__,
      maintainer_email=wraith.__email__,
      license=wraith.__license__,
      #classifiers=['Development Status :: 5 - Production/Stable',
      #             'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
      #             'Intended Audience :: Developers',
      #             'Intended Audience :: System Administrators',
      #             'Topic :: Security',
      #             'Topic :: Software Development',
      #             'Topic :: Software Development :: Libraries',
      #             'Topic :: Security',
      #             'Topic :: System :: Networking',
      #             'Topic :: Utilities',
      #             'Operating System :: POSIX :: Linux',
      #             'Programming Language :: Python',
      #             'Programming Language :: Python :: 2.7'],
    keywords='Linux Python wireless WLAN WiFi pentest',
    packages=find_packages(),
    #package_data={'wraith':['nlhelp/*.help','utils/data/*.txt']}
)
