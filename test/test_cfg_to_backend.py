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


class TestCfgToBackend(unittest2.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set test mode for applications backend
        os.environ['TEST_ALIGNAK_BACKEND'] = '1'
        os.environ['ALIGNAK_BACKEND_MONGO_DBNAME'] = 'alignak-backend-import-test'

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
        fnull = open(os.devnull, 'w')
        cls.backend_process = subprocess.Popen(shlex.split('alignak-backend'))
        print("Started as %s" % cls.backend_process.pid)

        time.sleep(3)

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
        cls.backend_process.kill()
        print("Stopped")

    @classmethod
    def tearDown(cls):
        cls.backend.delete("host", {})
        cls.backend.delete("service", {})
        cls.backend.delete("command", {})
        cls.backend.delete("livesynthesis", {})

    def test_timeperiod(self):
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', '--quiet',
                              'alignak_cfg_files/timeperiods.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        self.assertEqual(exit_code, 0)

        result = self.backend.get('timeperiod')
        tps = result['_items']
        self.assertEqual(len(tps), 1+2)   # Imported TP + 2 default backend created TPs
        found = False
        for comm in tps:
            if comm['name'] != 'workhours':
                continue

            found = True
            ref = {u"name": u"workhours",
                   u"definition_order": 100,
                   u"notes": u"",
                   u'_sub_realm': True,
                   u"alias": u"Normal Work Hours",
                   u"dateranges": [{u'monday': u'09:00-17:00'}, {u'tuesday': u'09:00-17:00'},
                                   {u'friday': u'09:00-12:00,14:00-16:00'},
                                   {u'wednesday': u'09:00-17:00'},
                                   {u'thursday': u'09:00-17:00'}],
                   u"exclude": [], u"is_active": False, u"imported_from": u"alignak-backend-import"
                   }
            del comm['_links']
            del comm['_id']
            del comm['_etag']
            del comm['_created']
            del comm['_updated']
            del comm['_realm']
            self.assertEqual(comm, ref)
        self.assertTrue(found)

    def test_timeperiod_duplicates(self):
        # Do not allow duplicates ...
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', '--quiet',
                              'alignak_cfg_files/timeperiods_duplicate.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        # Importation is ok because Alignak filters the duplicated timeperiods
        self.assertEqual(exit_code, 0)

        # Allow duplicates ... and do not delete the backend data
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py',
                               '--duplicate', 'alignak_cfg_files/timeperiods.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        self.assertEqual(exit_code, 0)

        # The second defined TP is the one that got imported on first importation
        # The last importation did not imported the only defined TP
        result = self.backend.get('timeperiod')
        tps = result['_items']
        self.assertEqual(len(tps), 1+2)   # Imported TP + 2 default backend created TPs
        found = False
        for comm in tps:
            if comm['name'] != 'workhours':
                continue

            found = True
            ref = {u"name": u"workhours",
                   u"definition_order": 100,
                   u"notes": u"",
                   u'_sub_realm': True,
                   u"alias": u"Normal Work Hours",
                   u"dateranges": [{u'monday': u'09:00-18:00'}, {u'tuesday': u'09:00-18:00'},
                                   {u'friday': u'09:00-12:00,14:00-16:00'},
                                   {u'wednesday': u'09:00-18:00'},
                                   {u'thursday': u'09:00-18:00'}],
                   u"exclude": [], u"is_active": False, u"imported_from": u"alignak-backend-import"
                   }
            del comm['_links']
            del comm['_id']
            del comm['_etag']
            del comm['_created']
            del comm['_updated']
            del comm['_realm']
            self.assertEqual(comm, ref)
        self.assertTrue(found)

    def test_timeperiod_update(self):
        # Delete the backend content and import a TP
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', '--quiet',
                              'alignak_cfg_files/timeperiods_duplicate.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        # Importation is ok because Alignak filters the duplicated timeperiods
        self.assertEqual(exit_code, 0)

        # The second defined TP (09:00-18:00) is the one that got imported on first importation
        result = self.backend.get('timeperiod')
        tps = result['_items']
        self.assertEqual(len(tps), 1+2)   # Imported TP + 2 default backend created TPs
        found = False
        for comm in tps:
            if comm['name'] != 'workhours':
                continue

            found = True
            ref = {u"name": u"workhours",
                   u"definition_order": 100,
                   u"notes": u"",
                   u'_sub_realm': True,
                   u"alias": u"Normal Work Hours",
                   u"dateranges": [{u'monday': u'09:00-18:00'}, {u'tuesday': u'09:00-18:00'},
                                   {u'friday': u'09:00-12:00,14:00-16:00'},
                                   {u'wednesday': u'09:00-18:00'},
                                   {u'thursday': u'09:00-18:00'}],
                   u"exclude": [], u"is_active": False, u"imported_from": u"alignak-backend-import"
                   }
            del comm['_links']
            del comm['_id']
            del comm['_etag']
            del comm['_created']
            del comm['_updated']
            del comm['_realm']
            self.assertEqual(comm, ref)
        self.assertTrue(found)

        # Update an existing element
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py',
                              '--update', 'alignak_cfg_files/timeperiods.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        self.assertEqual(exit_code, 0)

        # The former existing TP (09:00-18:00) has been updated (09:00-17:00)
        result = self.backend.get('timeperiod')
        tps = result['_items']
        self.assertEqual(len(tps), 1 + 2)  # Imported TP + 2 default backend created TPs
        found = False
        for comm in tps:
            if comm['name'] != 'workhours':
                continue

            found = True
            ref = {u"name": u"workhours",
                   u"definition_order": 100,
                   u"notes": u"",
                   u'_sub_realm': True,
                   u"alias": u"Normal Work Hours",
                   u"dateranges": [{u'monday': u'09:00-17:00'}, {u'tuesday': u'09:00-17:00'},
                                   {u'friday': u'09:00-12:00,14:00-16:00'},
                                   {u'wednesday': u'09:00-17:00'},
                                   {u'thursday': u'09:00-17:00'}],
                   u"exclude": [], u"is_active": False, u"imported_from": u"alignak-backend-import"
                   }
            del comm['_links']
            del comm['_id']
            del comm['_etag']
            del comm['_created']
            del comm['_updated']
            del comm['_realm']
            self.assertEqual(comm, ref)
        self.assertTrue(found)

    def test_timeperiod_complex(self):
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', '--quiet',
                              'alignak_cfg_files/timeperiods_complex.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        self.assertEqual(exit_code, 0)

        r = self.backend.get_all('timeperiod')
        r = r['_items']
        self.assertEqual(len(r), 2+2)  # Imported TP + 2 default backend created TPs

        ref = {u"name": u"workhours",
               u"definition_order": 100,
               u"alias": u"Normal Work Hours",
               u"notes": u"",
               u'_sub_realm': True,
               u"dateranges": [{u'monday': u'09:00-17:00'}, {u'tuesday': u'09:00-17:00'},
                               {u'friday': u'09:00-12:00,14:00-16:00'},
                               {u'wednesday': u'09:00-17:00'},
                               {u'thursday': u'09:00-17:00'}],
               u"exclude": [u'us-holidays'], u"is_active": False,
               u"imported_from": u"alignak-backend-import"}
        comm = r[2]
        del comm['_links']
        del comm['_id']
        del comm['_etag']
        del comm['_created']
        del comm['_updated']
        del comm['_realm']
        self.assertItemsEqual(comm, ref)

        ref = {u"name": u"us-holidays",
               u"definition_order": 100,
               u"alias": u"U.S. Holidays",
               u"notes": u"",
               u'_sub_realm': True,
               u"dateranges": [{u'thursday -1 november': u'00:00-00:00'},
                               {u'monday 1 september': u'00:00-00:00'},
                               {u'january 1': u'00:00-00:00'},
                               {u'december 25': u'00:00-00:00'}, {u'july 4': u'00:00-00:00'}],
               u"exclude": [], u"is_active": False,
               u"imported_from": u"alignak-backend-import"}
        comm = r[3]
        del comm['_links']
        del comm['_id']
        del comm['_etag']
        del comm['_created']
        del comm['_updated']
        del comm['_realm']
        self.assertItemsEqual(comm, ref)

    def test_host_multiple_link_now(self):
        """
        The host will be added in host_group endpoint

        :return: None
        """
        # host.hostgroups
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', '--quiet',
                              'alignak_cfg_files/hosts_links_hostgroup.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        self.assertEqual(exit_code, 0)

        result = self.backend.get('host', params={'where': json.dumps({'_is_template': False})})
        hosts = result['_items']
        self.assertEqual(len(hosts), 1)
        for host in hosts:
            # host_id = hosts[0]['_id']
            print("Host:", host)

        result = self.backend.get('hostgroup')
        hostgroups = result['_items']
        self.assertEqual(len(hostgroups), 3)
        for hostgroup in hostgroups:
            print("Hostgroup:", hostgroup)
            print("Hostgroup groups:", hostgroup['hostgroups'])
            # self.assertEqual(hostgroup['hosts'], [hosts[0]['_id']])

    def test_host_multiple_link_later(self):
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', '--quiet',
                              'alignak_cfg_files/hosts_links_parent.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        self.assertEqual(exit_code, 0)

        result = self.backend.get('host', params={'where': json.dumps({'_is_template': False})})
        hosts = result['_items']
        self.assertEqual(len(hosts), 3)
        for host in hosts:
            print("Host:", host['name'])
            if host['name'] == 'webui':
                webui = host.copy()
            if host['name'] == 'backend':
                backend = host.copy()
            if host['name'] == 'mongo':
                mongo = host.copy()

        print(backend['parents'])
        self.assertEqual(backend['parents'], [])
        print(mongo['parents'])
        self.assertEqual(mongo['parents'], [backend['_id']])
        print(webui['parents'])
        self.assertEqual(webui['parents'], [backend['_id'], mongo['_id']])

    def test_hostgroups_links(self):
        """
        """
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', '--quiet',
                              'alignak_cfg_files/hostgroups_links_hostgroup.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        self.assertEqual(exit_code, 0)

        result = self.backend.get('host', params={'where': json.dumps({'_is_template': False})})
        hosts = result['_items']
        self.assertEqual(len(hosts), 1)
        host_id = hosts[0]['_id']

        result = self.backend.get('hostgroup')
        hostgroups = result['_items']
        self.assertEqual(len(hostgroups), 3)
        for hostgroup in hostgroups:
            print("Hostgroup:", hostgroup)
            print("Hostgroup groups members:", hostgroup['hostgroups'])
            print("Hostgroup members:", hostgroup['hosts'])

            # Test hostgroups relations with hostgroups
            if hostgroup['name'] == 'freebsd':
                self.assertEqual(len(hostgroup['hostgroups']), 1)
            if hostgroup['name'] == 'alignak':
                self.assertEqual(len(hostgroup['hostgroups']), 0)

            # Test hostgroups relations with hosts
            # Host webui is member of the 2 groups
            if hostgroup['name'] == 'freebsd':
                self.assertEqual(len(hostgroup['hosts']), 1)
                self.assertEqual(hostgroup['hosts'][0], host_id)
            if hostgroup['name'] == 'alignak':
                self.assertEqual(len(hostgroup['hosts']), 1)
                self.assertEqual(hostgroup['hosts'][0], host_id)

    def test_servicegroups_links(self):
        """
        """
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', '--quiet',
                              'alignak_cfg_files/services_link_servicegroups.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        self.assertEqual(exit_code, 0)

        result = self.backend.get('host', params={'where': json.dumps({'_is_template': False})})
        hosts = result['_items']
        self.assertEqual(len(hosts), 1)
        host_id = hosts[0]['_id']

        result = self.backend.get('service', params={'where': json.dumps({'_is_template': False})})
        services = result['_items']
        self.assertEqual(len(services), 2)
        service_id = services[0]['_id']

        result = self.backend.get('servicegroup')
        servicegroups = result['_items']
        self.assertEqual(len(servicegroups), 3)
        for servicegroup in servicegroups:
            print("servicegroup:", servicegroup)
            print("servicegroup groups members:", servicegroup['servicegroups'])
            print("servicegroup members:", servicegroup['services'])

            # Test servicegroups relations with servicegroups
            if servicegroup['name'] == 'web':
                self.assertEqual(len(servicegroup['servicegroups']), 1)
            if servicegroup['name'] == 'web_child':
                self.assertEqual(len(servicegroup['servicegroups']), 0)

            # Test servicegroups relations with services
            # service webui is member of the 2 groups
            if servicegroup['name'] == 'web':
                self.assertEqual(len(servicegroup['services']), 2)
            if servicegroup['name'] == 'web_child':
                self.assertEqual(len(servicegroup['services']), 1)

    def test_usergroups_links(self):
        """
        """
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', '--quiet',
                              'alignak_cfg_files/users_link_usergroups.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        self.assertEqual(exit_code, 0)

        result = self.backend.get('user', params={'where': json.dumps({'_is_template': False})})
        users = result['_items']
        self.assertEqual(len(users), 5)
        user_id = users[0]['_id']

        result = self.backend.get('usergroup')
        usergroups = result['_items']
        self.assertEqual(len(usergroups), 4)
        for usergroup in usergroups:
            print("usergroup:", usergroup)
            print("usergroup groups members:", usergroup['usergroups'])
            print("usergroup members:", usergroup['users'])

            # Test usergroups relations with usergroups
            if usergroup['name'] == 'admins':
                self.assertEqual(len(usergroup['usergroups']), 0)
            if usergroup['name'] == 'users':
                self.assertEqual(len(usergroup['usergroups']), 0)
            if usergroup['name'] == 'power_users':
                self.assertEqual(len(usergroup['usergroups']), 1)

            # Test usergroups relations with users
            # user webui is member of the 2 groups
            if usergroup['name'] == 'admins':
                self.assertEqual(len(usergroup['users']), 1)
            if usergroup['name'] == 'users':
                self.assertEqual(len(usergroup['users']), 3)
            if usergroup['name'] == 'power_users':
                self.assertEqual(len(usergroup['users']), 2)

    def test_command_with_args(self):
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', '--quiet',
                              'alignak_cfg_files/hosts.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        self.assertEqual(exit_code, 0)

        c = self.backend.get('command')
        self.assertEqual(len(c['_items']), 4)
        command_id = ''
        ev_handler_id = ''
        for co in c['_items']:
            if co['name'] == 'check_tcp':
                command_id = co['_id']
            if co['name'] == 'my_host_event_handler':
                ev_handler_id = co['_id']
        self.assertNotEqual(command_id, '')
        self.assertNotEqual(ev_handler_id, '')

        result = self.backend.get('host', params={'where': json.dumps({'_is_template': False})})
        print(result)
        self.assertEqual(len(result['_items']), 3)
        for host in result['_items']:
            self.assertEqual(host['check_command'], command_id)
            if host['name'] == 'srv01':
                self.assertEqual(host['check_command_args'], '3306!5!8')
            if host['name'] == 'srv02':
                self.assertEqual(host['check_command_args'], '80!5!8')
            if host['name'] == 'srv03':
                self.assertEqual(host['check_command_args'], '')

    def test_command_event_handler(self):
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', '--quiet',
                              'alignak_cfg_files/hosts.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        self.assertEqual(exit_code, 0)

        c = self.backend.get('command')
        self.assertEqual(len(c['_items']), 4)
        command_id = ''
        ev_handler_id = ''
        for co in c['_items']:
            if co['name'] == 'check_tcp':
                command_id = co['_id']
            if co['name'] == 'my_host_event_handler':
                ev_handler_id = co['_id']
        self.assertNotEqual(command_id, '')
        self.assertNotEqual(ev_handler_id, '')

        result = self.backend.get('host', params={'where': json.dumps({'_is_template': False})})
        self.assertEqual(len(result['_items']), 3)
        for host in result['_items']:
            print("Host: %s", host)
            self.assertEqual(host['check_command'], command_id)
            self.assertEqual(host['event_handler'], ev_handler_id)
            if host['name'] == 'srv01':
                self.assertEqual(host['check_command_args'], '3306!5!8')
            if host['name'] == 'srv02':
                self.assertEqual(host['check_command_args'], '80!5!8')
            if host['name'] == 'srv03':
                self.assertEqual(host['check_command_args'], '')

    def test_host_customvariables(self):
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', '--quiet',
                              'alignak_cfg_files/hosts_custom_variables.cfg'])
        (_, _) = q.communicate()
        exit_code = q.wait()
        self.assertEqual(exit_code, 0)

        result = self.backend.get('host', params={'where': json.dumps({'_is_template': False})})
        hosts = result['_items']
        self.assertEqual(len(hosts), 1)

        print("Found hosts: ")
        for host in hosts:
            print("- %s, customs: %s" % (host['name'], host['customs']))
            self.assertEqual(host['customs'], {
                u'_DISPLAY_NAME': u'srv01', u'_LOC_LAT': u'45.054700', u'_LOC_LNG': u'5.080856'
            })


