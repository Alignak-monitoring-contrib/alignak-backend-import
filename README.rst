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

.. image:: https://readthedocs.org/projects/alignak-backend/badge/?version=develop
    :target: http://alignak-backend.readthedocs.org/en/develop/?badge=develop
    :alt: Development documentation Status

.. image:: https://badge.fury.io/py/alignak_backend_import.svg
    :target: https://badge.fury.io/py/alignak_backend_import
    :alt: Most recent PyPi version

.. image:: https://img.shields.io/badge/IRC-%23alignak-1e72ff.svg?style=flat
    :target: http://webchat.freenode.net/?channels=%23alignak
    :alt: Join the chat #alignak on freenode.net

.. image:: https://img.shields.io/badge/License-AGPL%20v3-blue.svg
    :target: http://www.gnu.org/licenses/agpl-3.0
    :alt: License AGPL v3


Short description
-----------------

This package contains an utility tool `alignak_backend_import` that allows to import a Nagios-like flat files monitoring configuration into an Alignak Backend.


Installation
------------

From PyPI
~~~~~~~~~
To install the package from PyPI:
::

   sudo pip install alignak-backend-import


From source files
~~~~~~~~~~~~~~~~~
To install the package from the source files:
::

   git clone https://github.com/Alignak-monitoring-contrib/alignak-backend-import
   cd alignak-backend-import
   sudo pip install .


Release strategy
----------------

Alignak backend and its *satellites* (backend client, and backend import tools) must all have the
same features level. As of it, take care to install the same minor version on your system to
ensure compatibility between all the packages. Use 0.4.x version of Backend import and Backend
client with a 0.4.x version of the Backend.


Bugs, issues and contributing
-----------------------------

Contributions to this project are welcome and encouraged ... `issues in the project repository <https://github.com/alignak-monitoring-contrib/alignak-backend-import/issues>`_ are the common way to raise an information.
