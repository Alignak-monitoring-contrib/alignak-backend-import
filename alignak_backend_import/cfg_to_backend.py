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

from alignak_backend.models import command
from alignak_backend.models import timeperiod
from alignak_backend.models import hostgroup
from alignak_backend.models import hostdependency
from alignak_backend.models import servicedependency
from alignak_backend.models import serviceextinfo
from alignak_backend.models import trigger
from alignak_backend.models import contact
from alignak_backend.models import contactgroup
from alignak_backend.models import contactrestrictrole
from alignak_backend.models import escalation
from alignak_backend.models import host
from alignak_backend.models import hostextinfo
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
        realms = self.backend.get_all('realm')
        for cont in realms['_items']:
            if cont['name'] == 'All' and cont['_level'] == 0:
                self.realm_all = cont['_id']

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
        #    hostgroup.hostgroup_members
        # HOSTDEPENDENCY
        # SERVICEDEPENDENCY
        # SERVICEEXTINFO
        # TRIGGER
        # CONTACT
        # CONTACTGROUP
        #    contact.contactgroups / contactgroup.contactgroup_members
        # CONTACTRESTRICTROLE
        # ESCALATION
        # HOST
        #    hostgroup.members / host.use / host.parents
        # HOSTEXTINFO
        # HOSTESCALATION
        # SERVICEGROUP
        #    servicegroup.servicegroup_members
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
        if self.destroy_backend_data:
            print("~~~~~~~~~~~~~~~~~~~~~~~~ Deleting existing backend data ~~~~~~~~~~~~~~~~~~~~~~")
            headers = {'Content-Type': 'application/json'}
            if self.type == 'command' or self.type == 'all':
                self.backend.delete('command', headers)
            if self.type == 'timeperiod' or self.type == 'all':
                timeperiods = self.backend.get_all('timeperiod')
                headers_realm = {'Content-Type': 'application/json'}
                for tp in timeperiods['_items']:
                    if tp['name'] == '24x7':
                        self.inserted['timeperiod'] = {}
                        self.inserted['timeperiod'][tp['_id']] = '24x7'
                        self.default_tp = tp['_id']
                    else:
                        headers_realm['If-Match'] = tp['_etag']
                        self.backend.delete('timeperiod/' + tp['_id'], headers_realm)
            if self.type == 'hostgroup' or self.type == 'all':
                self.backend.delete('hostgroup', headers)
            if self.type == 'hostdependency' or self.type == 'all':
                self.backend.delete('hostdependency', headers)
            if self.type == 'servicedependency' or self.type == 'all':
                self.backend.delete('servicedependency', headers)
            if self.type == 'serviceextinfo' or self.type == 'all':
                self.backend.delete('serviceextinfo', headers)
            if self.type == 'trigger' or self.type == 'all':
                self.backend.delete('trigger', headers)
            if self.type == 'contact' or self.type == 'all':
                contacts = self.backend.get_all('contact')
                headers_contact = {'Content-Type': 'application/json'}
                for cont in contacts['_items']:
                    if cont['name'] != 'admin':
                        headers_contact['If-Match'] = cont['_etag']
                        self.backend.delete('contact/' + cont['_id'], headers_contact)
                realms = self.backend.get_all('realm')
                headers_realm = {'Content-Type': 'application/json'}
                for realm in realms['_items']:
                    if realm['name'] != 'All' and realm['_level'] != 0:

                        headers_realm['If-Match'] = realm['_etag']
                        # TODO: fix error: alignak_backend_client.client.BackendException:
                        # Backend error code 1003: Backend HTTPError:
                        # <class 'requests.exceptions.HTTPError'> /
                        # 409 Client Error: CONFLICT for url:
                        # http://127.0.0.1:5000/realm/574f4bc44c988c303107b0f6

                        # self.backend.delete('realm/' + realm['_id'], headers_realm)
                        # self.backend.delete('realm/' + realm['_id'], headers=None)
            if self.type == 'contactgroup' or self.type == 'all':
                self.backend.delete('contactgroup', headers)
            if self.type == 'contactrestrictrole' or self.type == 'all':
                self.backend.delete('contactrestrictrole', headers)
            if self.type == 'escalation' or self.type == 'all':
                self.backend.delete('escalation', headers)
            if self.type == 'host' or self.type == 'all':
                self.backend.delete('host', headers)
            if self.type == 'hostextinfo' or self.type == 'all':
                self.backend.delete('hostextinfo', headers)
            if self.type == 'hostescalation' or self.type == 'all':
                self.backend.delete('hostescalation', headers)
            if self.type == 'servicegroup' or self.type == 'all':
                self.backend.delete('servicegroup', headers)
            if self.type == 'service' or self.type == 'all':
                self.backend.delete('service', headers)
            if self.type == 'serviceescalation' or self.type == 'all':
                self.backend.delete('serviceescalation', headers)
            if self.type == 'livestate' or self.type == 'all':
                self.backend.delete('livestate', headers)
            if self.type == 'livesynthesis' or self.type == 'all':
                self.backend.delete('livesynthesis', headers)
            if self.type == 'all':
                self.backend.delete('uipref', headers)
            print("~~~~~~~~~~~~~~~~~~~~~~~~ Existing backend data destroyed ~~~~~~~~~~~~~~~~~~~~~")

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
        names = ['service_description', 'host_name', 'dependent_host_name',
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

        source.update(addprop)
        self.log("Converted: %s" % source)
        return source

    def update_later(self, resource, field):
        """
        Update field of resource having a link with other resources (objectid in backend)

        :param resource: resource name (command, contact, host...)
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
                data = {
                    field: self.inserted[item['resource']][item['value']]
                }
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
                                data[field].append(self.inserted[item['resource']].keys()[idx])

            try:
                headers['If-Match'] = item['_etag']
                self.log("before_patch: %s : %s:" % (''.join([resource, '/', index]), data))
                resp = self.backend.patch(''.join([resource, '/', index]), data, headers, True)
            except BackendException as e:
                print("# Patch error for: %s : %s" % (resource, data))
                print("***** Exception: %s" % str(e))
                print("***** Traceback: %s", traceback.format_exc())
                if "_issues" in e.response:
                    print("***** issues: %s" % e.response['_issues'])
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

        # Alignak defined timeperiods
        timeperiods = getattr(self.arbiter.conf, 'timeperiods')

        for item_obj in getattr(self.arbiter.conf, alignak_resource):
            item = {}

            self.log("...................................")
            self.log("Manage resource %s: %s (%s)" % (r_name, item_obj.uuid, item_obj.get_name()))
            print ("Manage resource %s: %s (%s)" % (r_name, item_obj.uuid, item_obj.get_name()))
            # TODO
            # Only deal with properties,
            for prop in item_obj.properties.keys():
                if not hasattr(item_obj, prop):
                    continue
                item[prop] = getattr(item_obj, prop)
            # As of it, ignore attributes (use, name, definition_order and register) !

            # Ignore specific items ...
            #  - admin contact
            if r_name == 'contact' and item[id_name] == "admin":
                print ("-> do not change anything for admin contact.")
                continue

            #  - default timeperiod
            if r_name == 'timeperiod' and item[id_name] == "24x7":
                print ("-> do not change anything for default timeperiod.")
                continue

            #  - specific commands
            if r_name == 'command' and item[id_name] in ['bp_rule', '_internal_host_up', '_echo']:
                print ("-> do not import this command.")
                continue

            # Special case of timeperiods
            for tp_name in ['host_notification_period', 'service_notification_period',
                            'check_period', 'notification_period', 'maintenance_period',
                            'snapshot_period', 'escalation_period', 'dependency_period']:
                if tp_name not in item:
                    continue
                print("TP for %s: %s = %s" % (
                    r_name, tp_name, item[tp_name]
                ))
                if item[tp_name] in timeperiods:
                    print("TP is %s" % (
                        timeperiods[item[tp_name]]
                    ))
                if item[tp_name] == '24x7':
                    print("Changed TP: %s to default TP." % (tp_name))
                    item[tp_name] = self.default_tp
                    continue

                if timeperiods[item[tp_name]] and \
                   timeperiods[item[tp_name]].timeperiod_name == '24x7':
                    print("Changed TP: %s to default TP." % (tp_name))
                    item[tp_name] = self.default_tp

            # convert objects
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

            # Special case of custom variables
            # Only import element custom variables if schema allows unknown fields ...
            # ... not the best solution. They should be imported in 'customs' defined array field!
            if 'customs' in schema['schema']:
                item['customs'] = item_obj.customs
            elif 'allow_unknown' in schema and schema['allow_unknown']:
                for prop in item_obj.customs.keys():
                    item[prop] = item_obj.customs[prop]

            # Special case of contacts
            if r_name == 'contact':
                item['back_role_super_admin'] = False

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

            # If id name is name ... keep it!
            if id_name != 'name':
                item['name'] = item[id_name]
                del item[id_name]

            # Force imported_from with Alignak ...
            # item['imported_from'] = 'alignak_backend_import'

            # Remove Shinken template link...
            if 'use' in item:
                del item['use']

            # Remove Alignak uuid if populated...
            if 'uuid' in item:
                del item['uuid']

            # Case where no realm but alignak define internal realm name 'Default'
            if 'realm' in item:
                if item['realm'] == 'Default':
                    del item['realm']
            if r_name in ['host', 'hostgroup']:
                item['realm'] = self.realm_all
            else:
                item['_realm'] = self.realm_all
            if r_name in ['service']:
                item.pop('realm', None)

            # Remove unnecessary 'unknown_members' in data
            if 'unknown_members' in item:
                self.log("removed 'unknown_members' field from: %s : %s:" % (r_name, item))
                item.pop('unknown_members', None)

            self.log("before_post: %s : %s:" % (r_name, item))
            try:
                # With headers=None, the post method manages correctly the posted data ...
                response = self.backend.post(r_name, item, headers=None)
            except BackendException as e:
                print("# Post error for: %s : %s" % (r_name, item))
                print("***** Exception: %s" % str(e))
                print("***** Traceback: %s", traceback.format_exc())
                if "_issues" in e.response:
                    print("***** issues: %s" % e.response['_issues'])
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

        if self.type == 'contact' or self.type == 'all':
            print("~~~~~~~~~~~~~~~~~~~~~~ add contact ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = [
                {
                    'field': 'contactgroups', 'type': 'list',
                    'resource': 'contactgroup', 'now': False
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
            schema = contact.get_schema()
            self.manage_resource('contact', data_later, 'contact_name', schema)

        if self.type == 'contactgroup' or self.type == 'all':
            print("~~~~~~~~~~~~~~~~~~~~~~ add contactgroup ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = [
                {
                    'field': 'members', 'type': 'list',
                    'resource': 'contact', 'now': True
                },
                {
                    'field': 'contactgroup_members', 'type': 'list',
                    'resource': 'contactgroup', 'now': False
                }
            ]
            schema = contactgroup.get_schema()
            self.manage_resource('contactgroup', data_later, 'contactgroup_name', schema)
            print("~~~~~~~~~~~~~~~~~~~~~~ post contactgroup ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            self.update_later('contactgroup', 'contactgroup_members')

        if self.type == 'escalation' or self.type == 'all':
            print("~~~~~~~~~~~~~~~~~~~~~~ add escalation ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = [
                {
                    'field': 'contacts', 'type': 'list',
                    'resource': 'contact', 'now': True
                },
                {
                    'field': 'contact_groups', 'type': 'list',
                    'resource': 'contactgroup', 'now': True
                }
            ]
            schema = escalation.get_schema()
            self.manage_resource('escalation', data_later, 'escalation_name', schema)

        if self.type == 'hostgroup' or self.type == 'all':
            print("~~~~~~~~~~~~~~~~~~~~~~ add hostgroups ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = [
                {
                    'field': 'members', 'type': 'list',
                    'resource': 'host', 'now': False
                },
                {
                    'field': 'hostgroup_members', 'type': 'list',
                    'resource': 'hostgroup', 'now': False
                }
            ]
            schema = hostgroup.get_schema()
            self.manage_resource('hostgroup', data_later, 'hostgroup_name', schema)
            print("~~~~~~~~~~~~~~~~~~~~~~ post hostgroups ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            self.update_later('hostgroup', 'hostgroup_members')

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
                    'field': 'check_period', 'type': 'simple',
                    'resource': 'timeperiod', 'now': True
                },
                {
                    'field': 'contacts', 'type': 'list',
                    'resource': 'contact', 'now': True
                },
                {
                    'field': 'contact_groups', 'type': 'list',
                    'resource': 'contactgroup', 'now': True
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
            self.update_later('hostgroup', 'members')

        if self.type == 'hostextinfo' or self.type == 'all':
            print("~~~~~~~~~~~~~~~~~~~~~~ add hostextinfo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = []
            schema = hostextinfo.get_schema()
            self.manage_resource('hostextinfo', data_later, 'host_name', schema)

        if self.type == 'hostdependency' or self.type == 'all':
            print("~~~~~~~~~~~~~~~~~~~~~~ add hostdependency ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = [
                {
                    'field': 'host_name', 'type': 'list',
                    'resource': 'host', 'now': True
                },
                {
                    'field': 'dependent_host_name', 'type': 'list',
                    'resource': 'host', 'now': True
                },
                {
                    'field': 'dependent_hostgroup_name', 'type': 'list',
                    'resource': 'hostgroup', 'now': True
                },
                {
                    'field': 'hostgroup_name', 'type': 'list',
                    'resource': 'hostgroup', 'now': True
                }
            ]
            schema = hostdependency.get_schema()
            self.manage_resource('hostdependency', data_later, 'name', schema)

        if self.type == 'servicedependency' or self.type == 'all':
            print("~~~~~~~~~~~~~~~~~~~~~~ add servicedependency ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = [
                {
                    'field': 'dependent_host_name', 'type': 'list',
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
                    'field': 'host_name', 'type': 'list',
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
                    'field': 'contacts', 'type': 'list',
                    'resource': 'contact', 'now': True
                },
                {
                    'field': 'contact_groups', 'type': 'list',
                    'resource': 'contactgroup', 'now': True
                }
            ]
            schema = hostescalation.get_schema()
            self.manage_resource('hostescalation', data_later, 'host_name', schema)

        if self.type == 'servicegroup' or self.type == 'all':
            print("~~~~~~~~~~~~~~~~~~~~~~ add servicegroup ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = [
                {
                    'field': 'members', 'type': 'list',
                    'resource': 'service', 'now': False
                },
                {
                    'field': 'servicegroup_members', 'type': 'list',
                    'resource': 'servicegroup', 'now': False
                }
            ]
            schema = servicegroup.get_schema()
            self.manage_resource('servicegroup', data_later, 'servicegroup_name', schema)
            print("~~~~~~~~~~~~~~~~~~~~~~ post servicegroup ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            self.update_later('servicegroup', 'servicegroup_members')

        if self.type == 'service' or self.type == 'all':
            print("~~~~~~~~~~~~~~~~~~~~~~ add service ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = [
                {
                    'field': 'host_name', 'type': 'simple',
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
                    'field': 'contacts', 'type': 'list',
                    'resource': 'contact', 'now': True
                },
                {
                    'field': 'contact_groups', 'type': 'list',
                    'resource': 'contactgroup',
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
            self.update_later('servicegroup', 'members')

        if self.type == 'serviceextinfo' or self.type == 'all':
            print("~~~~~~~~~~~~~~~~~~~~~~ add serviceextinfo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = []
            schema = serviceextinfo.get_schema()
            self.manage_resource('serviceextinfo', data_later, 'name', schema)

        if self.type == 'serviceescalation' or self.type == 'all':
            print("~~~~~~~~~~~~~~~~~~~~~~ add serviceescalation ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            data_later = [
                {
                    'field': 'contacts', 'type': 'list',
                    'resource': 'contact', 'now': True
                },
                {
                    'field': 'contact_groups', 'type': 'list',
                    'resource': 'contactgroup', 'now': True
                }
            ]
            schema = serviceescalation.get_schema()
            self.manage_resource('serviceescalation', data_later, 'host_name', schema)

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
