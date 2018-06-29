#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest2
import os
import time
import shlex
import subprocess


def setup_module(module):
    # Set test mode for applications backend
    os.environ['TEST_ALIGNAK_BACKEND'] = '1'
    os.environ['ALIGNAK_BACKEND_MONGO_DBNAME'] = 'alignak-backend-import-test'
    os.environ['ALIGNAK_BACKEND_CONFIGURATION_FILE'] = './cfg/settings/settings.json'

    # Delete used mongo DBs
    exit_code = subprocess.call(
        shlex.split('mongo %s --eval "db.dropDatabase()"'
                    % os.environ['ALIGNAK_BACKEND_MONGO_DBNAME'])
    )
    assert exit_code == 0
    time.sleep(1)

    test_dir = os.path.dirname(os.path.realpath(__file__))
    print("Current test directory: %s" % test_dir)

    print("Starting Alignak backend...")
    subprocess.Popen(['uwsgi', '--plugin', 'python', '-w', 'alignak_backend.app:app',
                      '--socket', '0.0.0.0:5000',
                      '--protocol=http', '--enable-threads', '--pidfile',
                      '/tmp/uwsgi.pid'])
    time.sleep(1)


def teardown_module(module):
    print("Stopping Alignak backend...")
    subprocess.call(['uwsgi', '--stop', '/tmp/uwsgi.pid'])
    print("Stopped")


class TestCfgToBackend(unittest2.TestCase):

    def testImportShinken1(self):
        """Import a complete shinken configuration
        :return:
        """
        print ("Feeding backend...")
        fnull = open(os.devnull, 'w')
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py',
                              '--delete',
                              # '--quiet',
                              'shinken_cfg_files/default/_main.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        print("Exited with: %d" % exit_code)
        assert exit_code == 0

    def testImportAlignakDemo(self):
        """Import the alignak demo server configuration

        :return:
        """
        print ("Feeding backend...")
        fnull = open(os.devnull, 'w')
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py',
                              '--delete',
                              # '--quiet',
                              'alignak_cfg_files/alignak-demo/alignak-backend-import.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        print("Exited with: %d" % exit_code)
        assert exit_code == 0

    def testImportAlignak1(self):
        """Import the alignak default configuration (updated after log + arbiter interface
        modification)

        :return:
        """
        print ("Feeding backend...")
        fnull = open(os.devnull, 'w')
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py',
                              '--delete',
                              # '--quiet',
                              'alignak_cfg_files/alignak_most_recent/alignak-backend-import.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        print("Exited with: %d" % exit_code)
        assert exit_code == 0

    def testImportIssue83(self):
        """Import the alignak configuration that raised #83

        :return:
        """
        print ("Feeding backend...")
        fnull = open(os.devnull, 'w')
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py',
                              '--delete',
                              # '--quiet',
                              'alignak_cfg_files/issue_83/imported.cfg'],
                             stdout=fnull)
        (_, _) = q.communicate()
        exit_code = q.wait()
        print("Exited with: %d" % exit_code)
        assert exit_code == 0
