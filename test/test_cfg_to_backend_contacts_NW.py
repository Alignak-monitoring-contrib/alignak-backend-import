#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import unittest2
import os
import time
import shlex
import json
import subprocess
from alignak_backend_client.client import Backend


class TestContactsNW(unittest2.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set test mode for applications backend
        os.environ['TEST_ALIGNAK_BACKEND'] = '1'
        os.environ['ALIGNAK_BACKEND_MONGO_DBNAME'] = 'alignak-backend-import-test'
        os.environ['ALIGNAK_BACKEND_CONFIGURATION_FILE'] = './cfg/settings/settings.json'

        cls.maxDiff = None

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
        cls.p = subprocess.Popen(['uwsgi', '--plugin', 'python', '-w', 'alignak_backend.app:app',
                                  '--socket', '0.0.0.0:5000',
                                  '--protocol=http', '--enable-threads', '--pidfile',
                                  '/tmp/uwsgi.pid'])
        time.sleep(1)
        print("Started as %s" % cls.p.pid)

        cls.backend = Backend('http://127.0.0.1:5000')
        cls.backend.login("admin", "admin", "force")

        cls.backend.delete("host", {})
        cls.backend.delete("service", {})
        cls.backend.delete("command", {})
        cls.backend.delete("livesynthesis", {})

    @classmethod
    def tearDownClass(cls):
        """
        Stop alignak backend

        :return: None
        """
        print("Stopping Alignak backend...")
        subprocess.call(['uwsgi', '--stop', '/tmp/uwsgi.pid'])
        print("Stopped")

    def test_user_notification_ways(self):
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', '--quiet',
                              'alignak_cfg_files/users.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        self.assertEqual(exit_code, 0)

        result = self.backend.get('command')
        cmds = result['_items']
        for cmd in cmds:
            print(cmd['_id'], cmd['name'])
            if cmd['name'] == 'notify-host-by-email':
                cmd_nh1 = cmd['_id']
            if cmd['name'] == 'notify-host-by-email-2':
                cmd_nh2 = cmd['_id']
            if cmd['name'] == 'notify-service-by-email':
                cmd_ns = cmd['_id']
        self.assertGreaterEqual(len(cmds), 3)
        self.assertIsNotNone(cmd_nh1)
        self.assertIsNotNone(cmd_nh2)
        self.assertIsNotNone(cmd_ns)

        result = self.backend.get_all('user', params={'where': json.dumps({'_is_template': False})})
        users = result['_items']
        self.assertEqual(len(users), 5)

        print("Found users: ")
        for user in users:
            print("-", user['name'])
            if user['name'] == 'admin':
                self.assertEqual(user['is_admin'], True)
                self.assertEqual(user['back_role_super_admin'], True)
            else:
                self.assertEqual(user['back_role_super_admin'], False)
                self.assertTrue(user['host_notifications_enabled'])
                self.assertTrue(user['service_notifications_enabled'])
                # Note that commands are duplicated because they are defined in the user template
                # AND inherited from the notification ways!
                self.assertEqual(sorted(user['host_notification_commands']),
                                 sorted([cmd_nh1, cmd_nh2, cmd_nh1, cmd_nh2]))
                self.assertEqual(user['service_notification_commands'],
                                 [cmd_ns, cmd_ns])
