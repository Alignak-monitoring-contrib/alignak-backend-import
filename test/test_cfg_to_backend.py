#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest2
import time
import json
import subprocess
from alignak_backend_client.client import Backend


class TestCfgToBackend(unittest2.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.maxDiff=None
        # cls.p = subprocess.Popen(['uwsgi', '-w', 'alignakbackend:app', '--socket', '0.0.0.0:5000', '--protocol=http', '--enable-threads'])
        cls.p = subprocess.Popen(['alignak_backend'])
        print ("Backend PID: %s" % cls.p)
        time.sleep(3)

        cls.backend = Backend('http://127.0.0.1:5000')
        cls.backend.login("admin", "admin", "force")
        cls.backend.delete("host", {})
        cls.backend.delete("service", {})
        cls.backend.delete("command", {})
        cls.backend.delete("timeperiod", {})
        cls.backend.delete("livestate", {})
        cls.backend.delete("livesynthesis", {})

    @classmethod
    def tearDownClass(cls):
        cls.backend.delete("user", {})
        cls.p.kill()

    @classmethod
    def tearDown(cls):
        cls.backend.delete("host", {})
        cls.backend.delete("service", {})
        cls.backend.delete("command", {})
        cls.backend.delete("timeperiod", {})
        cls.backend.delete("livestate", {})
        cls.backend.delete("livesynthesis", {})

    def test_timeperiod(self):
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', 'alignak_cfg_files/timeperiods.cfg'])
        (stdoutdata, stderrdata) = q.communicate() # now wait

        result = self.backend.get('timeperiod')
        tps = result['_items']
        self.assertEqual(len(tps), 1)
        for comm in tps:
            ref = {u"name": u"workhours",
                   u"definition_order": 100,
                   u"notes": u"",
                   u"alias": u"Normal Work Hours",
                   u"dateranges": [{u'monday': u'09:00-17:00'}, {u'tuesday': u'09:00-17:00'},
                                   {u'friday': u'09:00-12:00,14:00-16:00'}, {u'wednesday': u'09:00-17:00'},
                                   {u'thursday': u'09:00-17:00'}],
                   u"exclude": [], u"is_active": False, u"imported_from": u"alignak_backend_import"
                   }
            del comm['_links']
            del comm['_id']
            del comm['_etag']
            del comm['_created']
            del comm['_updated']
            del comm['_realm']
            self.assertEqual(comm, ref)


    def test_timeperiod_complex(self):
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', 'alignak_cfg_files/timeperiods_complex.cfg'])
        (_, _) = q.communicate() # now wait

        r = self.backend.get_all('timeperiod')
        r = r['_items']
        self.assertEqual(len(r), 2)
        ref = {u"name": u"workhours",
               u"definition_order": 100,
               u"alias": u"Normal Work Hours",
               u"notes": u"",
               u"dateranges": [{u'monday': u'09:00-17:00'}, {u'tuesday': u'09:00-17:00'},
                               {u'friday': u'09:00-12:00,14:00-16:00'}, {u'wednesday': u'09:00-17:00'},
                               {u'thursday': u'09:00-17:00'}],
               u"exclude": [u'us-holidays'], u"is_active": False,
               u"imported_from": u"alignak_backend_import"}
        comm = r[0]
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
               u"dateranges": [{u'thursday -1 november': u'00:00-00:00'},
                               {u'monday 1 september': u'00:00-00:00'},
                               {u'january 1': u'00:00-00:00'},
                               {u'december 25': u'00:00-00:00'}, {u'july 4': u'00:00-00:00'}],
               u"exclude": [], u"is_active": False,
               u"imported_from": u"alignak_backend_import"}
        comm = r[1]
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
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', 'alignak_cfg_files/hosts_links_hostgroup.cfg'])
        (stdoutdata, stderrdata) = q.communicate() # now wait

        result = self.backend.get('host')
        hosts = result['_items']
        self.assertEqual(len(hosts), 1)
        for host in hosts:
            # host_id = hosts[0]['_id']
            print "Host:", host

        result = self.backend.get('hostgroup')
        hostgroups = result['_items']
        self.assertEqual(len(hostgroups), 2)
        for hostgroup in hostgroups:
            print "Hostgroup:", hostgroup
            print "Hostgroup groups:", hostgroup['hostgroups']
            self.assertEqual(hostgroup['hosts'], [hosts[0]['_id']])

    def test_host_multiple_link_later(self):
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', 'alignak_cfg_files/hosts_links_parent.cfg'])
        (stdoutdata, stderrdata) = q.communicate() # now wait

        result = self.backend.get('host')
        hosts = result['_items']
        self.assertEqual(len(hosts), 3)
        for host in hosts:
            print "Host:", host['name']
            if host['name'] == 'webui':
                webui = host.copy()
            if host['name'] == 'backend':
                backend = host.copy()
            if host['name'] == 'mongo':
                mongo = host.copy()

        print backend['parents']
        self.assertEqual(backend['parents'], [])
        print mongo['parents']
        self.assertEqual(mongo['parents'], [backend['_id']])
        print webui['parents']
        self.assertEqual(webui['parents'], [backend['_id'], mongo['_id']])

    def test_hostgroups_links(self):
        """
        """
        # host.hostgroups
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', 'alignak_cfg_files/hostgroups_links_hostgroup.cfg'])
        (stdoutdata, stderrdata) = q.communicate() # now wait

        result = self.backend.get('host')
        hosts = result['_items']
        self.assertEqual(len(hosts), 1)
        host_id = hosts[0]['_id']

        result = self.backend.get('hostgroup')
        hostgroups = result['_items']
        self.assertEqual(len(hostgroups), 2)
        for hostgroup in hostgroups:
            print "Hostgroup:", hostgroup
            print "Hostgroup groups members:", hostgroup['hostgroups']
            print "Hostgroup members:", hostgroup['hosts']
            if hostgroup['name'] == 'freebsd':
                self.assertEqual(len(hostgroup['hostgroups']), 1)
            if hostgroup['name'] == 'alignak':
                self.assertEqual(len(hostgroup['hostgroups']), 0)

    def test_command_with_args(self):
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', 'alignak_cfg_files/hosts.cfg'])
        (stdoutdata, stderrdata) = q.communicate() # now wait

        c = self.backend.get('command')
        self.assertEqual(len(c['_items']), 1)
        command_id = ''
        for co in c['_items']:
            command_id = co['_id']

        result = self.backend.get('host')
        self.assertEqual(len(result['_items']), 3)
        for host in result['_items']:
            self.assertEqual(host['check_command'], command_id)
            if host['name'] == 'srv01':
                self.assertEqual(host['check_command_args'], '3306!5!8')
            if host['name'] == 'srv02':
                self.assertEqual(host['check_command_args'], '80!5!8')
            if host['name'] == 'srv03':
                self.assertEqual(host['check_command_args'], '')

        co = self.backend.get_all('command')
        co = co['_items']
        self.assertEqual(len(co), 1)
        self.assertEqual(co[0]['name'], "check_tcp")

    def test_host_customvariables(self):
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', 'alignak_cfg_files/hosts_custom_variables.cfg'])
        (stdoutdata, stderrdata) = q.communicate() # now wait

        result = self.backend.get_all('host')
        hosts = result['_items']
        self.assertEqual(len(hosts), 1)

        print "Found hosts: "
        for host in hosts:
            print "- %s, customs: %s" % (host['name'], host['customs'])
            self.assertEqual(host['customs'], {u'_LOC_LAT': u'45.054700', u'_LOC_LNG': u'5.080856'})


