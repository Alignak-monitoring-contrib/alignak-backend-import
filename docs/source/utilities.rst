.. _utilities:

Utilities
=========

Alignak backend importation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

 ``alignak_backend_import`` is an utility tool that can import a monitoring configuration stored in Nagios-like flat files and send this configuration to Alignak backend.
 It allows importing an existing configuration from Nagios or Shinken.


Usage
---------------------------
The ``alignak_backend_import`` script receives some command line parameters to define its behavior:

    - main configuration file
    - destination backend
    - backend elements types
    - ...

The default behavior is to update an existing Alignak backend running on http://127.0.0.1:5000.

The backend content is not deleted by default. This to avoid deleting data by error ;) Furthermore,
the results of a configuration update may be unpredictable and break the data integroty because no
global configuration check is done when data are imported.

**Note**: As of it, beware of configuration updates if you do not really know the previous backend data!

The most common usage is to delete all the backend content to import a brand new configuration. It is also the safest usage ...

To import a new backend from scratch, specify ``--delete`` (or `-d`) on the command line.
The ``alignak_backend_import`` script deletes all the existing data in the backend except for some default and mandatory data (eg. default timeperiods, default groups, ...).

The configuration to be imported is specified with an entry point filename that includes all the configuration elements: hosts, services, contacts, ...

The ``alignak_backend_import`` script uses the Alignak configuration process to load the configuration to be sure of the configuration validity ...
Then each object type is parsed, converted and imported in the Alignak backend. All the relations existing between the objects are created in the backend.
As example, an host is linked to some timeperiods (eg. check period), commands (eg. check command), ... and those relations are created.

As an example of configuration importation::

    alignak_backend_import -d /etc/shinken/shinken.cfg

Some specific features:

    - define the default host GPS location (`--gps`)
    - import the hosts, services templates (`--model`)
    - restrict to some elements (`--type`) **dangerous option!**


Command line interface
---------------------------
.. automodule:: alignak_backend_import.cfg_to_backend

