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

This package contains an utility tool `alignak_backend_import` that allows to import a Nagios-like flat files monitoring configuration into an Alignak Backend.

It also contains a backend client CLI that allows to make some simple operations with the backend.

Release strategy
----------------

Alignak backend and its *satellites* (backend client, and backend import tools) must all have the
same features level. As of it, take care to install the same minor version on your system to
ensure compatibility between all the packages. Use 0.4.x version of Backend import and Backend
client with a 0.4.x version of the Backend.


Backend client CLI
------------------

This simple script may be used to make simple operations with the Alignak backend:

- create a new element based (or not) on a template

- update a backend element

- delete an element

- get an element and dump its properties to the console or a file (in /tmp)

- get (and dump) a list of elements

A simple usage example for this script:
::

    # Assuming that you installed: alignak, alignak-backend and alignak-backend-import

    # From the root of this repository
    cd tests/cfg_passive_templates
    # Import the test configuration in the Alignak backend
    alignak-backend-import -d -m ./cfg_passive_templates.cfg
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

    # Get an host from the backend
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

    # Get the list of all hosts from the backend
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

    # Create an host into the backend
    backend_client -T windows-nsca-host -t host add myHost
    # The script inform on the console
        Created host 'myHost'

    # Create an host into the backend with extra data
    backend_client -T windows-nsca-host -t host --data='/tmp/create_data.json' add myHost
    # The script reads the JSON content of the file /tmp/create_data.json and tries to create
    # the host named myHost with the template and the read data

    # Update an host into the backend
    backend_client -t host --data='/tmp/update_data.json' update myHost
    # The script reads the JSON content of the file /tmp/update_data.json and tries to update
    # the host named myHost with the read data

    # Delete an host from the backend
    backend_client -T windows-nsca-host -t host delete myHost
    # The script inform on the console
        Deleted host 'myHost'


Bugs, issues and contributing
-----------------------------

Please report any issue using the project `issues page <https://github.com/Alignak-monitoring-contrib/alignak-backend-import/issues>`_.

