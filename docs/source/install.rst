.. _install:

Installation
============

Install with pip
----------------

With pip
~~~~~~~~

You can install with pip::

    pip install alignak_backend_import


From source
~~~~~~~~~~~

You can install it from source::

    git clone https://github.com/Alignak-monitoring/alignak-backend-import
    cd alignak-backend-import
    pip install .


For contributors
~~~~~~~~~~~~~~~~

If you want to hack into the codebase (e.g for future contribution), just install like this::

    pip install -e .


Install from source without pip
-------------------------------

If you are on Debian::

    apt-get -y install python python-dev python-pip git


Get the project sources::

    git clone https://github.com/Alignak-monitoring/alignak-backend-import


Install python prerequisites::

    pip install -r alignak-backend/requirements.txt


And install::

    cd alignak-backend
    python setup.py install