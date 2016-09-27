#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Copyright (C) 2015-2016: Alignak team, see AUTHORS.txt file for contributors
#
# This file is part of Alignak Backend Import.
#
# Alignak Backend Import is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Alignak Backend Import is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Alignak Backend Import.  If not, see <http://www.gnu.org/licenses/>.

"""
alignak_backend_import command line interface::

    Usage:
        {command} [-h] [-v] [-d] [-i] [-e] [-m] [-b=url] [-u=username] [-p=password] [<cfg_file>...]

    Options:
        -h, --help                  Show this screen.
        -V, --version               Show application version.
        -b, --backend url           Specify backend URL [default: http://127.0.0.1:5000]
        -d, --delete                Delete existing backend data [default: False]
        -e, --update                Update existing backend data [default: False]
        -i, --duplicate             Do not stop on duplicate items [default: False]
        -u, --username username     Backend login username [default: admin]
        -p, --password password     Backend login password [default: admin]
        -v, --verbose               Run in verbose mode (more info to display)
        -m, --model                 Import templates when they exist
        -g, --gps lat,lng           Specify default GPS location [default: 46.60611,1.87528]

    Use cases:
        Display help message:
            {command} -h

        Display current version:
            {command} -v

        Delete current backend data:
            {command} -d [-b=backend] [-u=username] [-p=password]

        Add some data in current backend:
            {command} [-b=backend] [-u=username] [-p=password] <cfg_file>

        Replace current backend data:
            {command} -d [-b=backend] [-u=username] [-p=password] <cfg_file>

        Replace current backend data and include templates:
            {command} -m -d [-b=backend] [-u=username] [-p=password] <cfg_file>

        Exit code:
            0 if required operation succeeded
            1 if Alignak is not installed on your system
            2 if backend access is denied (check provided username/password)
            3 if required configuration cannot be loaded by Alignak
            4 if some problems were encountered during backend importation
            5 if an exception occured when creating/updating data in the Alignak backend
            6 if an imported element is not named (can not find its name)

            64 if command line parameters are not used correctly
"""
from __future__ import print_function
import re
import json
import traceback

from copy import deepcopy

from logging import getLogger, INFO

from docopt import docopt
from docopt import DocoptExit

from future.utils import iteritems

try:
    from alignak.daemons.arbiterdaemon import Arbiter
    from alignak.commandcall import CommandCall
    from alignak.objects.item import Item
    from alignak.objects.config import Config
    import alignak.daterange as daterange
except ImportError:
    print("Alignak is not installed...")
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~")
    print("Exiting with error code: 1")
    exit(1)

from alignak_backend_client.client import Backend, BackendException

from alignak_backend_import import __version__

from alignak_backend.models import realm
from alignak_backend.models import command
from alignak_backend.models import timeperiod
from alignak_backend.models import host
from alignak_backend.models import hostgroup
from alignak_backend.models import hostdependency
from alignak_backend.models import hostescalation
from alignak_backend.models import service
from alignak_backend.models import servicegroup
from alignak_backend.models import servicedependency
from alignak_backend.models import serviceescalation
from alignak_backend.models import user
from alignak_backend.models import usergroup
from alignak_backend.models import userrestrictrole

loggerClient = getLogger('alignak_backend_client.client')
loggerClient.setLevel(INFO)


