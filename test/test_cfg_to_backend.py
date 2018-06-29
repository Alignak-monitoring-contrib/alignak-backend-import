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
        cls.backend.login("admin", "admin")

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
                   u"dateranges": [{u'monday': u'09:00-17:00'},
                                   {u'tuesday': u'09:00-17:00'},
                                   {u'wednesday': u'09:00-17:00'},
                                   {u'thursday': u'09:00-17:00'},
                                   {u'friday': u'09:00-12:00,14:00-16:00'}],
                   u"exclude": [], u"is_active": False, u"imported_from": u"alignak-backend-import"
                   }
            del comm['_links']
            del comm['_id']
            del comm['_etag']
            del comm['_created']
            del comm['_updated']
            del comm['_realm']
            del comm['schema_version']
            dr1 = comm.pop('dateranges')
            dr2 = ref.pop('dateranges')
            self.assertEqual(comm, ref)
            # Dateranges are the same ?
            for dr in dr1:
                assert dr in dr2
            # assert not [k for k in dr1 if dr1[k] != dr2[k]]
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
                   u"dateranges": [{u'monday': u'09:00-18:00'},
                                   {u'tuesday': u'09:00-18:00'},
                                   {u'thursday': u'09:00-18:00'},
                                   {u'wednesday': u'09:00-18:00'},
                                   {u'friday': u'09:00-12:00,14:00-16:00'}
                                   ],
                   u"exclude": [], u"is_active": False, u"imported_from": u"alignak-backend-import"
                   }
            del comm['_links']
            del comm['_id']
            del comm['_etag']
            del comm['_created']
            del comm['_updated']
            del comm['_realm']
            del comm['schema_version']
            dr1 = comm.pop('dateranges')
            dr2 = ref.pop('dateranges')
            self.assertEqual(comm, ref)
            # Dateranges are the same ?
            for dr in dr1:
                assert dr in dr2
            # assert not [k for k in dr1 if dr1[k] != dr2[k]]
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
                   u"dateranges": [{u'monday': u'09:00-18:00'},
                                   {u'tuesday': u'09:00-18:00'},
                                   {u'wednesday': u'09:00-18:00'},
                                   {u'thursday': u'09:00-18:00'},
                                   {u'friday': u'09:00-12:00,14:00-16:00'}
                                   ],
                   u"exclude": [], u"is_active": False, u"imported_from": u"alignak-backend-import"
                   }
            del comm['_links']
            del comm['_id']
            del comm['_etag']
            del comm['_created']
            del comm['_updated']
            del comm['_realm']
            del comm['schema_version']
            dr1 = comm.pop('dateranges')
            dr2 = ref.pop('dateranges')
            self.assertEqual(comm, ref)
            # Dateranges are the same ?
            for dr in dr1:
                assert dr in dr2
            # assert not [k for k in dr1 if dr1[k] != dr2[k]]
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
            del comm['schema_version']
            dr1 = comm.pop('dateranges')
            dr2 = ref.pop('dateranges')
            self.assertEqual(comm, ref)
            # Dateranges are the same ?
            for dr in dr1:
                assert dr in dr2
            # assert not [k for k in dr1 if dr1[k] != dr2[k]]
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
        del comm['schema_version']
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
        del comm['schema_version']
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
        self.assertEqual(len(c['_items']), 6)
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
        self.assertEqual(len(c['_items']), 6)
        command_id = ''
        ev_handler_id = ''
        for co in c['_items']:
            print("Command: %s" % co)
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
                u'_LOC_LAT': u'45.054700', u'_LOC_LNG': u'5.080856'
            })