class TestContactsNW(unittest2.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set test mode for applications backend
        os.environ['TEST_ALIGNAK_BACKEND'] = '1'
        os.environ['ALIGNAK_BACKEND_MONGO_DBNAME'] = 'alignak-backend-import-test'

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
        fnull = open(os.devnull, 'w')
        cls.backend_process = subprocess.Popen(shlex.split('alignak-backend'))
        print("Started as %s" % cls.backend_process.pid)

        time.sleep(3)

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
        cls.backend_process.kill()
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
                self.assertEqual(user['is_admin'], False)
                self.assertEqual(user['back_role_super_admin'], True)
            else:
                self.assertEqual(user['back_role_super_admin'], False)
                self.assertTrue(user['host_notifications_enabled'])
                self.assertTrue(user['service_notifications_enabled'])
                self.assertEqual(user['host_notification_commands'], [cmd_nh1, cmd_nh2])
                self.assertEqual(user['service_notification_commands'], [cmd_ns])


class TestContacts(unittest2.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set test mode for applications backend
        os.environ['TEST_ALIGNAK_BACKEND'] = '1'
        os.environ['ALIGNAK_BACKEND_MONGO_DBNAME'] = 'alignak-backend-import-test'

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
        fnull = open(os.devnull, 'w')
        cls.backend_process = subprocess.Popen(shlex.split('alignak-backend'))
        print("Started as %s" % cls.backend_process.pid)

        time.sleep(3)

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
        cls.backend_process.kill()
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
            print("-", user['name'], user)
            if user['name'] == 'generic-contact':
                continue

            self.assertEqual(user['_is_template'], False)
            # Except the admin user, all are tagged with the generic-contact
            if user['name'] != 'admin':
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
                self.assertEqual(user['is_admin'], False)
                self.assertEqual(user['back_role_super_admin'], True)
                self.assertEqual(user['can_update_livestate'], True)
            else:
                self.assertEqual(user['is_admin'], True)
                self.assertEqual(user['back_role_super_admin'], False)
                self.assertEqual(user['can_update_livestate'], False)
                self.assertEqual(user['host_notification_commands'], [cmd_nh1])
                self.assertEqual(user['service_notification_commands'], [cmd_ns])


class TestHosts(unittest2.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set test mode for applications backend
        os.environ['TEST_ALIGNAK_BACKEND'] = '1'
        os.environ['ALIGNAK_BACKEND_MONGO_DBNAME'] = 'alignak-backend-import-test'

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
        fnull = open(os.devnull, 'w')
        cls.backend_process = subprocess.Popen(shlex.split('alignak-backend'))
        print("Started as %s" % cls.backend_process.pid)

        time.sleep(3)

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
        cls.backend_process.kill()
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


class TestServices(unittest2.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set test mode for applications backend
        os.environ['TEST_ALIGNAK_BACKEND'] = '1'
        os.environ['ALIGNAK_BACKEND_MONGO_DBNAME'] = 'alignak-backend-import-test'

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
        fnull = open(os.devnull, 'w')
        cls.backend_process = subprocess.Popen(shlex.split('alignak-backend'))
        print("Started as %s" % cls.backend_process.pid)

        time.sleep(3)

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
        cls.backend_process.kill()
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
