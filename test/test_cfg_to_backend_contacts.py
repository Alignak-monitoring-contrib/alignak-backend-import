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


class TestContacts(unittest2.TestCase):
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

    def test_user_template(self):
        """Tests users templates"""
        # Import and insert the templates into the backend (--model)
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', '--quiet',
                              'alignak_cfg_files/users.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        self.assertEqual(exit_code, 0)

        result = self.backend.get_all('user')
        users = result['_items']
        self.assertEqual(len(users), 6)

        print("Found users: ")
        self.generic_contact = None
        for user in users:
            print("-", user['name'], user)
            # generic-contact only is a template
            if user['name'] == 'generic-contact':
                self.assertEqual(user['_is_template'], True)
                self.generic_contact = user['_id']
        self.assertIsNotNone(self.generic_contact)

        print("Found users: ")
        for user in users:
            # Except the admin and generic-contact users, all are templated with the generic-contact
            if user['name'] in ['generic-contact', 'admin']:
                continue

            print("-", user['name'], user)
            self.assertEqual(user['_is_template'], False)
            self.assertEqual(user['_templates'], [self.generic_contact])
            # Tags remain empty
            self.assertEqual(user['tags'], [])

    def test_user_direct_notification(self):
        """Test user direct notifications"""
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', '--quiet',
                              'alignak_cfg_files/user_admin.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        self.assertEqual(exit_code, 0)

        result = self.backend.get('command')
        cmds = result['_items']
        for cmd in cmds:
            print("Command: %s" % cmd)
            if cmd['name'] == 'notify-host-by-email':
                cmd_nh1 = cmd['_id']
            if cmd['name'] == 'notify-service-by-email':
                cmd_ns = cmd['_id']
        self.assertGreaterEqual(len(cmds), 2)
        self.assertIsNotNone(cmd_nh1)
        self.assertIsNotNone(cmd_ns)

        result = self.backend.get_all('user')
        users = result['_items']
        self.assertEqual(len(users), 2)

        print("Found users: ")
        for user in users:
            print("-", user['name'], user)
            if user['name'] == 'admin':
                self.assertEqual(user['is_admin'], True)
                self.assertEqual(user['back_role_super_admin'], True)
                self.assertEqual(user['can_update_livestate'], True)
            else:
                self.assertEqual(user['is_admin'], True)
                self.assertEqual(user['back_role_super_admin'], False)
                self.assertEqual(user['can_update_livestate'], False)
                self.assertEqual(user['host_notification_commands'], [cmd_nh1])
                self.assertEqual(user['service_notification_commands'], [cmd_ns])
