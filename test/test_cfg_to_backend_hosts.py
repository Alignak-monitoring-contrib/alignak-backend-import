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


class TestHosts(unittest2.TestCase):
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

    def test_hosts(self):

        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', '--quiet',
                              'alignak_cfg_files/hosts.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        self.assertEqual(exit_code, 0)

        result = self.backend.get('timeperiod')
        tps = result['_items']
        for tp in tps:
            print(tp['_id'], tp['name'])
            if tp['name'] == '24x7':
                tp_always = tp['_id']
            if tp['name'] == 'Never':
                tp_never = tp['_id']
            if tp['name'] == 'All time default 24x7':
                tp_default = tp['_id']
        self.assertEqual(len(tps), 2)

        result = self.backend.get('host', params={'where': json.dumps({'_is_template': False})})
        hosts = result['_items']
        # 3 newly created hosts
        self.assertEqual(len(hosts), 3)
        for host in hosts:
            if host['name'] == '_dummy':
                continue
            # Hosts specific fields
            if host['name'] == 'srv01':
                self.assertEqual(host['address'], '192.168.1.11')
            if host['name'] == 'srv02':
                self.assertEqual(host['address'], '192.168.1.12')
            if host['name'] == 'srv03':
                self.assertEqual(host['address'], '192.168.1.13')

            # Host template fields
            self.assertEqual(host['check_interval'], 4)
            self.assertEqual(host['max_check_attempts'], 6)

            # Host template fields - must have a valid check period
            self.assertIn('check_period', host)
            self.assertEqual(host['check_period'], tp_always)

            # Host template fields - must have a valid notification period
            self.assertIn('notification_period', host)
            self.assertEqual(host['notification_period'], tp_always)

            # Host template fields - must have a Never maintenance period
            self.assertIn('maintenance_period', host)
            self.assertEqual(host['maintenance_period'], tp_never)

            # Host template fields - must have a Never snapshot period
            self.assertIn('snapshot_period', host)
            self.assertEqual(host['snapshot_period'], tp_never)

    def test_hosts_template(self):
        """Tests hosts templates"""
        # Import and insert the templates into the backend (--model)
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', '--quiet',
                              'alignak_cfg_files/hosts_2_templates.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        self.assertEqual(exit_code, 0)

        result = self.backend.get_all('host', params={'where': json.dumps({'_is_template': True})})
        hosts = result['_items']
        self.assertEqual(len(hosts), 4)

        print("Found hosts templates: ")
        self.template1 = None
        self.template2 = None
        self.template3 = None
        for host in hosts:
            print("-", host['name'], host)
            # template01 only is a template
            if host['name'] == 'template01':
                self.assertEqual(host['_is_template'], True)
                self.template1 = host['_id']
            # template02 only is a template
            if host['name'] == 'template02':
                self.assertEqual(host['_is_template'], True)
                self.template2 = host['_id']
            # template03 only is a template
            if host['name'] == 'template03':
                self.assertEqual(host['_is_template'], True)
                self.template3 = host['_id']
        self.assertIsNotNone(self.template1)
        self.assertIsNotNone(self.template2)
        self.assertIsNotNone(self.template3)

        result = self.backend.get_all('host', params={'where': json.dumps({'_is_template': False})})
        hosts = result['_items']
        self.assertEqual(len(hosts), 1)

        print("Found hosts: ")
        for host in hosts:
            print("-", host['name'], host)
            if host['name'] in ['template01', 'template02', '_dummy']:
                self.assertEqual(host['_is_template'], True)
                continue

            if host['name'] in ['template03']:
                self.assertEqual(host['_is_template'], True)
                self.assertEqual(host['_templates'], [self.template2])
                # Tags remain empty
                self.assertEqual(host['tags'], [])
                continue

            self.assertEqual(host['_is_template'], False)
            if host['name'] == 'srv01':
                self.assertEqual(host['_templates'], [self.template1, self.template3])
                # Tags remain empty
                self.assertEqual(host['tags'], [])

    def test_host_with_double_template(self):

        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', '--quiet',
                              'alignak_cfg_files/hosts_2_templates.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        self.assertEqual(exit_code, 0)

        result = self.backend.get('host', params={'where': json.dumps({'_is_template': False})})
        # 1 newly created host
        self.assertEqual(len(result['_items']), 1)
        for comm in result['_items']:
            reg_comm = comm.copy()

        self.assertEqual(reg_comm['name'], 'srv01')
        self.assertEqual(reg_comm['max_check_attempts'], 6)
        self.assertEqual(reg_comm['check_interval'], 2)

    def test_hosts_dependency(self):

        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', '--quiet',
                              'alignak_cfg_files/hosts_links_parent.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        self.assertEqual(exit_code, 0)

        result = self.backend.get('hostdependency')
        hds = result['_items']
        for hd in hds:
            print(hd)
        self.assertEqual(len(hds), 2)
