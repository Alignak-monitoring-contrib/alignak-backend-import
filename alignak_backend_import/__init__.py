#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""
    Alignak backend import

    This module contains utility tools to import Nagios-like flat files configuration into
    an Alignak REST backend.
"""
# Application version and manifest
VERSION = (1, 0, 'rc2')

__application__ = u"Alignak backend import"
__short_version__ = '.'.join((str(each) for each in VERSION[:2]))
__version__ = '.'.join((str(each) for each in VERSION[:4]))
__author__ = u"Frédéric Mohier"
__author_email__ = u"frederic.mohier@alignak.net"
__copyright__ = u"(c) 2015-2016, %s" % __author__
__license__ = u"GNU Affero General Public License, version 3"
__description__ = u"Alignak backend import tools"
__releasenotes__ = u"""Alignak Backend import tools"""
__git_url__ = "https://github.com/alignak-monitoring-contrib/alignak-backend-import"
__doc_url__ = "https://github.com/alignak-monitoring-contrib/alignak-backend-import"

__classifiers__ = [
    'Development Status :: 5 - Production/Stable',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'Intended Audience :: System Administrators',
    'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
    'Natural Language :: English',
    'Programming Language :: Python',
    'Topic :: System :: Monitoring',
    'Topic :: System :: Systems Administration'
]