class CfgToBackend(object):
    """
    Class to manage an item
    An Item is the base of many objects of Alignak. So it define common properties,
    common functions.
    """

    # Store list of errors found
    errors_found = []

    def __init__(self):
        self.result = True
        self.later = {}
        self.inserted = {}
        self.inserted_uuid = {}
        self.ignored = {}

        # Get command line parameters
        args = None
        try:
            args = docopt(__doc__, version=__version__)
        except DocoptExit:
            print(
                "Command line parsing error.\n"
                "alignak_backend_import -h will display the command line parameters syntax."
            )
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~")
            print("Exiting with error code: 64")
            exit(64)

        # Verbose
        self.verbose = False
        if '--verbose' in args and args['--verbose']:
            self.verbose = True

        # Define here the path of the cfg files
        cfg = None
        if '<cfg_file>' in args:
            cfg = args['<cfg_file>']
            self.log("Configuration to load: %s" % cfg)
            print("Importing configuration: %s" % cfg)
        else:
            self.log("No configuration specified")

        if not cfg:
            print("No configuration specified")
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~")
            print("Exiting with error code: 2")
            exit(2)

        if not isinstance(cfg, list):
            cfg = [cfg]

        # Define here the url of the backend
        self.backend = None
        self.backend_url = args['--backend']
        self.log("Backend URL: %s" % self.backend_url)
        print("Backend URL: %s" % self.backend_url)

        self.username = args['--username']
        self.password = args['--password']
        self.log("Backend login with credentials: %s/%s" % (self.username, self.password))

        # Delete all objects in backend ?
        self.destroy_backend_data = args['--delete']
        self.log("Delete existing backend data: %s" % self.destroy_backend_data)
        print("Delete existing backend data: %s" % self.destroy_backend_data)

        # Update objects in the backend rather than create them
        self.update_backend_data = args['--update']
        self.log("Updating backend data: %s" % self.update_backend_data)
        print("Updating backend data: %s" % self.update_backend_data)

        self.allow_duplicates = False
        if '--duplicate' in args:
            self.allow_duplicates = args['--duplicate']
        self.log("Allowing duplicate objects: %s" % self.allow_duplicates)
        print("Allowing duplicate objects: %s" % self.allow_duplicates)

        self.models = False
        if '--model' in args:
            self.models = args['--model']
        self.log("Importing objects templates: %s" % self.models)
        print("Importing objects templates: %s" % self.models)

        self.gps = {"type": "Point", "coordinates": [46.60611, 1.87528]}
        if '--gps' in args:
            point = args['--gps'].split(',')
            self.gps.coordinates = point
        self.log("Default host location: %s" % self.gps)
        print("Default host location: %s" % self.gps)

        # Alignak arbiter configuration
        # - configuration
        # - is_daemon
        # - do_replace
        # - verify_only
        # - debug
        # - debug_file
        # - config_name (new from 2016-08-06)
        # - analyse=None
        # pylint: disable=too-many-function-args
        try:
            print("Try new Arbiter signature...")
            self.arbiter = Arbiter(cfg, False, False, False, False, '', 'arbiter-master', None)
        except Exception as e:
            print("Try old Arbiter signature... %s" % str(e))
            self.arbiter = Arbiter(cfg, False, False, False, False, '', None)

        try:
            # Get flat files configuration
            self.arbiter.load_config_file()

            # Raw configuration
            self.raw_conf = Config()
            buf = self.raw_conf.read_config(cfg)
            self.raw_objects = self.raw_conf.read_config_buf(buf)
        except Exception as e:
            print("Configuration loading exception: %s" % str(e))
            print("***** Traceback: %s", traceback.format_exc())
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~")
            print("Exiting with error code: 3")
            exit(3)

        # Authenticate on Backend
        self.authenticate()

        # Default realm
        self.realm_all = ''
        self.default_realm = ''
        realms = self.backend.get_all('realm')
        for r in realms['_items']:
            if r['name'] == 'All' and r['_level'] == 0:
                self.inserted['realm'] = {}
                self.inserted['realm'][r['_id']] = 'All'
                self.realm_all = r['_id']

        # Default timeperiods
        self.inserted['timeperiod'] = {}
        self.al_always = None
        self.tp_always = None
        timeperiods = self.backend.get_all('timeperiod')
        for tp in timeperiods['_items']:
            if tp['name'] == '24x7':
                self.inserted['timeperiod'][tp['_id']] = '24x7'
                self.tp_always = tp['_id']

        self.al_none = None
        self.al_never = None
        self.tp_never = None
        timeperiods = self.backend.get_all('timeperiod')
        for tp in timeperiods['_items']:
            if tp['name'] == 'Never':
                self.inserted['timeperiod'][tp['_id']] = 'Never'
                self.tp_never = tp['_id']

        # Default user
        users = self.backend.get_all('user')
        for u in users['_items']:
            if u['name'] == 'admin':
                self.inserted['user'] = {}
                self.inserted['user'][u['_id']] = 'admin'

        # Default commands
        self.default_command = ''
        commands = self.backend.get_all('command')
        for c in commands['_items']:
            if c['name'] == '_internal_host_up' or c['name'] == '_echo':
                if 'command' not in self.inserted:
                    self.inserted['command'] = {}
                self.inserted['command'][c['_id']] = c['name']
                self.default_command = c['_id']

        # Default dummy host
        self.dummy_host = ''
        hosts = self.backend.get_all('host')
        for h in hosts['_items']:
            if h['name'] == '_dummy':
                if 'host' not in self.inserted:
                    self.inserted['host'] = {}
                self.inserted['host'][h['_id']] = h['name']
                self.dummy_host = h['_id']

        # Build templates lists from raw Arbiter objects
        if self.models:
            self.build_templates()
            print("-----")
            print("Found %d hosts templates" % len(self.hosts_templates))
            print("Found %d services templates" % len(self.services_templates))

            if not self.dummy_host:
                print("**********")
                print("No _dummy host found in the backend. "
                      "Importing service models may raise errors!")
                print("**********")

        # Rebuild the date ranges in the raw Arbiter objects (raw objects are modified!)
        self.recompose_dateranges()

        # Delete data in backend if asked in arguments
        if self.destroy_backend_data:
            self.delete_data()

        # Import the objects in the backend
        self.import_objects()
        if self.errors_found:
            print('############################# errors report ##################################')
            for error in self.errors_found:
                print(error)
            print('##############################################################################')
        self.result = len(self.errors_found) == 0

    def authenticate(self):
        """
        Login on backend with username and password

        :return: None
        """
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Backend authentication ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        try:
            # Backend authentication with token generation
            # headers = {'Content-Type': 'application/json'}
            # payload = {'username': self.username, 'password': self.password, 'action': 'generate'}
            self.backend = Backend(self.backend_url)
            self.backend.login(self.username, self.password)
        except BackendException as e:
            print("Backend exception: %s" % str(e))

        if self.backend.token is None:
            print("Access denied!")
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~")
            print("Exiting with error code: 2")
            exit(2)
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Authenticated ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")

    def delete_data(self):
        """
        Delete data in backend

        :return: None
        """
        try:
            print("~~~~~~~~~~~~~~~~~~~~~~~~ Deleting existing backend data ~~~~~~~~~~~~~~~~~~~~~~")
            headers = {'Content-Type': 'application/json'}
            print("Deleting realms")
            # Get realms in _level reverse order to be able to delete them ...
            realms = self.backend.get('realm', params={'sort': '-_level'})
            headers = {'Content-Type': 'application/json'}
            for r in realms['_items']:
                if r['name'] != 'All':
                    print("Deleting realm: %s" % r['name'])
                    to_del = self.backend.get('realm/' + r['_id'])
                    headers['If-Match'] = to_del['_etag']
                    self.backend.delete('realm/' + to_del['_id'], headers)

            print("Deleting commands")
            commands = self.backend.get_all('command')
            headers = {'Content-Type': 'application/json'}
            for c in commands['_items']:
                if c['name'] != '_internal_host_up' and c['name'] != '_echo':
                    print("Deleting command: %s" % c['name'])
                    headers['If-Match'] = c['_etag']
                    self.backend.delete('command/' + c['_id'], headers)

            print("Deleting timeperiods")
            timeperiods = self.backend.get_all('timeperiod')
            headers = {'Content-Type': 'application/json'}
            for tp in timeperiods['_items']:
                if tp['name'] != '24x7' and tp['name'] != 'Never':
                    print("Deleting timeperiod: %s" % tp['name'])
                    headers['If-Match'] = tp['_etag']
                    self.backend.delete('timeperiod/' + tp['_id'], headers)

            print("Deleting users")
            users = self.backend.get_all('user')
            headers = {'Content-Type': 'application/json'}
            for u in users['_items']:
                if u['name'] != 'admin':
                    print("Deleting user: %s" % u['name'])
                    headers['If-Match'] = u['_etag']
                    self.backend.delete('user/' + u['_id'], headers)

            print("Deleting usergroups")
            usergroups = self.backend.get_all('usergroup')
            headers = {'Content-Type': 'application/json'}
            for ug in usergroups['_items']:
                if ug['name'] != 'All':
                    print("Deleting usergroup: %s" % ug['name'])
                    headers['If-Match'] = ug['_etag']
                    self.backend.delete('usergroup/' + ug['_id'], headers)

            print("Deleting hosts")
            hosts = self.backend.get_all('host')
            headers = {'Content-Type': 'application/json'}
            for h in hosts['_items']:
                if h['name'] != '_dummy':
                    print("Deleting host: %s" % h['name'])
                    headers['If-Match'] = h['_etag']
                    self.backend.delete('host/' + h['_id'], headers)

            print("Deleting hostdependencys")
            self.backend.delete('hostdependency', headers)

            print("Deleting hostgroups")
            hostgroups = self.backend.get_all('hostgroup')
            headers = {'Content-Type': 'application/json'}
            for hg in hostgroups['_items']:
                if hg['name'] != 'All':
                    print("Deleting hostgroup: %s" % hg['name'])
                    headers['If-Match'] = hg['_etag']
                    self.backend.delete('hostgroup/' + hg['_id'], headers)

            print("Deleting hostescalations")
            self.backend.delete('hostescalation', headers)

            print("Deleting services")
            self.backend.delete('service', headers)

            print("Deleting servicedependencys")
            self.backend.delete('servicedependency', headers)

            print("Deleting servicegroups")
            servicegroups = self.backend.get_all('servicegroup')
            headers = {'Content-Type': 'application/json'}
            for sg in servicegroups['_items']:
                if sg['name'] != 'All':
                    print("Deleting servicegroup: %s" % sg['name'])
                    headers['If-Match'] = sg['_etag']
                    self.backend.delete('servicegroup/' + sg['_id'], headers)

            print("Deleting serviceescalations")
            self.backend.delete('serviceescalation', headers)

            print("Deleting userrestrictroles")
            self.backend.delete('userrestrictrole', headers)

            print("Deleting livesynthesis")
            self.backend.delete('livesynthesis', headers)

            print("Deleting actions acknowledge")
            self.backend.delete('actionacknowledge', headers)
            print("Deleting actions downtime")
            self.backend.delete('actiondowntime', headers)
            print("Deleting actions re-check")
            self.backend.delete('actionforcecheck', headers)

            print("~~~~~~~~~~~~~~~~~~~~~~~~ Existing backend data destroyed ~~~~~~~~~~~~~~~~~~~~~")
        except BackendException as e:
            print("# Backend deletion error")
            print("***** Exception: %s" % str(e))
            print("***** Traceback: %s", traceback.format_exc())
            print("***** response: %s" % e.response)
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~")
            print("Exiting with error code: 5")
            exit(5)

    def build_templates(self):
        """
        Get the templates from the raw objects and build templates lists

        :return: None
        """
        # Create objects from raw objects
        self.raw_conf.create_objects(self.raw_objects)
        # Create Template links
        self.raw_conf.linkify_templates()
        # All inheritances
        self.raw_conf.apply_inheritance()
        # Explode between types
        self.raw_conf.explode()
        # Implicit inheritance for services
        self.raw_conf.apply_implicit_inheritance()
        # Fill default values
        self.raw_conf.fill_default()

        self.log("*** Parse templates ***")

        self.hosts_templates = []
        hosts = getattr(self.raw_conf, 'hosts')
        for tpl_uuid in hosts.templates:
            self.log("Host template: %s" % (hosts.templates[tpl_uuid]))
            self.hosts_templates.append(hosts.templates[tpl_uuid])

        self.services_templates = []
        services = getattr(self.raw_conf, 'services')
        for tpl_uuid in services.templates:
            # Only the one with declared host_name...
            host_name = getattr(services.templates[tpl_uuid], 'host_name', None)
            if not host_name:
                # Use the backend default dummy host
                setattr(services.templates[tpl_uuid], 'host_name', self.dummy_host)
                self.log(
                    "Service template with no host: %s" % (services.templates[tpl_uuid])
                )
                self.services_templates.append(services.templates[tpl_uuid])
                continue

            # Several host templates can be specified as a comma separated list...
            if ',' in host_name:
                host_names = host_name.split(',')
            else:
                host_names = [host_name]
            # Define a service template for each host
            for host_name in host_names:
                setattr(services.templates[tpl_uuid], 'host_name', host_name.strip())
                self.log("Service template with host: %s" % (services.templates[tpl_uuid]))
                self.services_templates.append(services.templates[tpl_uuid])

    def recompose_dateranges(self):
        """
        For each timeperiod, recompose daterange in backend format

        :return: None
        """
        # modify dateranges of timeperiods
        fields = ['imported_from', 'use', 'name', 'definition_order', 'register',
                  'timeperiod_name', 'alias', 'dateranges', 'exclude', 'is_active']
        for ti in self.raw_objects['timeperiod']:
            dateranges = []
            for propti in ti:
                if propti not in fields:
                    self.log("=-=-=-=-=-=-=-=-=-")
                    self.log(propti)
                    self.log(ti[propti])
                    # case we have in ti[propti] many spaces like for:
                    # december 25             00:00-00:00
                    if len(ti[propti]) == 1 and '  ' in ti[propti][0]:
                        self.log("++++++++++++++++++++++++++++++++++++++++++++++++++")
                        recomp = propti + ' ' + ti[propti][0]
                        explode_dr = recomp.split('  ')
                        dateranges.append({explode_dr[0]: explode_dr[-1].strip()})
                    else:
                        for times in ti[propti]:
                            if '  ' in times:
                                recomp = propti + ' ' + times
                                explode_dr = recomp.split('  ')
                                dateranges.append({explode_dr[0]: explode_dr[-1].strip()})
                            else:
                                dateranges.append({propti: times})
            ti['dr'] = dateranges

    def recompose_commands(self, commands):
        """
        Rebuild command (or commands) property

        Returns a list of tuples containing:
        - command uuid
        - command name
        - command arguments

        :param commands: command or commands list
        :return: tuples list
        :rtype:
        """
        commands_list = []

        if not isinstance(commands, list):
            commands = [commands]

        for cmd_in_list in commands:
            if not cmd_in_list:
                continue
            if 'alignak.commandcall.CommandCall' in str(type(cmd_in_list)):
                c_command = getattr(cmd_in_list, 'command').command_name
                c_params = getattr(cmd_in_list, 'args')
                commands_list.append((cmd_in_list.uuid, c_command, c_params))
            else:
                # Explode command name as command / args
                c_call = cmd_in_list.replace(r'\!', '___PROTECT_EXCLAMATION___')
                tab = c_call.split('!')
                c_command = tab[0].strip()
                c_params = [s.replace('___PROTECT_EXCLAMATION___', '!') for s in tab[1:]]

                commands = getattr(self.arbiter.conf, 'commands')
                for cmd in commands:
                    if cmd.command_name == c_command:
                        print("-> Replaced command name with command id for: %s" % (
                            cmd.command_name
                        ))
                        commands_list.append((cmd.uuid, c_command, c_params))
                        break

        return commands_list

    def convert_objects(self, source):
        """
        Convert objects in name of this object

        :param source: object properties
        :type source: dict
        :return: properties modified
        :rtype: dict
        """
        names = ['services', 'service', 'hosts', 'host', 'dependent_host',
                 'dependent_hostgroup_name', 'command_name', 'timeperiod_name']
        addprop = {}
        # First iteration to update notification ways (#19)
        for prop in source:
            # Notification ways
            if prop == 'notificationways':
                nws = getattr(self.arbiter.conf, 'notificationways')
                for nw in nws:
                    # Update user information with the notification way properties
                    addprop['host_notifications_enabled'] = nw.host_notifications_enabled
                    addprop['service_notifications_enabled'] = nw.service_notifications_enabled
                    if nw.host_notification_period == self.al_always:
                        addprop['host_notification_period'] = self.tp_always
                    elif nw.host_notification_period == self.al_none:
                        addprop['host_notification_period'] = self.tp_never
                    elif nw.host_notification_period == self.al_never:
                        addprop['host_notification_period'] = self.tp_never
                    else:
                        addprop['host_notification_period'] = nw.host_notification_period
                    if nw.service_notification_period == self.al_always:
                        addprop['service_notification_period'] = self.tp_always
                    elif nw.service_notification_period == self.al_none:
                        addprop['service_notification_period'] = self.tp_never
                    elif nw.service_notification_period == self.al_never:
                        addprop['service_notification_period'] = self.tp_never
                    else:
                        addprop['service_notification_period'] = nw.service_notification_period
                    addprop['host_notification_options'] = nw.host_notification_options
                    addprop['service_notification_options'] = nw.service_notification_options
                    addprop['host_notification_commands'] = nw.host_notification_commands
                    addprop['service_notification_commands'] = nw.service_notification_commands
                    addprop['min_business_impact'] = nw.min_business_impact
                    # Ignore other defined NW
                    break
        source.update(addprop)

        # Second iteration after update of notification ways (#19)
        for prop in source:
            # Unique commands
            if prop in ['check_command', 'event_handler', 'snapshot_command']:
                is_commands_list = isinstance(source[prop], list)

                new_commands = self.recompose_commands(source[prop])
                if is_commands_list:
                    source[prop] = []
                for c_id, c_name, c_args in new_commands:
                    print("- new command: %s - %s - %s" % (c_id, c_name, c_args))
                    if is_commands_list:
                        source[prop].append(c_name)
                    else:
                        source[prop] = c_name
                    if c_args:
                        addprop['%s_args' % prop] = c_args
                        print("-> Added %s_args: %s" % (prop, addprop['%s_args' % prop]))
                    if not is_commands_list:
                        break
                addprop[prop] = source[prop]

            # Commands list
            if prop in ['service_notification_commands', 'host_notification_commands']:
                is_commands_list = isinstance(source[prop], list)

                new_commands = self.recompose_commands(source[prop])
                if is_commands_list:
                    source[prop] = []
                for c_id, c_name, c_args in new_commands:
                    print("- new command: %s - %s - %s" % (c_id, c_name, c_args))
                    if is_commands_list:
                        source[prop].append(c_name)
                    else:
                        source[prop] = c_name
                    if c_args:
                        addprop['%s_args' % prop] = c_args
                        print("-> Added %s_args: %s" % (prop, addprop['%s_args' % prop]))
                    if not is_commands_list:
                        break
                addprop[prop] = source[prop]

            if prop == 'dateranges':
                for ti in self.raw_objects['timeperiod']:
                    if ti['timeperiod_name'][0] == source['timeperiod_name']:
                        source[prop] = ti['dr']
            elif isinstance(source[prop], list) and source[prop] and isinstance(source[prop][0],
                                                                                Item):
                elements = []
                for element in source[prop]:
                    for name in names:
                        if hasattr(element, name):
                            self.log('Found %s in prop %s' % (name, prop))
                            elements.append(getattr(element, name))
                            break
                source[prop] = elements
            elif isinstance(source[prop], Item):
                for name in names:
                    if hasattr(source[prop], name):
                        self.log('Found %s in prop %s' % (name, prop))
                        source[prop] = getattr(source[prop], name)
                        break
            elif isinstance(source[prop], object):
                self.log("%s = %s" % (prop, source[prop]))

            # Rename contact as user ...
            if prop == 'contacts':
                source['users'] = source[prop]
                source.pop('contacts')
            if prop == 'contact_name':
                source['name'] = source[prop]
                # Do not remove this attribute, else dict size changes! Manage this later...
                # source.pop('contact_name')
            if prop == 'contactgroup_name':
                source['name'] = source[prop]
                # Do not remove this attribute, else dict size changes! Manage this later...
                # source.pop('contactgroup_name')
            if prop == 'contact_groups':
                source['usergroups'] = source[prop]
                source.pop('contact_groups')
            if prop == 'contactgroups':
                source['usergroups'] = source[prop]
                source.pop('contactgroups')

        source.update(addprop)
        self.log("Converted: %s" % source)
        return source

    def update_later(self, resource, field):
        """
        Update field of resource having a link with other resources (objectid in backend)

        :param resource: resource name (command, user, host...)
        :type resource: str
        :param field: field of resource to update
        :type field: str
        :return: None
        """
        headers = {'Content-Type': 'application/json'}
        for (index, item) in iteritems(self.later[resource][field]):
            print("Late update for: %s/%s -> %s" % (resource, index, item))
            if item['type'] == 'simple':
                data = {field: []}
                val = item['value']
                if val not in self.inserted[item['resource']] and \
                   val not in self.inserted[item['resource']].values() and \
                   val not in self.inserted_uuid[item['resource']].values():
                    self.errors_found.append("# Unknown %s: %s for %s" % (item['resource'],
                                                                          val, resource))
                else:
                    if val in self.inserted[item['resource']]:
                        data[field] = self.inserted[item['resource']][val]
                    elif val in self.inserted[item['resource']].values():
                        idx = self.inserted[item['resource']].values().index(val)
                        data[field] = self.inserted[item['resource']].keys()[idx]
                    elif val in self.inserted_uuid[item['resource']].values():
                        idx = self.inserted_uuid[item['resource']].values().index(val)
                        data[field] = self.inserted_uuid[item['resource']].keys()[idx]
                print("Late update for: %s/%s -> %s" % (resource, index, data))
            elif item['type'] == 'list':
                data = {field: []}
                if isinstance(item['value'], basestring):
                    item['value'] = item['value'].split(',')
                for val in item['value']:
                    val = val.strip()
                    if val != '':
                        if val not in self.inserted[item['resource']] and \
                           val not in self.inserted[item['resource']].values() and \
                           val not in self.inserted_uuid[item['resource']].values():
                            self.errors_found.append("# Unknown %s: %s for %s" % (item['resource'],
                                                                                  val, resource))
                        else:
                            if val in self.inserted[item['resource']]:
                                data[field].append(self.inserted[item['resource']][val])
                            elif val in self.inserted[item['resource']].values():
                                idx = self.inserted[item['resource']].values().index(val)
                                data[field].append(self.inserted[item['resource']].keys()[idx])
                            elif val in self.inserted_uuid[item['resource']].values():
                                idx = self.inserted_uuid[item['resource']].values().index(val)
                                data[field].append(
                                    self.inserted_uuid[item['resource']].keys()[idx]
                                )
                print("Late update for: %s/%s -> %s" % (resource, index, data))

            endpoint = ''.join([resource, '/', index])
            try:
                self.log("before_patch: %s : %s:" % (endpoint, data))
                to_patch = self.backend.get(endpoint)
                headers['If-Match'] = to_patch['_etag']
                resp = self.backend.patch(endpoint, data, headers, True)
            except BackendException as e:
                print("# Patch error for: %s : %s" % (endpoint, data))
                print("***** Exception: %s" % str(e))
                print("***** Traceback: %s", traceback.format_exc())
                print("***** response: %s" % e.response)
                print("~~~~~~~~~~~~~~~~~~~~~~~~~~")
                print("Exiting with error code: 5")
                exit(5)
            else:
                if '_status' in resp:
                    if resp['_status'] == 'ERR':
                        raise ValueError(resp['_issues'])
                    elif resp['_status'] == 'OK':
                        for (ind, dummy) in iteritems(self.later[resource]):
                            if index in self.later[resource][ind]:
                                self.later[resource][ind][index]['_etag'] = resp['_etag']

    def manage_resource(self, r_name, data_later, id_name, schema, template=False):
        # pylint: disable=protected-access, too-many-arguments
        # pylint: disable=too-many-locals
        """
        Array of data to include in internal cache or to update with internal objects cache:
        data_later = [
            {
                'field': 'use', 'type': 'simple|list', 'resource': 'command', 'now': True
            }
        ]
        field: field name in the current managed element
        type: object type (list, ...)
        resource: object backend element type
        now: tries to update immediatly or store for a future update (update_later)


        :param r_name: resource name
        :type r_name: str
        :param data_later:
        :param id_name:
        :param schema:
        :return:
        """
        if r_name not in self.inserted:
            self.inserted[r_name] = {}
        if r_name not in self.inserted_uuid:
            self.inserted_uuid[r_name] = {}
        if r_name not in self.later:
            self.later[r_name] = {}
        for dummy, values in enumerate(data_later):
            if values['field'] not in self.later[r_name]:
                self.later[r_name][values['field']] = {}

        alignak_resource = r_name + 's'
        if re.search('y$', r_name):
            alignak_resource = re.sub('y$', 'ies', r_name)
        elif r_name == 'hostextinfo':
            alignak_resource = 'hostsextinfo'
        elif r_name == 'serviceextinfo':
            alignak_resource = 'servicesextinfo'
        elif r_name == 'user':
            alignak_resource = 'contacts'
        elif r_name == 'usergroup':
            alignak_resource = 'contactgroups'

        # Alignak defined timeperiods
        timeperiods = getattr(self.arbiter.conf, 'timeperiods')

        elements = None
        # Alignak defined hostgroups
        if r_name == 'hostgroup':
            hgs = getattr(self.arbiter.conf, 'hostgroups')
            for hg in hgs:
                hg._parent = None

            for hg in hgs:
                for child in sorted(hg.get_hostgroup_members()):
                    if not child:
                        continue
                    # Search child group...
                    print("Found child: %s for %s" % (
                        child, hg.hostgroup_name
                    ))
                    for group in hgs:
                        if group.get_name() == child:
                            print("Found parent: %s (%s) for %s" % (
                                hg.uuid, hg.hostgroup_name, group
                            ))
                            group._parent = hg.uuid
                            break
            for hg in hgs:
                print("HG: %s (%s) - %s" % (
                    hg.uuid, hg.hostgroup_name, hg._parent
                ))
                hg.properties['_parent'] = hg._parent
            elements = hgs
        # Alignak defined servicegroups
        elif r_name == 'servicegroup':
            sgs = getattr(self.arbiter.conf, 'servicegroups')
            for sg in sgs:
                sg._parent = None

            for sg in sgs:
                for child in sorted(sg.get_servicegroup_members()):
                    if not child:
                        continue
                    # Search child group...
                    print("Found child: %s for %s" % (
                        child, sg.servicegroup_name
                    ))
                    for group in sgs:
                        if group.get_name() == child:
                            print("Found parent: %s (%s) for %s" % (
                                sg.uuid, sg.servicegroup_name, group
                            ))
                            group._parent = sg.uuid
                            break
            for sg in sgs:
                print("SG: %s (%s) - %s" % (
                    sg.uuid, sg.servicegroup_name, sg._parent
                ))
                sg.properties['_parent'] = sg._parent
            elements = sgs
        # Alignak defined usergroups
        elif r_name == 'usergroup':
            ugs = getattr(self.arbiter.conf, 'contactgroups')
            for ug in ugs:
                ug._parent = None

            for ug in ugs:
                for child in sorted(ug.get_contactgroup_members()):
                    if not child:
                        continue
                    # Search child group...
                    print("Found child: %s for %s" % (
                        child, ug.contactgroup_name
                    ))
                    for group in ugs:
                        if group.get_name() == child:
                            print("Found parent: %s (%s) for %s" % (
                                ug.uuid, ug.contactgroup_name, group
                            ))
                            group._parent = ug.uuid
                            break
            for ug in ugs:
                print("UG: %s (%s) - %s" % (
                    ug.uuid, ug.contactgroup_name, ug._parent
                ))
                ug.properties['_parent'] = ug._parent
            elements = ugs
        else:
            elements = getattr(self.arbiter.conf, alignak_resource)

        # Alignak defined realms
        if self.default_realm == '':
            realms = getattr(self.arbiter.conf, 'realms')
            default_realm = realms.get_default()
            print ("Realms: %s, default: %s" % (realms, default_realm))
            self.default_realm = default_realm.uuid
            print ("*** Alignak default realm: %s (%s)" % (
                self.default_realm, default_realm.get_name()
            ))

        # Build templates list to replace Alignak elements
        if template:
            self.inserted['%s_template' % r_name] = {}
            if r_name == 'host':
                elements = self.hosts_templates

            if r_name == 'service':
                elements = self.services_templates

        for item_obj in elements:
            if not item_obj:
                continue
            item = {}

            self.log("...................................")
            self.log("Manage resource %s: %s (%s)" % (r_name, item_obj.uuid, item_obj.get_name()))
            print("...................................")
            if template:
                print("Manage template %s: %s (%s)" % (r_name, item_obj.uuid, item_obj.get_name()))
            else:
                print("Manage resource %s: %s (%s)" % (r_name, item_obj.uuid, item_obj.get_name()))

            # Only deal with properties,
            for prop in item_obj.properties.keys():
                if not hasattr(item_obj, prop):
                    continue
                item[prop] = getattr(item_obj, prop)
            # As of it, ignore attributes (use, name, definition_order and register) !

            # Remove unused attributes...
            # ------------------------------------------------------------
            #  - retain_nonstatus_information / retain_status_information
            if 'retain_status_information' in item:
                # print ("-> remove retain_status_information.")
                item.pop('retain_status_information')
            if 'retain_nonstatus_information' in item:
                # print ("-> remove retain_nonstatus_information.")
                item.pop('retain_nonstatus_information')

            # Ignore specific items ...
            # ------------------------------------------------------------
            #  - admin user (managed later...)

            #  - default timeperiod
            if r_name == 'timeperiod' and item[id_name] == "24x7":
                print ("-> do not change anything for default timeperiod.")
                self.al_always = item_obj.uuid
                continue

            if r_name == 'timeperiod' and item[id_name] == "none":
                self.al_none = item_obj.uuid
                print ("-> do not change anything for default timeperiod.")
                continue

            if r_name == 'timeperiod' and item[id_name] == "Never":
                self.al_never = item_obj.uuid
                print ("-> do not change anything for default timeperiod.")
                continue

            #  - default realm
            if r_name == 'realm' and item[id_name] == "All":
                print ("-> do not change anything for default realm: %s." % self.realm_all)
                continue

            #  - default hostgroup
            if r_name == 'hostgroup' and item[id_name] == "All":
                print ("-> do not change anything for default hostgroup.")
                continue

            #  - default servicegroup
            if r_name == 'servicegroup' and item[id_name] == "All":
                print ("-> do not change anything for default servicegroup.")
                continue

            #  - default usergroup
            if r_name == 'usergroup' and item['contactgroup_name'] == "All":
                print ("-> do not change anything for default usergroup.")
                continue

            #  - specific commands
            if r_name == 'command' and item[id_name] in ['bp_rule', '_internal_host_up', '_echo']:
                print ("-> do not import this command.")
                continue

            # Update specific values for timeperiods...
            # ------------------------------------------------------------
            # Special case of timeperiods (except maintenance_period and snapshot_period)
            for tp_name in ['host_notification_period', 'service_notification_period',
                            'check_period', 'notification_period',
                            'escalation_period', 'dependency_period']:
                if tp_name not in item:
                    continue

                if not item[tp_name]:
                    # Default is always
                    item[tp_name] = self.tp_always
                    continue

                if item[tp_name].lower() == '24x7':
                    item[tp_name] = self.tp_always
                    continue

                if item[tp_name].lower() == 'never' or item[tp_name].lower() == 'none':
                    item[tp_name] = self.tp_never
                    continue

                if item[tp_name] in timeperiods and \
                   timeperiods[item[tp_name]] and \
                   timeperiods[item[tp_name]].timeperiod_name.lower() == '24x7':
                    item[tp_name] = self.tp_always

            # Convert objects
            # ------------------------------------------------------------
            item = self.convert_objects(item)
            # Remove properties
            prop_to_del = []
            for prop in item:
                if item[prop] is None:
                    prop_to_del.append(prop)
                elif prop == 'register':
                    prop_to_del.append(prop)
                elif prop == '_id':
                    prop_to_del.append(prop)
                elif prop == 'imported_from':
                    prop_to_del.append(prop)
                elif prop == 'invalid_entries':
                    prop_to_del.append(prop)
                elif prop == 'activated_once':
                    prop_to_del.append(prop)
                elif prop == 'unresolved':
                    prop_to_del.append(prop)

                # case we have [''], rewrite it to []
                elif isinstance(item[prop], list) and len(item[prop]) == 1 and item[prop][0] == '':
                    del item[prop][0]
            for prop in prop_to_del:
                del item[prop]

            later_tmp = {}

            # Special process for realms
            if r_name == 'realm':
                print(" --> realm: %s - %s" % (id_name, item))

                if 'definition_order' in item:
                    # Remove this field
                    item.pop('definition_order')

                if item['name'] == 'All' or item['name'] == 'Default':
                    # Default Alignak realm is same as our All realm
                    self.default_realm = item['uuid']

                if 'realm_members' in item:
                    print(" --> Drop realm members for %s: %s" % (
                        item[id_name], item['realm_members']
                    ))
                    item.pop('realm_members')

                if 'higher_realms' in item:
                    print(" --> Higher realms for %s: %s" % (item[id_name], item['higher_realms']))
                    if not item['higher_realms']:
                        # Link to default All backend realm
                        item['_parent'] = self.realm_all
                    else:
                        # Link to first higher realm
                        item['_parent'] = item['higher_realms'][0]
                    item.pop('higher_realms')

                if item['_parent'] == self.default_realm:
                    item['_parent'] = self.realm_all

                if 'broker_complete_links' in item:
                    item.pop('broker_complete_links')
                print(" --> realm(modified): %s" % item)
            else:
                # Default is to set element in the default realm
                item['_realm'] = self.realm_all

                # Realms related to other elements...
                if 'realm' in item:
                    if r_name in ['hostgroup', 'host']:
                        print(" --> %s, realm: %s" % (r_name, item['realm']))

                        if item['realm'] == self.default_realm or not item['realm']:
                            item['_realm'] = self.realm_all
                        else:
                            item['_realm'] = item['realm']

                    if r_name in ['servicegroup', 'service']:
                        print(" --> %s, realm: %s" % (r_name, item['realm']))

                        if item['realm'] == self.default_realm or not item['realm']:
                            item['_realm'] = self.realm_all
                        else:
                            item['_realm'] = item['realm']
                    item.pop('realm', None)

                if item['_realm'] == self.realm_all:
                    item['_sub_realm'] = True

            # Special process for custom variables
            # Only import element custom variables if schema allows unknown fields ...
            # ... not the best solution. They should be imported in 'customs' defined array field!
            if 'customs' in schema['schema']:
                item['customs'] = item_obj.customs
            elif 'allow_unknown' in schema and schema['allow_unknown']:
                for prop in item_obj.customs.keys():
                    item[prop] = item_obj.customs[prop]

            # Special case of hostdependency
            if r_name == 'hostdependency':
                if 'host_name' in item:
                    item['hosts'] = item['host_name']
                    item.pop('host_name')
                if 'dependent_host_name' in item:
                    item['dependent_hosts'] = item['dependent_host_name']
                    item.pop('dependent_host_name')
                if 'hostgroup_name' in item:
                    item['hostgroups'] = item['hostgroup_name']
                    item.pop('hostgroup_name')
                if 'dependent_hostgroup_name' in item:
                    item['dependent_hostgroups'] = item['dependent_hostgroup_name']
                    item.pop('dependent_hostgroup_name')

                if 'dependency_period' not in item or not item['dependency_period']:
                    item['dependency_period'] = self.tp_always

            # Special case of servicedependency
            if r_name == 'servicedependency':
                if 'host_name' in item:
                    item['hosts'] = item['host_name']
                    item.pop('host_name')
                if 'service_description' in item:
                    item['services'] = item['service_description']
                    item.pop('service_description')
                if 'dependent_host_name' in item:
                    item['dependent_hosts'] = item['dependent_host_name']
                    item.pop('dependent_host_name')
                if 'dependent_service_description' in item:
                    item['dependent_services'] = item['dependent_service_description']
                    item.pop('dependent_service_description')
                if 'hostgroup_name' in item:
                    item['hostgroups'] = item['hostgroup_name']
                    item.pop('hostgroup_name')
                if 'dependent_hostgroup_name' in item:
                    item['dependent_hostgroups'] = item['dependent_hostgroup_name']
                    item.pop('dependent_hostgroup_name')

                if 'dependency_period' not in item or not item['dependency_period']:
                    item['dependency_period'] = self.tp_always

            # Special case of hostgroups
            if r_name == 'hostgroup':
                if 'members' in item:
                    item['hosts'] = item['members']
                    item.pop('members')
                if 'hostgroup_members' in item:
                    item['hostgroups'] = item['hostgroup_members']
                    item.pop('hostgroup_members')

            # Special case of hosts
            if r_name == 'host':
                if self.models and item_obj.is_tpl():
                    item['_is_template'] = True
                    if 'check_command' not in item:
                        item['check_command'] = ''

                if 'hostgroups' in item:
                    # Remove hostgroups relations ... still useful?
                    if item['hostgroups']:
                        print(" --> remove hostgroups relation: %s" % (item['hostgroups']))
                    item.pop('hostgroups')
                if 'trigger_name' in item:
                    item['trigger'] = item['trigger_name']
                    item.pop('trigger_name')

                # Define location as default: France circle center ;))
                item['location'] = deepcopy(self.gps)
                if item['customs'] and '_LOC_LAT' in item['customs']:
                    item['location']['coordinates'][0] = float(item['customs']['_LOC_LAT'])
                if 'customs' in item and '_LOC_LNG' in item['customs']:
                    item['location']['coordinates'][1] = float(item['customs']['_LOC_LNG'])

            # Special case of servicegroups
            if r_name == 'servicegroup':
                if 'members' in item:
                    item['services'] = item['members']
                    item.pop('members')
                if 'servicegroup_members' in item:
                    item['servicegroups'] = item['servicegroup_members']
                    item.pop('servicegroup_members')

            # Special case of services
            if r_name == 'service':
                if self.models and item_obj.is_tpl():
                    print("Service is a template ...")
                    item['_is_template'] = True
                    item['host'] = ''
                    if 'check_command' not in item:
                        item['check_command'] = ''
                    if 'service_description' not in item:
                        item['service_description'] = item['name']

                if 'servicegroups' in item:
                    # Remove servicegroups relations ... still useful?
                    if item['servicegroups']:
                        print(" --> %s, servicegroups: %s" % (
                            item[id_name], item['servicegroups']
                        ))
                    item.pop('servicegroups')
                if 'trigger_name' in item:
                    item['trigger'] = item['trigger_name']
                    item.pop('trigger_name')
                if 'merge_host_contacts' in item:
                    item.pop('merge_host_contacts')

                if 'host_name' in item:
                    item['host'] = item['host_name']
                    item.pop('host_name')
                else:
                    item['host'] = self.dummy_host
                print("Service host/description: %s/%s" %
                      (item['host'], item['service_description']))

                if 'hostgroup_name' in item:
                    item['hostgroups'] = item['hostgroup_name']
                    item.pop('hostgroup_name')

            # Special case of usergroups
            if r_name == 'usergroup':
                if 'members' in item:
                    item['users'] = item['members']
                    item.pop('members')
                if 'contactgroup_name' in item:
                    # Remove contactgroup_name, replaced with name...
                    item.pop('contactgroup_name')
                if 'contactgroup_members' in item:
                    item['usergroups'] = item['contactgroup_members']
                    item.pop('contactgroup_members')

            # Special case of users
            if r_name == 'user':
                item['ui_preferences'] = {}
                item.pop('usergroups')
                item.pop('expert')
                # Waiting for manage the notification ways in the backend
                # Delete (temporarily...) this property
                item.pop('notificationways')

                if 'contact_name' in item:
                    item['name'] = item[id_name]
                    if item['contact_name'] == 'admin':
                        print ("-> import user 'admin' renamed as 'imported_admin'.")
                        item['name'] = 'imported_admin'

                    # Remove contact_name, replaced with name...
                    item.pop('contact_name')

                if 'host_notification_period' not in item or \
                   not item['host_notification_period']:
                    item['host_notification_period'] = self.tp_always

                if 'service_notification_period' not in item or \
                   not item['service_notification_period']:
                    item['service_notification_period'] = self.tp_always

                if 'address6' in item:
                    if item['address6'] in self.inserted['realm']:
                        item['_realm'] = self.inserted['realm'][item['address6']]
                        print("-> import user '%s' in realm '%s'." % (
                            item['name'], item['address6']
                        ))
                    if item['address6'] in self.inserted['realm'].values():
                        index = self.inserted['realm'].values().index(item['address6'])
                        item['_realm'] = self.inserted['realm'].keys()[index]
                        print("-> import user '%s' in realm '%s'." % (
                            item['name'], item['address6']
                        ))

            # Special case of timeperiods for hosts and services
            # Always define timeperiods if they do not exist
            if r_name == 'host' or r_name == 'service':
                # Always check and notify...
                if 'check_period' not in item or \
                   not item['check_period']:
                    item['check_period'] = self.tp_always

                if 'notification_period' not in item or \
                   not item['notification_period']:
                    item['notification_period'] = self.tp_always

                # Never maintenance and snapshot...
                if 'maintenance_period' not in item or \
                   not item['maintenance_period']:
                    item['maintenance_period'] = self.tp_never

                if 'snapshot_period' not in item or \
                   not item['snapshot_period']:
                    item['snapshot_period'] = self.tp_never

            # Hack for check_command_args
            if 'check_command_args' in item and isinstance(item['check_command_args'], list):
                item['check_command_args'] = '!'.join(item['check_command_args'])

            self.log("Creating links with other objects (data_later)")
            for dummy, values in enumerate(data_later):

                if values['field'] in item \
                        and values['type'] == 'simple':
                    if values['now'] and \
                       values['resource'] in self.inserted and \
                       item[values['field']] in self.inserted[values['resource']]:
                        # Link is still existing and should be valid... do nothing, except logging.
                        self.log("***Found: %s = %s" % (values['field'], item[values['field']]))

                    elif item[values['field']] in self.inserted[values['resource']].values():
                        index = self.inserted[values['resource']].values().index(
                            item[values['field']]
                        )
                        item[values['field']] = self.inserted[values['resource']].keys()[index]

                    elif item[values['field']] in self.inserted_uuid[values['resource']].values():
                        idx = self.inserted_uuid[values['resource']].values().index(
                            item[values['field']]
                        )
                        item[values['field']] = self.inserted_uuid[values['resource']].keys()[idx]

                    else:
                        later_tmp[values['field']] = item[values['field']]
                        del item[values['field']]

                elif values['field'] in item \
                        and values['type'] == 'list' \
                        and values['now']:
                    add = True
                    objectsid = []

                    if isinstance(item[values['field']], basestring):
                        item[values['field']] = item[values['field']].split()

                    for dummy, vallist in enumerate(item[values['field']]):
                        if not vallist:
                            continue
                        if hasattr(vallist, 'strip'):
                            vallist = vallist.strip()

                        if values['resource'] in self.inserted and \
                                vallist in self.inserted[values['resource']]:
                            objectsid.append(vallist)
                        elif values['resource'] in self.inserted and \
                                vallist in self.inserted[values['resource']].values():
                            index = self.inserted[values['resource']].values().index(vallist)
                            objectsid.append(self.inserted[values['resource']].keys()[index])
                        elif values['resource'] in self.inserted_uuid and \
                                vallist in self.inserted_uuid[values['resource']].values():
                            idx = self.inserted_uuid[values['resource']].values().index(
                                vallist
                            )
                            objectsid.append(self.inserted_uuid[values['resource']].keys()[
                                idx])
                        else:
                            add = False
                    if add:
                        item[values['field']] = objectsid
                    else:
                        later_tmp[values['field']] = item[values['field']]
                        del item[values['field']]

                elif values['field'] in item \
                        and values['type'] == 'list' \
                        and not values['now']:
                    later_tmp[values['field']] = item[values['field']]
                    del item[values['field']]

            # hostdependency - set name once relations are resolved
            if r_name == 'hostdependency':
                if 'name' not in item or not item['name']:
                    host_name = ''
                    if item['hosts']:
                        host_name = item['hosts'][0]
                        if host_name in self.inserted['host']:
                            host_name = self.inserted['host'][host_name]
                    dependent_host_name = ''
                    if item['hosts']:
                        dependent_host_name = item['dependent_hosts'][0]
                        if dependent_host_name in self.inserted['host']:
                            dependent_host_name = self.inserted['host'][dependent_host_name]
                    item['name'] = "%s -> %s" % (host_name, dependent_host_name)

            if r_name == 'servicedependency':
                if 'name' not in item or not item['name']:
                    host_name = ''
                    if item['hosts']:
                        host_name = item['hosts'][0]
                        if host_name in self.inserted['host']:
                            host_name = self.inserted['host'][host_name]
                    dependent_host_name = ''
                    if item['dependent_hosts']:
                        dependent_host_name = item['dependent_hosts'][0]
                        if dependent_host_name in self.inserted['host']:
                            dependent_host_name = self.inserted['host'][dependent_host_name]

                    service_name = ''
                    if item['services']:
                        service_name = item['services'][0]
                        if service_name in self.inserted['service']:
                            service_name = self.inserted['service'][service_name]
                    dependent_service = ''
                    if item['dependent_services']:
                        dependent_service = item['dependent_services'][0]
                        if dependent_service in self.inserted['service']:
                            dependent_service = self.inserted['service'][dependent_service]

                    item['name'] = "%s/%s -> %s/%s" % (
                        host_name, service_name, dependent_host_name, dependent_service
                    )

            # Remove unused fields
            # ------------------------------------------------------------
            # - Shinken template link...
            if 'use' in item:
                # As of #95 in the alignak-backend, interesting to get used as tags ...
                if item['use'] and r_name in ['host', 'service', 'contact']:
                    item['tags'] = item['use']
                    print("Set item 'tags' as: %s" % item['tags'])
                self.log("removed 'use' field from: %s : %s:" % (r_name, item))
                item.pop('use')

            # - Alignak uuid...
            if 'uuid' in item:
                # Commented because too verbose !
                # self.log("removed 'uuid' field from: %s : %s:" % (r_name, item))
                item.pop('uuid')

            # - 'unknown_members'
            if 'unknown_members' in item:
                self.log("removed 'unknown_members' field from: %s : %s:" % (r_name, item))
                item.pop('unknown_members')

            # Elements common fields
            # ------------------------------------------------------------
            # - 'imported_from' with this script ...
            item['imported_from'] = 'alignak_backend_import'

            # item['_id']       auto generated by the backend

            # item['name']      ok
            if id_name != 'name':
                print(" --> id_name: %s" % (id_name))
                if id_name not in item and 'name' not in item:
                    print(" --> not named item: %s" % (item))
                    exit(6)
                # if 'name' not in item or not item[id_name]:
                item['name'] = item[id_name]
                item.pop(id_name)
                print(" --> replaced name for %s: %s" % (r_name, item['name']))
                if '$' in item['name']:
                    item['name'] = item['name'].replace('$', '_')
                    print(" --> replaced name for %s: %s" % (r_name, item['name']))

            # item['alias']     not always included, what to do?
            # item['comment']   never included, what to do?

            self.log("before_post: %s : %s:" % (r_name, item))
            if self.allow_duplicates:
                # Check if element still exists in the backend
                print("Checking element existence for %s: %s" % (r_name, item['name']))
                params = {'where': json.dumps({'name': item['name']})}
                if r_name == 'service':
                    params = {'where': json.dumps({
                        'name': item['name'],
                        'host': item['host']
                    })}
                response = self.backend.get(r_name, params=params)
                if len(response['_items']) > 0:
                    # Still exists in the backend, log and continue...
                    if r_name not in self.ignored:
                        self.ignored[r_name] = {}
                    self.ignored[r_name][item['name']] = item
                    continue

            try:
                # Special case for templates ... some have check_command some do not have!
                if template:
                    if 'check_command' not in item:
                        item['check_command'] = ''

                if self.update_backend_data:
                    print("Updating %s: %s" % (r_name, item['name']))
                    params = {'where': json.dumps({'name': item['name']})}
                    if r_name == 'service':
                        params = {'where': json.dumps({
                            'name': item['name'],
                            'host': item['host']
                        })}
                    response = self.backend.get(r_name, params=params)
                    if len(response['_items']) > 0:
                        # Exists in the backend, we can update...
                        headers = {
                            'Content-Type': 'application/json',
                            'If-Match': response['_items'][0]['_etag']
                        }
                        self.backend.patch(
                            r_name + '/' + response['_items'][0]['_id'], item,
                            headers=headers, inception=True
                        )
                        print("Updated %s: %s" % (r_name, item['name']))
                        continue
                else:
                    # With headers=None, the post method manages correctly the posted data ...
                    response = self.backend.post(r_name, item, headers=None)
                    if '_is_template' in item and item['_is_template']:
                        print("-> Created a new: %s template: %s (%s)" % (
                            r_name, item['name'], response['_id']
                        ))
                    else:
                        print("-> Created a new: %s : %s (%s) (%s)" % (
                            r_name, item['name'], response['_id'], item_obj.uuid
                        ))
            except BackendException as e:
                print("# Post/patch error for: %s : %s" % (r_name, item))
                print("***** Exception: %s" % str(e))
                print("***** %s", traceback.format_exc())
                print("***** response: %s" % e.response)
                print("~~~~~~~~~~~~~~~~~~~~~~~~~~")
                print("Exiting with error code: 5")
                # Response is formed as a dictionary: {
                # u'_status': u'ERR',
                # u'_issues': {
                #   u'notification_options': u"unallowed values [u'n']"
                # },
                # u'_error': {
                #   u'message': u'Insertion failure: 1 document(s) contain(s) error(s)',
                #   u'code': 422
                # }
                # }
                exit(5)
            else:
                self.log("Element insertion response : %s:" % response)
                if template:
                    self.inserted['%s_template' % r_name][response['_id']] = item['name']
                self.inserted[r_name][response['_id']] = item['name']
                self.inserted_uuid[r_name][response['_id']] = item_obj.uuid

                for dummy, values in enumerate(data_later):
                    if values['field'] in later_tmp:
                        print("***Update later: %s/%s, with %s = %s" % (
                            r_name, response['_id'], values['field'], later_tmp[values['field']]
                        ))
                        self.later[r_name][values['field']][response['_id']] = {
                            'type': values['type'],
                            'resource': values['resource'],
                            'value': later_tmp[values['field']],
                            '_etag': response['_etag']
                        }

                # Special case of users - create user restriction roles in the backend
                if r_name == 'user':
                    try:
                        # Default is to allow read on all elements of the user's realm
                        user_role = {
                            'user': response['_id'],
                            'realm': item['_realm'],
                            'sub_realm': True,
                            'resource': '*',
                            'crud': ['read']
                        }
                        response = self.backend.post('userrestrictrole', user_role, headers=None)
                        print("-> Created a new user_role: %s : %s (%s)" % (
                            r_name, user_role, response['_id']
                        ))
                    except BackendException as e:
                        print("# Post error for user_role: %s : %s" % (r_name, item))
                        print("***** Exception: %s" % str(e))
                        print("***** %s", traceback.format_exc())
                        print("***** response: %s" % e.response)
                        print("~~~~~~~~~~~~~~~~~~~~~~~~~~")
                        print("Exiting with error code: 5")
                        exit(5)

    def import_objects(self):
        """
        Import objects in the backend

        :return: None
        """
        print("~~~~~~~~~~~~~~~~~~~~~~ add realm ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        data_later = [
            {
                'field': '_parent', 'type': 'simple',
                'resource': 'realm', 'now': True
            }
        ]
        schema = realm.get_schema()
        self.manage_resource('realm', data_later, 'realm_name', schema)
        print("~~~~~~~~~~~~~~~~~~~~~~ post realms ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        self.update_later('realm', '_parent')

        print("~~~~~~~~~~~~~~~~~~~~~~ add commands ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        data_later = []
        schema = command.get_schema()
        self.manage_resource('command', data_later, 'command_name', schema)

        print("~~~~~~~~~~~~~~~~~~~~~~ add timeperiods ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        data_later = []
        schema = timeperiod.get_schema()
        self.manage_resource('timeperiod', data_later, 'timeperiod_name', schema)

        # ------------------------------
        # User part
        # ------------------------------
        print("~~~~~~~~~~~~~~~~~~~~~~ add user ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        data_later = [
            {
                'field': 'host_notification_period', 'type': 'simple',
                'resource': 'timeperiod', 'now': True
            },
            {
                'field': 'service_notification_period', 'type': 'simple',
                'resource': 'timeperiod', 'now': True
            },
            {
                'field': 'host_notification_commands', 'type': 'list',
                'resource': 'command', 'now': True
            },
            {
                'field': 'service_notification_commands', 'type': 'list',
                'resource': 'command', 'now': True
            }
        ]
        schema = user.get_schema()
        self.manage_resource('user', data_later, 'name', schema)

        print("~~~~~~~~~~~~~~~~~~~~~~ add usergroup ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        data_later = [
            {
                'field': '_parent', 'type': 'simple',
                'resource': 'usergroup', 'now': True
            },
            {
                'field': 'usergroups', 'type': 'list',
                'resource': 'usergroup', 'now': False
            },
            {
                'field': 'users', 'type': 'list',
                'resource': 'user', 'now': True
            }
        ]
        schema = usergroup.get_schema()
        self.manage_resource('usergroup', data_later, 'name', schema)
        print("~~~~~~~~~~~~~~~~~~~~~~ post usergroup ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        self.update_later('usergroup', '_parent')
        self.update_later('usergroup', 'usergroups')

        # ------------------------------
        # Host part
        # ------------------------------
        print("~~~~~~~~~~~~~~~~~~~~~~ add host ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        data_later = [
            {
                'field': 'parents', 'type': 'list',
                'resource': 'host', 'now': False
            },
            {
                'field': '_realm', 'type': 'simple',
                'resource': 'realm', 'now': True
            },
            {
                'field': 'check_command', 'type': 'simple',
                'resource': 'command', 'now': True
            },
            {
                'field': 'event_handler', 'type': 'simple',
                'resource': 'command', 'now': True
            },
            {
                'field': 'check_period', 'type': 'simple',
                'resource': 'timeperiod', 'now': True
            },
            {
                'field': 'users', 'type': 'list',
                'resource': 'user', 'now': True
            },
            {
                'field': 'usergroups', 'type': 'list',
                'resource': 'usergroup', 'now': True
            },
            {
                'field': 'notification_period', 'type': 'simple',
                'resource': 'timeperiod', 'now': True
            },
            {
                'field': 'escalations', 'type': 'list',
                'resource': 'escalation', 'now': True
            },
            {
                'field': 'maintenance_period', 'type': 'simple',
                'resource': 'timeperiod', 'now': True
            },
            {
                'field': 'snapshot_period', 'type': 'simple',
                'resource': 'timeperiod', 'now': True
            }
        ]
        schema = host.get_schema()
        self.manage_resource('host', data_later, 'host_name', schema)
        print("~~~~~~~~~~~~~~~~~~~~~~ post host ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        self.update_later('host', 'parents')

        if self.models:
            print("~~~~~~~~~~~~~~~~~~~~~~ add host templates ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = [
                {
                    'field': 'parents', 'type': 'list',
                    'resource': 'host', 'now': False
                },
                {
                    'field': '_realm', 'type': 'simple',
                    'resource': 'realm', 'now': True
                },
                {
                    'field': 'hostgroups', 'type': 'list',
                    'resource': 'hostgroup', 'now': True
                },
                {
                    'field': 'check_command', 'type': 'simple',
                    'resource': 'command', 'now': True
                },
                {
                    'field': 'event_handler', 'type': 'simple',
                    'resource': 'command', 'now': True
                },
                {
                    'field': 'check_period', 'type': 'simple',
                    'resource': 'timeperiod', 'now': True
                },
                {
                    'field': 'users', 'type': 'list',
                    'resource': 'user', 'now': True
                },
                {
                    'field': 'usergroups', 'type': 'list',
                    'resource': 'usergroup', 'now': True
                },
                {
                    'field': 'notification_period', 'type': 'simple',
                    'resource': 'timeperiod', 'now': True
                },
                {
                    'field': 'escalations', 'type': 'list',
                    'resource': 'escalation', 'now': True
                },
                {
                    'field': 'maintenance_period', 'type': 'simple',
                    'resource': 'timeperiod', 'now': True
                },
                {
                    'field': 'snapshot_period', 'type': 'simple',
                    'resource': 'timeperiod', 'now': True
                }
            ]
            schema = host.get_schema()
            # Import hosts templates
            self.manage_resource('host', data_later, 'name', schema, template=True)
            print("~~~~~~~~~~~~~~~~~~~~~~ post host templates ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            self.update_later('host', 'parents')

        print("~~~~~~~~~~~~~~~~~~~~~~ add hostdependency ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        data_later = [
            {
                'field': 'hosts', 'type': 'list',
                'resource': 'host', 'now': True
            },
            {
                'field': 'dependent_hosts', 'type': 'list',
                'resource': 'host', 'now': True
            },
            {
                'field': 'hostgroups', 'type': 'list',
                'resource': 'hostgroup', 'now': True
            },
            {
                'field': 'dependent_hostgroups', 'type': 'list',
                'resource': 'hostgroup', 'now': True
            },
            {
                'field': 'dependency_period', 'type': 'simple',
                'resource': 'timeperiod', 'now': True
            }
        ]
        schema = hostdependency.get_schema()
        self.manage_resource('hostdependency', data_later, 'name', schema)

        print("~~~~~~~~~~~~~~~~~~~~~~ add hostgroups ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        data_later = [
            {
                'field': '_parent', 'type': 'simple',
                'resource': 'hostgroup', 'now': True
            },
            {
                'field': '_realm', 'type': 'simple',
                'resource': 'realm', 'now': True
            },
            {
                'field': 'hostgroups', 'type': 'list',
                'resource': 'hostgroup', 'now': False
            },
            {
                'field': 'hosts', 'type': 'list',
                'resource': 'host', 'now': True
            }
        ]
        schema = hostgroup.get_schema()
        self.manage_resource('hostgroup', data_later, 'hostgroup_name', schema)
        print("~~~~~~~~~~~~~~~~~~~~~~ post hostgroups ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        self.update_later('hostgroup', '_parent')
        self.update_later('hostgroup', 'hostgroups')

        print("~~~~~~~~~~~~~~~~~~~~~~ add hostescalation ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        data_later = [
            {
                'field': 'users', 'type': 'list',
                'resource': 'user', 'now': True
            },
            {
                'field': 'usergroups', 'type': 'list',
                'resource': 'usergroup', 'now': True
            }
        ]
        schema = hostescalation.get_schema()
        self.manage_resource('hostescalation', data_later, 'host', schema)

        # ------------------------------
        # Service part
        # ------------------------------
        print("~~~~~~~~~~~~~~~~~~~~~~ add service ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        data_later = [
            {
                'field': 'host', 'type': 'simple',
                'resource': 'host', 'now': True
            },
            {
                'field': '_realm', 'type': 'simple',
                'resource': 'realm', 'now': True
            },
            {
                'field': 'servicegroups', 'type': 'list',
                'resource': 'servicegroup', 'now': True
            },
            {
                'field': 'hostgroups', 'type': 'list',
                'resource': 'hostgroup', 'now': True
            },
            {
                'field': 'check_command', 'type': 'simple',
                'resource': 'command', 'now': True
            },
            {
                'field': 'event_handler', 'type': 'simple',
                'resource': 'command', 'now': True
            },
            {
                'field': 'check_period', 'type': 'simple',
                'resource': 'timeperiod', 'now': True
            },
            {
                'field': 'notification_period', 'type': 'simple',
                'resource': 'timeperiod', 'now': True
            },
            {
                'field': 'users', 'type': 'list',
                'resource': 'user', 'now': True
            },
            {
                'field': 'usergroups', 'type': 'list',
                'resource': 'usergroup',
                'now': True
            },
            {
                'field': 'escalations', 'type': 'list',
                'resource': 'escalation', 'now': True
            },
            {
                'field': 'maintenance_period', 'type': 'simple',
                'resource': 'timeperiod', 'now': True
            },
            {
                'field': 'snapshot_period', 'type': 'simple',
                'resource': 'timeperiod', 'now': True
            },
            {
                'field': 'service_dependencies', 'type': 'list',
                'resource': 'service', 'now': True
            }
        ]
        schema = service.get_schema()
        self.manage_resource('service', data_later, 'service_description', schema)
        print("~~~~~~~~~~~~~~~~~~~~~~ post service ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")

        if self.models:
            print("~~~~~~~~~~~~~~~~~~~~~~ add service templates ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = [
                {
                    'field': 'host', 'type': 'simple',
                    'resource': 'host', 'now': True
                },
                {
                    'field': '_realm', 'type': 'simple',
                    'resource': 'realm', 'now': True
                },
                {
                    'field': 'servicegroups', 'type': 'list',
                    'resource': 'servicegroup', 'now': True
                },
                {
                    'field': 'check_command', 'type': 'simple',
                    'resource': 'command', 'now': True
                },
                {
                    'field': 'event_handler', 'type': 'simple',
                    'resource': 'command', 'now': True
                },
                {
                    'field': 'check_period', 'type': 'simple',
                    'resource': 'timeperiod', 'now': True
                },
                {
                    'field': 'notification_period', 'type': 'simple',
                    'resource': 'timeperiod', 'now': True
                },
                {
                    'field': 'users', 'type': 'list',
                    'resource': 'user', 'now': True
                },
                {
                    'field': 'usergroups', 'type': 'list',
                    'resource': 'usergroup',
                    'now': True
                },
                {
                    'field': 'escalations', 'type': 'list',
                    'resource': 'escalation', 'now': True
                },
                {
                    'field': 'maintenance_period', 'type': 'simple',
                    'resource': 'timeperiod', 'now': True
                },
                {
                    'field': 'snapshot_period', 'type': 'simple',
                    'resource': 'timeperiod', 'now': True
                },
                {
                    'field': 'service_dependencies', 'type': 'list',
                    'resource': 'service', 'now': True
                }
            ]
            schema = service.get_schema()
            self.manage_resource(
                'service', data_later, 'service_description', schema, template=True
            )
            print("~~~~~~~~~~~~~~~~~~~~~~ post service templates ~~~~~~~~~~~~~~~~~~~~~~~~~~~~")

        print("~~~~~~~~~~~~~~~~~~~~~~ add servicedependency ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        data_later = [
            {
                'field': 'hosts', 'type': 'list',
                'resource': 'host', 'now': True
            },
            {
                'field': 'services', 'type': 'list',
                'resource': 'service', 'now': True
            },
            {
                'field': 'dependent_hosts', 'type': 'list',
                'resource': 'host', 'now': True
            },
            {
                'field': 'dependent_services', 'type': 'list',
                'resource': 'service', 'now': True
            },
            {
                'field': 'hostgroups', 'type': 'list',
                'resource': 'hostgroup', 'now': True
            },
            {
                'field': 'dependent_hostgroups', 'type': 'list',
                'resource': 'hostgroup', 'now': True
            },
            {
                'field': 'dependency_period', 'type': 'simple',
                'resource': 'timeperiod', 'now': True
            }
        ]
        schema = servicedependency.get_schema()
        self.manage_resource('servicedependency', data_later, 'name', schema)

        print("~~~~~~~~~~~~~~~~~~~~~~ add servicegroup ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        data_later = [
            {
                'field': '_parent', 'type': 'simple',
                'resource': 'servicegroup', 'now': True
            },
            {
                'field': 'servicegroups', 'type': 'list',
                'resource': 'servicegroup', 'now': False
            },
            {
                'field': 'services', 'type': 'list',
                'resource': 'service', 'now': True
            }
        ]
        schema = servicegroup.get_schema()
        self.manage_resource('servicegroup', data_later, 'servicegroup_name', schema)
        print("~~~~~~~~~~~~~~~~~~~~~~ post servicegroup ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        self.update_later('servicegroup', '_parent')
        self.update_later('servicegroup', 'servicegroups')

        print("~~~~~~~~~~~~~~~~~~~~~~ add serviceescalation ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        data_later = [
            {
                'field': 'users', 'type': 'list',
                'resource': 'user', 'now': True
            },
            {
                'field': 'usergroups', 'type': 'list',
                'resource': 'usergroup', 'now': True
            }
        ]
        schema = serviceescalation.get_schema()
        self.manage_resource('serviceescalation', data_later, 'host', schema)

    def log(self, message):
        """
        Display message if in verbose mode

        :param message: message to display
        :type message: str
        :return: None
        """
        if self.verbose:
            print(message)


def main():
    """
    Main function
    """
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    print("alignak_backend_import, version: %s" % __version__)
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    fill = CfgToBackend()
    if not fill.result:
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        print("alignak_backend_import, some problems were encountered during importation")
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        print("Exiting with error code: 4")
        exit(4)
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    print("alignak_backend_import, inserted elements: ")
    for object_type in sorted(fill.inserted):
        count = len(fill.inserted[object_type])
        if '%s_template' % object_type in fill.inserted:
            count = count - len(fill.inserted['%s_template' % object_type])
        if count:
            print(" - %s %s(s)" % (count, object_type))
        else:
            print(" - no %s(s)" % object_type)
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    print("alignak_backend_import, ignored elements: ")
    for object_type in sorted(fill.ignored):
        count = len(fill.ignored[object_type])
        if '%s_template' % object_type in fill.ignored:
            count = count - len(fill.ignored['%s_template' % object_type])
        if count:
            print(" - %s %s(s)" % (count, object_type))
        else:
            print(" - no %s(s)" % object_type)
        for elt in sorted(fill.ignored[object_type]):
            print("%s: %s" % (object_type, fill.ignored[object_type][elt]))
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")

if __name__ == "__main__":  # pragma: no cover
    main()
