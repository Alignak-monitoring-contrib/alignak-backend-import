.. _install:

Installation
============

Install from Alignak repositories
---------------------------------

If you installed the Alignak backend from the Alignak Debian / RPM packages repositories, you can install with::

    # Debian
    apt install python-alignak-backend-import

    # RPM
    yum install python-alignak-backend-import

.. note:: for Python 3 version, replace ``python`` with ``python3`` in the packages name.

Install with pip
----------------

With pip
~~~~~~~~

You can install with pip::

    pip install alignak-backend-import


From source
~~~~~~~~~~~

You can install it from source::

    git clone https://github.com/Alignak-monitoring-contrib/alignak-backend-import
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

    git clone https://github.com/Alignak-monitoring-contrib/alignak-backend-import


Install python prerequisites::

    pip install -r alignak-backend-import/requirements.txt


And install::

    cd alignak-backend-import
    python setup.py install
