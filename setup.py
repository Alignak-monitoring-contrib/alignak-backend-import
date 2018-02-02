#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2015-2018:
#   Frederic Mohier, frederic.mohier@gmail.com
#
# This file is part of (alignak_backend_import).
#
# (alignak_backend_import) is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# (alignak_backend_import) is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with (alignak_backend_import).  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import re
del os.link
from importlib import import_module

try:
    from setuptools import setup, find_packages
except:
    sys.exit("Error: missing python-setuptools library")

long_description = "Python Alignak backend importation tool"
try:
    with open('README.rst') as f:
        long_description = f.read()
except IOError:
    pass

try:
    python_version = sys.version_info
except:
    python_version = (1, 5)
if python_version < (2, 7):
    sys.exit("This application requires a minimum Python 2.7.x, sorry!")

from alignak_backend_import import __version__, __author__, __author_email__, __doc_url__
from alignak_backend_import import  __copyright__, __classifiers__, __license__, __git_url__
from alignak_backend_import import __name__ as __pkg_name__

package = import_module('alignak_backend_import')

setup(
    name=__pkg_name__,
    version=__version__,

    license=__license__,

    # metadata for upload to PyPI
    author=__author__,
    author_email=__author_email__,
    url=__doc_url__,
    download_url=__git_url__,
    keywords="alignak monitoring backend import tool",
    description=package.__doc__.strip(),
    long_description=long_description,
    long_description_content_type='text/x-rst',

    project_urls={
        'Presentation': 'http://alignak.net',
        'Documentation': 'http://docs.alignak.net/en/latest/',
        'Source': 'https://github.com/alignak-monitoring-contrib/alignak-backed/',
        'Tracker': 'https://github.com/alignak-monitoring-contrib/alignak-backend/issues',
        'Contributions': 'https://github.com/alignak-monitoring-contrib/'
    },

    # Package data
    packages=find_packages(exclude=['docs', 'test']),
    include_package_data=True,

    # Unzip Egg
    zip_safe=False,
    platforms='any',

    # Dependencies...
    install_requires=['future', 'requests', 'alignak-backend-client'],
    dependency_links=[
        # Use the standard PyPi repository
        "https://pypi.python.org/simple/",
    ],

    entry_points={
        'console_scripts': [
            'alignak-backend-import = alignak_backend_import.cfg_to_backend:main'
        ],
    },

    classifiers = __classifiers__
)
