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


Short description
-----------------

This package contains an utility tool `alignak-backend-import` that allows to import a Nagios-like flat files monitoring configuration into an Alignak Backend.

Release strategy
----------------

Alignak backend and its *satellites* (backend client, and backend import tools) must all have the
same features level. As of it, take care to install the same minor version on your system to
ensure compatibility between all the packages. Use 0.4.x version of Backend import and Backend
client with a 0.4.x version of the Backend.


Alignak backend import
----------------------

The `alignak-backend-import` script may be used to import a Nagios like flat-files configuration into the Alignak backend.

The online `documentation<http://alignak-backend-import.readthedocs.io/en/latest/utilities.html#alignak-backend-importation>`_ exaplins all the command line parameters that may be used.

A simple usage example for this script:
::

    # Assuming that you installed: alignak, alignak-backend and alignak-backend-import

    # From the root of this repository
    cd tests/alignak_cfg_files
    # Import the test configuration in the Alignak backend
    alignak-backend-import -d -m ./alignak-demo/alignak-backend-import.cfg

    # The script imports the configuration and makes some console logs:
        alignak_backend_import, inserted elements:
        - 6 command(s)
        - 3 host(s)
        - 3 host_template(s)
        - no hostdependency(s)
        - no hostescalation(s)
        - 12 hostgroup(s)
        - 1 realm(s)
        - 1 service(s)
        - 14 service_template(s)
        - no servicedependency(s)
        - no serviceescalation(s)
        - 12 servicegroup(s)
        - 2 timeperiod(s)
        - 2 user(s)
        - 3 usergroup(s)

    # To confirm, you easily can get an host from the backend
    backend_client -t host get test_host_0

    # The script dumps the json host on the console and creates a file: */tmp/alignak-object-dump-host-test_host_0.json*
    {
        ...
        "active_checks_enabled": true,
        "address": "127.0.0.1",
        "address6": "",
        "alias": "test_host_0",
        ...
        "customs": {
            "_OSLICENSE": "gpl",
            "_OSTYPE": "gnulinux"
        },
        ...
    }

    # Get the list of all imported hosts from the backend
    backend_client --list -t host get

    # The script dumps the json list of hosts on the console and creates a file: */tmp/alignak-object-list-hosts.json*
    {
        ...
        "active_checks_enabled": true,
        "address": "127.0.0.1",
        "address6": "",
        "alias": "test_host_0",
        ...
        "customs": {
            "_OSLICENSE": "gpl",
            "_OSTYPE": "gnulinux"
        },
        ...
    }

Bugs, issues and contributing
-----------------------------

Please report any issue using the project `issues page <https://github.com/Alignak-monitoring-contrib/alignak-backend-import/issues>`_.

