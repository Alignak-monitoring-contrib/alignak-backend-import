.. _utilities:

Utilities
=========

Alignak backend command line interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

 ``alignak_backend_cli`` is an utility tool that can make simple operations with the Alignak backend.
 It allows getting, updating, creating data from/into the backend.


Usage
-----
The ``alignak_backend_cli`` script receives some command line parameters to define its behavior:


Command line interface
----------------------
.. automodule:: alignak_backend_import.backend_client


Alignak backend importation
~~~~~~~~~~~~~~~~~~~~~~~~~~~

 ``alignak_backend_import`` is an utility tool that can import a monitoring configuration stored in Nagios-like flat files and send this configuration to Alignak backend.
 It allows importing an existing configuration from Nagios or Shinken.


Usage
-----
The ``alignak_backend_import`` script receives some command line parameters to define its behavior:

    - main configuration file
    - destination backend
    - backend elements types
    - ...

The default behavior is to update an existing Alignak backend running on http://127.0.0.1:5000.

The backend content is not deleted by default. This to avoid deleting data by error ;) Furthermore,
the results of a configuration update may be unpredictable and break the data integrity because no
global configuration check is done when data are imported.

**Note**: As of it, beware of configuration updates if you do not really know the previous backend data!

The most common usage is to delete all the backend content to import a brand new configuration. It is also the safest usage ...

To import a new backend from scratch, specify ``--delete`` (or `-d`) on the command line.
The ``alignak_backend_import`` script deletes all the existing data in the backend except for some
default and mandatory data (eg. default timeperiods, default groups, ...).

The configuration to be imported is specified with an entry point filename that must include all the
configuration elements: hosts, services, contacts, ... it is a common Alignak, Shinken or Nagios
main configuration file that includes directives like `cfg_dir`, `cfg_file`, ...


The ``alignak_backend_import`` script uses the Alignak configuration process to load the
configuration to be sure of the configuration validity ...
Then each object type is parsed, converted and imported in the Alignak backend. All the relations
existing between the objects are created in the backend.
As example, an host is linked to some timeperiods (eg. check period), commands (eg. check command),
... and those relations are created.

As an example of configuration importation::

    alignak_backend_import -d /etc/shinken/shinken.cfg

Some specific features:

    - define the default host GPS location (`--gps` or `-g`)
    - import the hosts, services templates (`--model` or `-m`)
    - allow duplicate objects (`--duplicate` or `-i`)
    - update existing objects (`--update` or `-e`)

The `--gps` option allows to define the default GPS coordinates to be used for hosts which
position is not yet defined in the configuration files.

The `--model` option imports all the hosts and services templates in the backend. The Alignak Web
UI uses the templates to ease the creation of new hosts and services.

The `--duplicate` option will try to find each imported object in the Alignak backend and will
not import the object if it still exists. Thus, this option is very heavy because the scripts
makes two request for each object ... but this option is very useful if you are wish to import
the configuration of multiple servers into the same backend.

The `--update` option will try to find each imported object in the Alignak backend and will
update the object if it still exists. This option is very interesting if you made small changes
or only some fine tuning in an imported configuration because it will avoid deleting all the
backend data; especially interesting to keep some checks results in the live state.

The `--check` option do not change anything in the Alignak backend. This option is very 
interesting if you simply want to check what will be done for an imported configuration.


Command line interface
----------------------
.. automodule:: alignak_backend_import.cfg_to_backend

