#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest2
import os
import time
import shlex
import subprocess


class TestCfgToBackend(unittest2.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        This method:
          * delete mongodb database
          * start the backend with uwsgi

        :return: None
        """
        # Set test mode for Alignak backend
        os.environ['TEST_ALIGNAK_BACKEND'] = '1'
        os.environ['ALIGNAK_BACKEND_MONGO_DBNAME'] = 'alignak-backend-import-test'

        # Delete used mongo DBs
        exit_code = subprocess.call(
            shlex.split(
                'mongo %s --eval "db.dropDatabase()"' % os.environ['ALIGNAK_BACKEND_MONGO_DBNAME'])
        )
        assert exit_code == 0

        cls.p = subprocess.Popen(['uwsgi', '--plugin', 'python', '-w', 'alignakbackend:app',
                                  '--socket', '0.0.0.0:5000',
                                  '--protocol=http', '--enable-threads', '--pidfile',
                                  '/tmp/uwsgi.pid'])
        time.sleep(3)
        cls.endpoint = 'http://127.0.0.1:5000'

    @classmethod
    def tearDownClass(cls):
        """
        Stop alignak backend

        :return: None
        """
        subprocess.call(['uwsgi', '--stop', '/tmp/uwsgi.pid'])
        time.sleep(2)

    def testImportShinken1(self):
        """
        Import a complete shinken configuration
        :return:
        """
        print ("Feeding backend...")
        exit_code = subprocess.call(
            shlex.split('alignak-backend-import '
                        '--delete shinken_cfg_files/default/_main.cfg')
        )
        assert exit_code == 0

    def testImportAlignak1(self):
        """
        Import the alignak demo server configuration (updated after log + arbiter interface
        modification)

        :return:
        """
        print ("Feeding backend...")
        exit_code = subprocess.call(
            shlex.split('alignak-backend-import '
                        '--delete alignak_cfg_files/alignak_most_recent/alignak.backend-import.cfg')
        )
        assert exit_code == 0
