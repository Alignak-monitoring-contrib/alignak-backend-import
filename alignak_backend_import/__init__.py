#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""
    Alignak backend import

    This module contains utility tools to import Nagios-like flat files configuration into
    an Alignak REST backend.
"""
# Application version and manifest
VERSION = (0, 6, 7)

__application__ = u"Alignak backend import"
__short_version__ = '.'.join((str(each) for each in VERSION[:2]))
__version__ = '.'.join((str(each) for each in VERSION[:4]))
__author__ = u"Frédéric Mohier"
__author_email__ = u"frederic.mohier@gmail.com"
__copyright__ = u"(c) 2015-2016, %s" % __author__
__license__ = u"GNU Affero General Public License, version 3"
__description__ = u"Alignak backend import tools"
__releasenotes__ = u"""Alignak Backend import tools"""
__doc_url__ = "https://github.com/Alignak-monitoring-contrib/alignak-backend-import"
