Alignak Backend import
======================

*Import flat files Nagios-like configuration into the Alignak backend*

.. image:: https://travis-ci.org/Alignak-monitoring-contrib/alignak-backend-import.svg?branch=develop
    :target: https://travis-ci.org/Alignak-monitoring-contrib/alignak-backend-import
    :alt: Develop branch build status

.. image:: https://readthedocs.org/projects/alignak-backend-import/badge/?version=latest
    :target: http://alignak-backend-import.readthedocs.org/en/latest/?badge=latest
    :alt: Latest documentation Status

.. image:: https://readthedocs.org/projects/alignak-backend-import/badge/?version=develop
    :target: http://alignak-backend-import.readthedocs.org/en/develop/?badge=develop
    :alt: Development documentation Status

.. image:: https://badge.fury.io/py/alignak-backend-import.svg
    :target: https://badge.fury.io/py/alignak-backend-import
    :alt: Last PyPi version

.. image:: https://img.shields.io/badge/License-AGPL%20v3-blue.svg
    :target: http://www.gnu.org/licenses/agpl-3.0
    :alt: License AGPL v3


Release strategy
----------------

Alignak backend and its *satellites* (backend client, and backend import tools) must all have the
same features level. As of it, take care to install the same minor version on your system to
ensure compatibility between all the packages. Use 0.4.x version of Backend import and Backend
client with a 0.4.x version of the Backend.


Short description
-----------------

This package contains an utility tool `alignak_backend_import` that allows to import a Nagios-like flat files monitoring configuration into an Alignak Backend.

Bugs, issues and contributing
-----------------------------

Please report any issue using the project `GitHub repository<https://github.com/Alignak-monitoring-contrib/alignak-backend-import/issues>`_.