class TestContacts(unittest2.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.p = subprocess.Popen(['alignak_backend'])
        print ("Backend PID: %s" % cls.p)
        time.sleep(3)

        cls.backend = Backend('http://127.0.0.1:5000')
        cls.backend.login("admin", "admin", "force")

    @classmethod
    def tearDownClass(cls):
        cls.p.kill()

    @classmethod
    def tearDown(cls):
        print ""

    def test_users(self):
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', 'alignak_cfg_files/users.cfg'])
        (stdoutdata, stderrdata) = q.communicate() # now wait

        result = self.backend.get_all('user')
        users = result['_items']
        self.assertEqual(len(users), 4)

        print "Found users: "
        for user in users:
            print "-", user['name']
            if user['name'] == 'admin':
                self.assertEqual(user['is_admin'], False)
                self.assertEqual(user['back_role_super_admin'], True)
            else:
                # self.assertEqual(user['is_admin'], True)
                self.assertEqual(user['back_role_super_admin'], False)

    def test_user_is_admin(self):
        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', 'alignak_cfg_files/user_admin.cfg'])
        (stdoutdata, stderrdata) = q.communicate() # now wait

        result = self.backend.get_all('user')
        users = result['_items']
        self.assertEqual(len(users), 2)

        print "Found users: "
        for user in users:
            print "-", user['name']
            if user['name'] == 'admin':
                self.assertEqual(user['is_admin'], False)
                self.assertEqual(user['back_role_super_admin'], True)
            else:
                self.assertEqual(user['is_admin'], True)
                self.assertEqual(user['back_role_super_admin'], False)


class TestHosts(unittest2.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.p = subprocess.Popen(['alignak_backend'])
        print ("Backend PID: %s" % cls.p)
        time.sleep(3)

        cls.backend = Backend('http://127.0.0.1:5000')
        cls.backend.login("admin", "admin", "force")

    @classmethod
    def tearDownClass(cls):
        cls.p.kill()

    @classmethod
    def tearDown(cls):
        print ""

    def test_hosts(self):

        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', 'alignak_cfg_files/hosts.cfg'])
        (stdoutdata, stderrdata) = q.communicate() # now wait

        result = self.backend.get('timeperiod')
        tps = result['_items']
        for tp in tps:
            print tp['_id'], tp['name']
            if tp['name'] == '24x7':
                tp_always = tp['_id']
            if tp['name'] == 'none':
                tp_never = tp['_id']
            if tp['name'] == 'All time default 24x7':
                tp_default = tp['_id']
        self.assertEqual(len(tps), 2)

        result = self.backend.get('host')
        hosts = result['_items']
        self.assertEqual(len(hosts), 3)
        for host in hosts:
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


    def test_host_with_double_template(self):

        q = subprocess.Popen(['../alignak_backend_import/cfg_to_backend.py', '--delete', 'alignak_cfg_files/hosts_2_templates.cfg'])
        (stdoutdata, stderrdata) = q.communicate() # now wait

        r = self.backend.get('host')
        self.assertEqual(len(r['_items']), 1)
        for comm in r['_items']:
            reg_comm = comm.copy()

        self.assertEqual(reg_comm['name'], 'srv01')
        self.assertEqual(reg_comm['max_check_attempts'], 6)
        self.assertEqual(reg_comm['check_interval'], 2)

