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


class TestServices(unittest2.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set test mode for applications backend
        os.environ['TEST_ALIGNAK_BACKEND'] = '1'
        os.environ['ALIGNAK_BACKEND_MONGO_DBNAME'] = 'alignak-backend-import-test'

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

    def test_services_template(self):
        """Tests hosts templates"""
        # Import and insert the templates into the backend (--model)
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete',
                              'alignak_cfg_files/hosts_services_templates.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        self.assertEqual(exit_code, 0)

        result = self.backend.get_all('host',
                                      params={'where': json.dumps({'_is_template': True})})
        hosts = result['_items']
        self.assertEqual(len(hosts), 4)

        print("Found host templates: ")
        host_template = None
        for host in hosts:
            print("-", host['name'])
            self.assertIn(host['name'], ['_dummy', 'generic-host',
                                         'generic-passive-host', 'windows-passive-host'])
            if host['name'] == 'windows-passive-host':
                host_template = host
        self.assertEqual(len(hosts), 4)
        self.assertIsNotNone(host_template)

        result = self.backend.get_all('service',
                                      params={'where': json.dumps({'_is_template': True})})
        services = result['_items']
        self.assertEqual(len(services), 6)

        print("Found service templates: ")
        for service in services:
            print("-", service['name'])
            self.assertIn(service['name'], ['windows-passive-service',
                                            'nsca_uptime',
                                            'nsca_memory',
                                            'nsca_cpu',
                                            'nsca_disk',
                                            'nsca_services'])

        result = self.backend.get_all('host',
                                      params={'where': json.dumps({'_is_template': False})})
        hosts = result['_items']
        self.assertEqual(len(hosts), 1)

        # Only one host using the template windows-passive-host...
        print("Found hosts: ")
        for host in hosts:
            print("-", host['name'])
            self.assertEqual(host['_templates'], [host_template['_id']])

        result = self.backend.get_all('service',
                                      params={'where': json.dumps({'_is_template': False})})
        services = result['_items']
        self.assertEqual(len(services), 5)

        # will inherit from 5 services
        print("Found services: ")
        for service in services:
            print("-", service['name'])

    def test_services_hostgroup(self):
        """Tests services / hostgroups (issue #65)"""
        # Import and insert the templates into the backend (--model)
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete',
                              'alignak_cfg_files/issue65.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        self.assertEqual(exit_code, 0)

        # Get all hostgroups
        result = self.backend.get_all('hostgroup')
        hostgroups = result['_items']
        self.assertEqual(len(hostgroups), 2)
        print("Found hostgroups: ")
        for hostgroup in hostgroups:
            print("-", hostgroup['name'])

        # Get all hosts
        result = self.backend.get_all('host', params={'where': json.dumps({'_is_template': False})})
        hosts = result['_items']
        self.assertEqual(len(hosts), 3)
        print("Found hosts: ")
        for host in hosts:
            print("-", host['name'])

        # Get all services
        result = self.backend.get_all('service',
                                      params={'where': json.dumps({'_is_template': False})})
        services = result['_items']
        self.assertEqual(len(services), 3)
        print("Found services: ")
        for service in services:
            print("-", service['name'])
