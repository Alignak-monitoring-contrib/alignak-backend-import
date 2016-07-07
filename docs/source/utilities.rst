.. _utilities:

Utilities
=========

Alignak backend importation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

 ``alignak_backend_import`` is an utility tool that can import a monitoring configuration stored in Nagios-like flat files and send this configuration to Alignak backend. It allows importing an existing configuration from Nagios or Shinken.


Usage
---------------------------
 The default behavior is to update an existing Alignak backend running on http://127.0.0.1:5000.
 This is why it does not delete the existing backend content.

 To start a new backend from scratch, please specify ``--delete``.


Command line interface
---------------------------
.. automodule:: alignak_backend_import.cfg_to_backend

