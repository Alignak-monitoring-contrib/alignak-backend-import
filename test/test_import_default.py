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
        print ("Starting Alignak backend...")
        # Set test mode for alignak backend
        os.environ['TEST_ALIGNAK_BACKEND'] = '1'
        os.environ['ALIGNAK_BACKEND_MONGO_DBNAME'] = 'alignak-backend-import-test'

        cls.p = subprocess.Popen(['alignak_backend'])
        print ("Backend PID: %s" % cls.p)
        time.sleep(3)

    def test_import(self):

        print ("Feeding backend...")
        exit_code = subprocess.call(
            shlex.split('alignak_backend_import --delete shinken_cfg_files/default/_main.cfg')
        )
        assert exit_code == 0
