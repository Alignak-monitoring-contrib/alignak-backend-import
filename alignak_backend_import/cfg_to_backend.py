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
        {command} [-h] [-v] [-d] [-b=url] [-u=username] [-p=password] [-t=type] [<cfg_file>...]

    Options:
        -h, --help                  Show this screen.
        -V, --version               Show application version.
        -b, --backend url           Specify backend URL [default: http://127.0.0.1:5000]
        -d, --delete                Delete existing backend data
        -u, --username username     Backend login username [default: admin]
        -p, --password password     Backend login password [default: admin]
        -v, --verbose               Run in verbose mode (more info to display)
        -t, --type type             Only manages this object type [default: all]

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

        Exit code:
            0 if required operation succeeded
            1 if Alignak is not installed on your system
            2 if backend access is denied (check provided username/password)
            3 if required configuration cannot be loaded by Alignak
            4 if some problems were encountered during backend importation
            5 if an exception occured when creating/updating data in the Alignak backend

            64 if command line parameters are not used correctly
"""
from __future__ import print_function
import re
import traceback

from logging import getLogger, DEBUG, INFO, WARNING

from docopt import docopt
from docopt import DocoptExit

from future.utils import iteritems

try:
    from alignak.daemons.arbiterdaemon import Arbiter
    from alignak.objects.item import Item
    from alignak.objects.config import Config
    import alignak.daterange as daterange
except ImportError:
    print("Alignak is not installed...")
    exit(1)

from alignak_backend_client.client import Backend, BackendException

from alignak_backend_import import __version__

from alignak_backend.models import realm
from alignak_backend.models import command
from alignak_backend.models import timeperiod
from alignak_backend.models import hostgroup
from alignak_backend.models import hostdependency
from alignak_backend.models import servicedependency
from alignak_backend.models import trigger
from alignak_backend.models import user
from alignak_backend.models import usergroup
from alignak_backend.models import userrestrictrole
from alignak_backend.models import host
from alignak_backend.models import hostescalation
from alignak_backend.models import servicegroup
from alignak_backend.models import service
from alignak_backend.models import serviceescalation

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
        self.default_tp = None

        # Get command line parameters
        try:
            args = docopt(__doc__, version=__version__)
        except DocoptExit:
            print("Command line parsing error")
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
        else:
            self.log("No configuration specified")

        # Define here the url of the backend
        self.backend_url = args['--backend']
        self.log("Backend URL: %s" % self.backend_url)

        # Delete all objects in backend ?
        self.destroy_backend_data = args['--delete']
        self.log("Delete existing backend data: %s" % self.destroy_backend_data)

        self.username = args['--username']
        self.password = args['--password']
        self.log("Backend login with credentials: %s/%s" % (self.username, self.password))

        self.type = 'all'
        if '--type' in args:
            self.type = args['--type']
        self.log("Managing objects of type: %s" % (self.type))

        # Authenticate on Backend
        self.authenticate()
        # Delete data in backend if asked in arguments
        self.delete_data()

        # get realm id
        self.realm_all = ''
        self.default_realm = ''
        realms = self.backend.get_all('realm')
        for r in realms['_items']:
            if r['name'] == 'All' and r['_level'] == 0:
                self.realm_all = r['_id']

        if not cfg:
            print("No configuration specified")
            exit(2)

        if not isinstance(cfg, list):
            cfg = [cfg]

        # Get flat files configuration
        try:
            self.arbiter = Arbiter(cfg, False, False, False, False, '')
            self.arbiter.load_config_file()

            # Load only conf file for timeperiod.dateranges
            alconf = Config()
            buf = alconf.read_config(cfg)
            self.raw_objects = alconf.read_config_buf(buf)

        except Exception as e:
            print("Configuration loading exception: %s" % str(e))
            exit(3)

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Order of objects + fields to update post add
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        #
        # COMMAND
        # TIMEPERIOD
        # HOSTGROUP
        #    hostgroup.hostgroups
        # HOSTDEPENDENCY
        # SERVICEDEPENDENCY
        # SERVICEEXTINFO
        # TRIGGER
        # USER
        # CONTACTGROUP
        #    user.usergroups / usergroup.usergroup_members
        # USERRESTRICTROLE
        # ESCALATION
        # HOST
        #    hostgroup.members / host.use / host.parents
        # HOSTEXTINFO
        # HOSTESCALATION
        # SERVICEGROUP
        #    servicegroup.servicegroups
        # SERVICE
        # SERVICEESCALATION
        #

        self.recompose_dateranges()
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
            exit(2)
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Authenticated ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")

    def delete_data(self):
        # pylint: disable=fixme
        """
        Delete data in backend

        :return: None
        """
        if not self.destroy_backend_data:
            return

        try:
            print("~~~~~~~~~~~~~~~~~~~~~~~~ Deleting existing backend data ~~~~~~~~~~~~~~~~~~~~~~")
            headers = {'Content-Type': 'application/json'}
            if self.type == 'command' or self.type == 'all':
                print("Deleting command")
                self.backend.delete('command', headers)
            if self.type == 'timeperiod' or self.type == 'all':
                print("Deleting timeperiods")
                timeperiods = self.backend.get_all('timeperiod')
                headers_tp = {'Content-Type': 'application/json'}
                for tp in timeperiods['_items']:
                    if tp['name'] == '24x7':
                        self.inserted['timeperiod'] = {}
                        self.inserted['timeperiod'][tp['_id']] = '24x7'
                        self.default_tp = tp['_id']
                    else:
                        print("Deleting timeperiod: %s" % tp['name'])
                        headers_tp['If-Match'] = tp['_etag']
                        self.backend.delete('timeperiod/' + tp['_id'], headers_tp)
            if self.type == 'hostgroup' or self.type == 'all':
                print("Deleting hostgroups")
                self.backend.delete('hostgroup', headers)
            if self.type == 'hostdependency' or self.type == 'all':
                print("Deleting hostdependencys")
                self.backend.delete('hostdependency', headers)
            if self.type == 'servicedependency' or self.type == 'all':
                print("Deleting servicedependencys")
                self.backend.delete('servicedependency', headers)
            if self.type == 'trigger' or self.type == 'all':
                print("Deleting triggers")
                self.backend.delete('trigger', headers)
            if self.type == 'user' or self.type == 'all':
                print("Deleting users")
                users = self.backend.get_all('user')
                headers_user = {'Content-Type': 'application/json'}
                for u in users['_items']:
                    if u['name'] == 'admin':
                        self.inserted['user'] = {}
                        self.inserted['user'][u['_id']] = 'admin'
                    else:
                        print("Deleting user: %s" % u['name'])
                        headers_user['If-Match'] = u['_etag']
                        self.backend.delete('user/' + u['_id'], headers_user)
            if self.type == 'realm' or self.type == 'all':
                print("Deleting realms")
                # Get realms in _level reverse order to be able to delete them ...
                realms = self.backend.get('realm', params={'sort': '-_level'})
                headers_realm = {'Content-Type': 'application/json'}
                for r in realms['_items']:
                    if r['name'] == 'All':
                        self.inserted['realm'] = {}
                        self.inserted['realm'][r['_id']] = 'All'
                    else:
                        print("Deleting realm: %s" % r['name'])
                        to_del = self.backend.get('realm/' + r['_id'])
                        headers_realm['If-Match'] = to_del['_etag']
                        self.backend.delete('realm/' + to_del['_id'], headers_realm)
            if self.type == 'usergroup' or self.type == 'all':
                print("Deleting usergroups")
                self.backend.delete('usergroup', headers)
            if self.type == 'userrestrictrole' or self.type == 'all':
                print("Deleting userrestrictroles")
                self.backend.delete('userrestrictrole', headers)
            if self.type == 'hostescalation' or self.type == 'all':
                print("Deleting hostescalations")
                self.backend.delete('hostescalation', headers)
            if self.type == 'host' or self.type == 'all':
                print("Deleting hosts")
                self.backend.delete('host', headers)
            if self.type == 'hostescalation' or self.type == 'all':
                print("Deleting hostescalations")
                self.backend.delete('hostescalation', headers)
            if self.type == 'servicegroup' or self.type == 'all':
                print("Deleting servicegroups")
                self.backend.delete('servicegroup', headers)
            if self.type == 'service' or self.type == 'all':
                print("Deleting services")
                self.backend.delete('service', headers)
            if self.type == 'serviceescalation' or self.type == 'all':
                print("Deleting serviceescalations")
                self.backend.delete('serviceescalation', headers)
            if self.type == 'livestate' or self.type == 'all':
                print("Deleting livestate")
                self.backend.delete('livestate', headers)
            if self.type == 'livesynthesis' or self.type == 'all':
                print("Deleting livesynthesis")
                self.backend.delete('livesynthesis', headers)
            if self.type == 'uipref' or self.type == 'all':
                print("Deleting uipref")
                self.backend.delete('uipref', headers)
            print("~~~~~~~~~~~~~~~~~~~~~~~~ Existing backend data destroyed ~~~~~~~~~~~~~~~~~~~~~")
        except BackendException as e:
            print("# Backend deletion error")
            print("***** Exception: %s" % str(e))
            print("***** Traceback: %s", traceback.format_exc())
            print("***** response: %s" % e.response)
            exit(5)

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
        for prop in source:
            if 'alignak.commandcall.CommandCall' in str(type(source[prop])):
                if prop == 'check_command':
                    addprop['check_command_args'] = getattr(source[prop], 'args')
                source[prop] = getattr(source[prop], 'command')

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
        # pylint: disable=too-many-nested-blocks
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

            try:
                endpoint = ''.join([resource, '/', index])
                self.log("before_patch: %s : %s:" % (endpoint, data))
                to_patch = self.backend.get(endpoint)
                headers['If-Match'] = to_patch['_etag']
                resp = self.backend.patch(endpoint, data, headers, True)
            except BackendException as e:
                print("# Patch error for: %s : %s" % (endpoint, data))
                print("***** Exception: %s" % str(e))
                print("***** Traceback: %s", traceback.format_exc())
                print("***** response: %s" % e.response)
                exit(5)
            else:
                if '_status' in resp:
                    if resp['_status'] == 'ERR':
                        raise ValueError(resp['_issues'])
                    elif resp['_status'] == 'OK':
                        for (ind, dummy) in iteritems(self.later[resource]):
                            if index in self.later[resource][ind]:
                                self.later[resource][ind][index]['_etag'] = resp['_etag']

    def manage_resource(self, r_name, data_later, id_name, schema):
        """
        data_later = [{'field': 'use', 'type': 'simple|list', 'resource': 'command'}]

        :param r_name: resource name
        :type r_name: str
        :param data_later:
        :param id_name:
        :param schema:
        :return:
        """
        # pylint: disable=too-many-locals
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

        # Alignak defined realms
        if self.default_realm == '':
            realms = getattr(self.arbiter.conf, 'realms')
            default_realm = realms.get_default()
            print ("Realms: %s, default: %s" % (realms, default_realm))
            self.default_realm = default_realm.uuid
            print ("*** Alignak default realm: %s (%s)" % (
                self.default_realm, default_realm.get_name()
            ))

        for item_obj in getattr(self.arbiter.conf, alignak_resource):
            item = {}

            self.log("...................................")
            self.log("Manage resource %s: %s (%s)" % (r_name, item_obj.uuid, item_obj.get_name()))
            print("...................................")
            print ("Manage resource %s: %s (%s)" % (r_name, item_obj.uuid, item_obj.get_name()))

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
            #  - admin user
            if r_name == 'user':
                if item[id_name] == "admin":
                    print ("-> do not change anything for admin user.")
                    continue
                if 'contact_name' in item and item['contact_name'] == 'admin':
                    print ("-> do not import another admin user.")
                    continue

            #  - default timeperiod
            if r_name == 'timeperiod' and item[id_name] == "24x7":
                print ("-> do not change anything for default timeperiod.")
                continue

            #  - default realm
            if r_name == 'realm' and item[id_name] == "All":
                print ("-> do not change anything for default realm.")
                continue

            #  - specific commands
            if r_name == 'command' and item[id_name] in ['bp_rule', '_internal_host_up', '_echo']:
                print ("-> do not import this command.")
                continue

            # Update specific values ...
            # ------------------------------------------------------------
            # Special case of timeperiods
            for tp_name in ['host_notification_period', 'service_notification_period',
                            'check_period', 'notification_period', 'maintenance_period',
                            'snapshot_period', 'escalation_period', 'dependency_period']:
                if tp_name not in item:
                    continue
                # print("TP for %s: %s = %s" % (r_name, tp_name, item[tp_name]))
                # if item[tp_name] in timeperiods:
                # print("TP is %s" % (timeperiods[item[tp_name]]))
                if item[tp_name] == '24x7':
                    # print("Changed TP: %s to default TP." % (tp_name))
                    item[tp_name] = self.default_tp
                    continue

                if timeperiods[item[tp_name]] and \
                   timeperiods[item[tp_name]].timeperiod_name == '24x7':
                    # print("Changed TP: %s to default TP." % (tp_name))
                    item[tp_name] = self.default_tp

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
                print(" --> realm(modified): %s" % (item))
            else:
                # Realms related to other elements...
                if 'realm' in item:
                    print(" --> %s, realm: %s" % (r_name, item['realm']))
                    # No realm for any element...
                    item.pop('realm', None)

                if r_name in ['host', 'hostgroup']:
                    item['realm'] = self.realm_all
                    item['hostgroups'] = []
                else:
                    item['_realm'] = self.realm_all

            # Special case of custom variables
            # Only import element custom variables if schema allows unknown fields ...
            # ... not the best solution. They should be imported in 'customs' defined array field!
            if 'customs' in schema['schema']:
                item['customs'] = item_obj.customs
            elif 'allow_unknown' in schema and schema['allow_unknown']:
                for prop in item_obj.customs.keys():
                    item[prop] = item_obj.customs[prop]

            # Special case of hostdependency / service
            if r_name == 'hostdependency':
                print("Host dependency: %s" % item)
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

            # Special case of hostgroups
            if r_name == 'hostgroup':
                if 'members' in item:
                    item['hosts'] = item['members']
                    item.pop('members')
                if 'hostgroup_members' in item:
                    item['hostgroups'] = item['hostgroup_members']
                    item.pop('hostgroup_members')
                print("Host group members: %s" % item['hosts'])

            # Special case of hosts
            if r_name == 'host':
                item.pop('hostgroups')
                item.pop('trigger_name')

                # Define location
                item['location'] = {"type": "Point", "coordinates": [100.0, 10.0]}

            # Special case of servicegroups
            if r_name == 'servicegroup':
                if 'members' in item:
                    item['services'] = item['members']
                    item.pop('members')
                    print("!!!!! #9: Do not import service group members: %s" % item['services'])
                    item.pop('services')
                if 'servicegroup_members' in item:
                    item['servicegroups'] = item['servicegroup_members']
                    item.pop('servicegroup_members')

            # Special case of services
            if r_name == 'service':
                item.pop('servicegroups')
                item.pop('trigger_name')
                item.pop('merge_host_contacts')

                if 'host_name' in item:
                    item['host'] = item['host_name']
                    item.pop('host_name')

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

            # Special case of users
            if r_name == 'user':
                item['back_role_super_admin'] = False

                if 'contact_name' in item:
                    # Remove contact_name, replaced with name...
                    item.pop('contact_name')

                if 'host_notification_period' not in item or \
                   not item['host_notification_period']:
                    item['host_notification_period'] = self.default_tp

                if 'service_notification_period' not in item or \
                   not item['service_notification_period']:
                    item['service_notification_period'] = self.default_tp

            # Special case of timeperiods for hosts and services
            # Always define timeperiods if they do not exist
            if r_name == 'host' or r_name == 'service':
                if 'check_period' not in item or \
                   not item['check_period']:
                    item['check_period'] = self.default_tp

                if 'notification_period' not in item or \
                   not item['notification_period']:
                    item['notification_period'] = self.default_tp

                if 'maintenance_period' not in item or \
                   not item['maintenance_period']:
                    item['maintenance_period'] = self.default_tp

                if 'snapshot_period' not in item or \
                   not item['snapshot_period']:
                    item['snapshot_period'] = self.default_tp

            # Hack for check_command_args
            if 'check_command_args' in item and isinstance(item['check_command_args'], list):
                item['check_command_args'] = '!'.join(item['check_command_args'])

            self.log("Creating links with other objects (data_later)")
            for dummy, values in enumerate(data_later):
                if values['field'] in item and values['type'] == 'simple':
                    if values['now'] and \
                       values['resource'] in self.inserted and \
                       item[values['field']] in self.inserted[values['resource']]:
                        # Link is still existing and should be valid
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
                        print("***Not found: %s = %s in inserted %ss identifiers nor values" % (
                            values['field'], item[values['field']], values['resource']
                        ))
                        later_tmp[values['field']] = item[values['field']]
                        del item[values['field']]

                elif values['field'] in item and values['type'] == 'list' and values['now']:
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
                            # objectsid.append(self.inserted[values['resource']][vallist])
                            objectsid.append(vallist)
                        elif values['resource'] in self.inserted and \
                                vallist in self.inserted[values['resource']].values():
                            index = self.inserted[values['resource']].values().index(vallist)
                            objectsid.append(self.inserted[values['resource']].keys()[index])
                        elif values['resource'] in self.inserted:
                            add = True
                        else:
                            add = False
                    if add:
                        item[values['field']] = objectsid
                    else:
                        print("***Not found: %s = %s in inserted %ss identifiers not values" % (
                            values['field'], item[values['field']], values['resource']
                        ))
                        later_tmp[values['field']] = item[values['field']]
                        del item[values['field']]
                elif values['field'] in item and values['type'] == 'list' and not values['now']:
                    print("***Not found: %s = %s in inserted %ss identifiers not values" % (
                        values['field'], item[values['field']], values['resource']
                    ))
                    later_tmp[values['field']] = item[values['field']]
                    del item[values['field']]

            # Remove unused fields
            # ------------------------------------------------------------
            # - Shinken template link...
            if 'use' in item:
                self.log("removed 'use' field from: %s : %s:" % (r_name, item))
                item.pop('use', None)

            # - Alignak uuid...
            if 'uuid' in item:
                # Commented because too verbose !
                # self.log("removed 'uuid' field from: %s : %s:" % (r_name, item))
                item.pop('uuid', None)

            # - 'unknown_members'
            if 'unknown_members' in item:
                self.log("removed 'unknown_members' field from: %s : %s:" % (r_name, item))
                item.pop('unknown_members', None)

            # Elements common fields
            # ------------------------------------------------------------
            # - 'imported_from' with this script ...
            item['imported_from'] = 'alignak_backend_import'

            # item['_id']       auto generated by the backend

            # item['name']      ok
            if id_name != 'name':
                item['name'] = item[id_name]
                item.pop(id_name)
                print(" --> replaced name for %s: %s" % (r_name, item['name']))

            # item['alias']     not always included, what to do?
            # item['comment']   never included, what to do?

            self.log("before_post: %s : %s:" % (r_name, item))
            try:
                # With headers=None, the post method manages correctly the posted data ...
                response = self.backend.post(r_name, item, headers=None)
                print("-> Created a new: %s : %s" % (r_name, response['_id']))
            except BackendException as e:
                print("# Post error for: %s : %s" % (r_name, item))
                print("***** Exception: %s" % str(e))
                print("***** %s", traceback.format_exc())
                print("***** response: %s" % e.response)
                exit(5)
            else:
                self.log("Element insertion response : %s:" % (response))
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

    def import_objects(self):
        """
        Import objects in backend

        :return: None
        """
        if self.type == 'realm' or self.type == 'all':
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

        if self.type == 'command' or self.type == 'all':
            print("~~~~~~~~~~~~~~~~~~~~~~ add commands ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = []
            schema = command.get_schema()
            self.manage_resource('command', data_later, 'command_name', schema)

        if self.type == 'timeperiod' or self.type == 'all':
            print("~~~~~~~~~~~~~~~~~~~~~~ add timeperiods ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = []
            schema = timeperiod.get_schema()
            self.manage_resource('timeperiod', data_later, 'timeperiod_name', schema)

        if self.type == 'trigger' or self.type == 'all':
            print("~~~~~~~~~~~~~~~~~~~~~~ add trigger ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = []
            schema = trigger.get_schema()
            self.manage_resource('trigger', data_later, 'trigger_name', schema)

        if self.type == 'user' or self.type == 'all':
            print("~~~~~~~~~~~~~~~~~~~~~~ add user ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = [
                {
                    'field': 'usergroups', 'type': 'list',
                    'resource': 'usergroup', 'now': False
                },
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

        if self.type == 'usergroup' or self.type == 'all':
            print("~~~~~~~~~~~~~~~~~~~~~~ add usergroup ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = [
                {
                    'field': 'users', 'type': 'list',
                    'resource': 'user', 'now': True
                },
                {
                    'field': 'usergroup_members', 'type': 'list',
                    'resource': 'usergroup', 'now': False
                }
            ]
            schema = usergroup.get_schema()
            self.manage_resource('usergroup', data_later, 'name', schema)
            print("~~~~~~~~~~~~~~~~~~~~~~ post usergroup ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            self.update_later('usergroup', 'usergroup_members')

        if self.type == 'hostgroup' or self.type == 'all':
            print("~~~~~~~~~~~~~~~~~~~~~~ add hostgroups ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = [
                {
                    'field': 'hostgroups', 'type': 'list',
                    'resource': 'hostgroup', 'now': False
                },
                {
                    'field': 'hosts', 'type': 'list',
                    'resource': 'host', 'now': False
                }
            ]
            schema = hostgroup.get_schema()
            self.manage_resource('hostgroup', data_later, 'hostgroup_name', schema)
            print("~~~~~~~~~~~~~~~~~~~~~~ post hostgroups ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            self.update_later('hostgroup', 'hostgroups')

        if self.type == 'host' or self.type == 'all':
            print("~~~~~~~~~~~~~~~~~~~~~~ add host ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = [
                {
                    'field': 'parents', 'type': 'list',
                    'resource': 'host', 'now': False
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
                    'field': 'trigger', 'type': 'simple',
                    'resource': 'trigger', 'now': True
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
            self.update_later('hostgroup', 'hosts')

        if self.type == 'hostdependency' or self.type == 'all':
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
                }
            ]
            schema = hostdependency.get_schema()
            self.manage_resource('hostdependency', data_later, 'name', schema)

        if self.type == 'servicedependency' or self.type == 'all':
            print("~~~~~~~~~~~~~~~~~~~~~~ add servicedependency ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = [
                {
                    'field': 'dependent_host', 'type': 'list',
                    'resource': 'host', 'now': True
                },
                {
                    'field': 'dependent_hostgroup_name', 'type': 'list',
                    'resource': 'hostgroup', 'now': True
                },
                {
                    'field': 'dependent_service_description', 'type': 'list',
                    'resource': 'service', 'now': True
                },
                {
                    'field': 'host', 'type': 'list',
                    'resource': 'host', 'now': True
                },
                {
                    'field': 'hostgroup_name', 'type': 'list',
                    'resource': 'hostgroup', 'now': True
                }
            ]
            schema = servicedependency.get_schema()
            self.manage_resource('servicedependency', data_later, 'name', schema)

        if self.type == 'hostescalation' or self.type == 'all':
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

        if self.type == 'servicegroup' or self.type == 'all':
            print("~~~~~~~~~~~~~~~~~~~~~~ add servicegroup ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = [
                {
                    'field': 'servicegroups', 'type': 'list',
                    'resource': 'servicegroup', 'now': False
                }
            ]
            schema = servicegroup.get_schema()
            self.manage_resource('servicegroup', data_later, 'servicegroup_name', schema)
            print("~~~~~~~~~~~~~~~~~~~~~~ post servicegroup ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            self.update_later('servicegroup', 'servicegroups')

        if self.type == 'service' or self.type == 'all':
            print("~~~~~~~~~~~~~~~~~~~~~~ add service ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = [
                {
                    'field': 'host', 'type': 'simple',
                    'resource': 'host', 'now': True
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

        if self.type == 'serviceescalation' or self.type == 'all':
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
        exit(4)
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    print("alignak_backend_import, inserted elements: ")
    for object_type in fill.inserted:
        if len(fill.inserted[object_type]):
            print(" - %s %s(s)" % (len(fill.inserted[object_type]), object_type))
        else:
            print(" - no %s(s)" % (object_type))
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")

if __name__ == "__main__":  # pragma: no cover
    main()
