# Copyright 2020-2021 Turbonomic
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# libraries

from collections import OrderedDict
from enum import Enum
from functools import cmp_to_key
from operator import itemgetter as ig
import re
import traceback

import arbiter
import vmtconnect as vc
import vmtreport.util as vu
from .__about__ import (__author__, __copyright__, __description__,
                        __license__, __title__, __version__)



__all__ = [
    '__author__',
    '__copyright__',
    '__description__',
    '__license__',
    '__title__',
    '__version__',
    'Connection',
    'GroupedData',
    'auth_credstore'
]

_commodities = {
    'Cluster': [
        'CPUHeadroom',
        'MemHeadroom',
        'numContainers',
        'numHosts',
        'numStorages',
        'numVDCs',
        'numVMs',
        'StorageHeadroom',
    ],
    'PhysicalMachine': [
        'Ballooning',
        'CPU',
        'CPUAllocation',
        'CPUProvisioned',
        'HOST_LUN_ACCESS',
        'IOThroughput',
        'Mem',
        'MemAllocation',
        'MemProvisioned',
        'numCPUs',
        'numSockets',
        'NetThroughput',
        'Q1VCPU',
        'Q2VCPU',
        'Q4VCPU',
        'Q8VCPU',
        'Q16VCPU',
        'Q32VCPU',
        'Swapping'
    ],
    'Storage': [
        'StorageAccess',
        'StorageAmount',
        'StorageLatency',
        'StorageProvisioned'
    ],
    'VirtualMachine': [
        'numVCPUs',
        'VCPU',
        'VMem',
        'VStorage'
    ]
}

_template_resources = {
    'computeResources': [
        'cpuConsumedFactor',
        'cpuSpeed',
        'ioThroughput',
        'memoryConsumedFactor',
        'memorySize',
        'networkThroughput',
        'numOfCpu'
    ],
    'infrastructureResources': [
        'coolingSize',
        'powerSize',
        'spaceSize'
    ],
    'storageResources': [
        'diskConsumedFactor',
        'diskIops',
        'diskSize'
    ]
}



class FieldTypes(Enum):
    #: Market commodities (stats)
    COMMODITY = 'commodity'
    #: Computed fields
    COMPUTED = 'computed'
    #: Static entity properties
    PROPERTY = 'property'
    #: String literal
    STRING = 'string'
    #: Template resource field, clusters only
    TEMPLATE = 'template'


# data groups (clusters or entity groups)
# all groups must be of the same type
class Groups:
    """Provides scope to a :py:class:`~vmtreport.GroupedDataReport` handler. This
    may be either of type **cluster**, or **group**, and optionally may contain a list of
    names/uuids.

    Arguments:
        connection (:py:class:`~vmtconnect.Connection`): vmtconnect Connection class
        config (dict): Dictionary of group configuration parameters.
    """
    __slots__ = [
        'conn',
        'type',
        'stop_on_error',
        '_groups'
    ]

    def __init__(self, connection, config):
        self.conn = connection
        self.type = config['type'].lower()
        self.stop_on_error = config.get('stop_on_error', False)

        if config.get('names', None):
            self._groups = [self.group_id(n) for n in config['names']]
        elif self.type == 'cluster':
            clusters = self.conn.search(scopes=['Market'],
                                        types=['Cluster'],
                                        nocache=True,
                                        pager=True)
            self._groups = []

            while not clusters.complete:
                data = clusters.next
                self._groups.extend([x['uuid'] for x in data])

    @property
    def ids(self):
        return self._groups

    def group_id(self, name):
        if self.type.lower() == 'group':
            types = ['Group']
        elif self.type.lower() == 'cluster':
            types = ['Cluster']
        else:
            raise TypeError(f"Unknown type '{self.type}'")

        try:
            return self.conn.search(q=name, types=types)[0]['uuid']
        except (KeyError, IndexError):
            if self.stop_on_error:
                raise ValueError(f"Unable to locate '{name}'")

            pass



# data fields
class DataField:
    """Report field representation. Each field must contain an **id**, **type**,
    and **value**. The **label** field is optional, and should only be set for
    fields that are to be represented in the output; all other fields will be
    truncated after calculated fields processing. Calculated fields are processed
    after all commodity and property fields are populated. The id field can be
    any valid string containing numbers and letters, and may be referenced by
    calculated fields.

    Arguments:
        config (dict): Field configuration dictionary.

    Attributes:
        id (str): Field's unique identifier.
        type (:py:class:`~vmtreport.FieldTypes`): Field type used to determine how
            the value is retrieved.
        name (str): Applies to commodities only. This is the Turbonomic commodity
            name used by the system. *Commodity names are case sensitive.*
        value (str): Resolution path in the API DTO for the value, if a commodity
            or property value, elsewise this is the expression for generating the
            calculated field. Other fields are referenced by prepending their
            **id** with $.
        label (str): Column display header for this field. Only fields with a
            non-null **label** will be returned in the dataset.
    """
    __slots__ = [
        'id',
        'type',
        'name',
        'value',
        'label'
    ]

    def __init__(self, config):
        self.id = config['id']
        self.type = FieldTypes(config['type'])
        self.name = None
        self.label = config.get('label', None)

        if self.type in (FieldTypes.COMMODITY, FieldTypes.TEMPLATE):
            self.name, self.value = config['value'].split(':', maxsplit=1)
        elif self.type in (FieldTypes.PROPERTY, FieldTypes.COMPUTED, FieldTypes.STRING):
            self.value = config['value']
        else:
            raise TypeError(f"Unknown type '{self.type}'")

    # resolve a compute field value
    def compute(self, data):
        r_var = r'([\$\w]+)'
        _str = self.value

        try:
            for token in [i for i in re.split(r_var, self.value) if i]:
                if token[0] == '$':
                    _str = _str.replace(token, str(data[token[1:]]))

            return vu.evaluate(_str)
        except ZeroDivisionError:
            return 0
        except KeyError:
            return None

    # parse a colon reference tree for the proper value
    def tree_get(self, data, _field=None):
        if not _field:
            _field = self.value

        keys = _field.split(':', maxsplit=1)

        if len(keys) > 1:
            return self.tree_get(data[keys[0]], keys[1])

        return data[keys[0]]


# data aggregator
class GroupedDataReport:
    """
    Data processor for generating tabular data from group or cluster properties,
    statistical data (commodities), and custom calculated fields.

    Arguments:
        conn (:py:class:`~vmtconnect.Connection`): Connection object.
        groups (dict): Groups definition.
        fields (list): List of field definition dictionaries.
        period (string): Epoch period to pull stats for. Default: CURRENT
    """
    __slots__ = [
        '__cache',
        'conn',
        'groups',
        'fields'
    ]

    def __init__(self, conn, groups, fields):
        self.conn = conn
        self.groups = Groups(conn, groups)
        self.fields = {f['id']: DataField(f) for f in fields}
        self.__cache = {x: {'stats': {}, 'template': {}, 'property': {}}
                        for x in self.groups.ids}

    # populate data for a given group
    def _get_group_data(self, group, type, related_type=None):
        _data = {'_id': group}

        try:
            if type == FieldTypes.STRING:
                for f in [x for x in self.fields.values() if x.type == type]:
                    _data[f.id] = f.value

            elif type == FieldTypes.PROPERTY:
                if not self.__cache[group]['property']:
                    self.__cache[group]['property'] = self.conn.search(uuid=group)[0]

                for f in [x for x in self.fields.values() if x.type == type]:
                    _data[f.id] = f.tree_get(self.__cache[group]['property'])

            elif type == FieldTypes.COMMODITY:
                def current(value):
                    return True if value['epoch'] == 'CURRENT' else False

                _fields = [x for x in self.fields.values()
                    if x.type == type and x.name in _commodities[related_type]
                ]
                stats = {x.name for x in _fields}
                idx = related_type
                func = None

                if related_type == 'Cluster':
                    related_type = None
                    func = current

                if _fields:
                    if not self.__cache[group]['stats'].get(idx):
                        self.__cache[group]['stats'][idx] = self.conn.get_entity_stats(scope=[group], stats=stats, related_type=related_type)

                    # roll-up data as we go (gets all commodity fields)
                    for p, v in vc.util.enumerate_stats(self.__cache[group]['stats'][idx], period=func):
                        for f in [x for x in _fields if x.name == v['name']]:
                            _data[f.id] = _data.get(f.id, 0) + f.tree_get(v)

            elif type == FieldTypes.TEMPLATE:
                _fields = [x for x in self.fields.values()
                    if x.type == type and x.name in _template_resources[related_type]
                ]

                if _fields:
                    if not self.__cache[group]['property']:
                        self.__cache[group]['property'] = self.conn.search(uuid=group)[0]

                    target = self.__cache[group]['property']['source']['displayName']
                    cluster = self.__cache[group]['property']['displayName'].replace('\\', '_')
                    tname = f"{target}::AVG:{cluster} for last 10 days"

                    if not self.__cache[group]['template']:
                        self.__cache[group]['template'] = self.conn.get_template_by_name(tname)

                    if self.__cache[group]['template'] is None:
                        print(f"Missing template data for {tname}")
                    else:
                        for p, v in vc.util.enumerate_template_resources(self.__cache[group]['template'], restype=lambda x: x == related_type):
                            for f in [x for x in _fields if x.name == v['name']]:
                                _data[f.id] = f.tree_get(v)

        except Exception as e:
            traceback.print_exc()

        return _data

    def apply(self, sort=None):
        """
        Applies group (scope) boundaries and field definitions to the Turbonomic
        environment, and generates the data set defined for this report.
        """
        data = []
        from pprint import pprint

        for g in self.groups.ids:
            # populate properties & literals
            _row = self._get_group_data(g, FieldTypes.STRING)
            _row = {**_row, **self._get_group_data(g, FieldTypes.PROPERTY)}

            # populate commodities
            for c in _commodities:
                _row = {**_row, **self._get_group_data(g, FieldTypes.COMMODITY, c)}

            # populate template resources
            for t in _template_resources:
                _row = {**_row, **self._get_group_data(g, FieldTypes.TEMPLATE, t)}

            # build calculated fields
            for f in [x for x in self.fields.values() if x.type == FieldTypes.COMPUTED]:
                _row[f.id] = f.compute(_row)

            # fill in gaps if any
            for f in [x for x in self.fields.values() if x.label]:
                if f.id not in _row:
                    _row[f.id] = None

            data = [*data, _row]

        if sort:
            data = multikeysort(data, sort)

        # replace labels and order columns
        for i, row in enumerate(data):
            _row = OrderedDict()
            for f in [x for x in self.fields.values() if x.label]:
                _row[f.label] = row[f.id]

            data[i] = _row

        return data


class Connection(arbiter.handlers.HttpHandler):
    """
    vmt-connect Handler for Arbiter. Provides a :py:class:`vmtconnect.Connection`
    object for use as an input source in an :py:class:`arbiter.Process`.

    Arguments:
        config (dict): Dictionary of handler configuration data
        **kwargs: Additional handler specific options. These will override any
            in the `config` options.
    """
    __slots__ = ['_connection']

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)

        self._connection = None

    def connect(self, force=False):
        """
        Standard Arbiter interface implementation. Returns the connection
        instance.
        """
        if self._connection and not force:
            return self._connection

        from requests.packages.urllib3 import disable_warnings
        from requests.packages.urllib3.exceptions import InsecureRequestWarning

        disable_warnings(InsecureRequestWarning)

        __auth = arbiter.get_auth(self.authentication)

        if isinstance(__auth, dict):
            if 'auth' in __auth:
                self._connection = vc.Connection(self.host, auth=__auth['auth'])
            elif 'username' in __auth and 'password' in __auth:
                self._connection = vc.Connection(self.host,
                                                 username=__auth['username'],
                                                 password=__auth['password'])
            return self._connection

        raise TypeError('Unknown authorization object returned.')


class GroupedData(Connection):
    """
    Data handler based on vmt-connect to pull and aggregate entity statistical
    data based on groups. The handler accepts a list of field definitions,
    including computed fields, from which a set is build. Groups are used to
    define the query scope and aggregate data automatically.

    Arguments:
        config (dict): Dictionary of handler configuration data
        **kwargs: Additional handler specific options. These will override any
            in the `config` options.
    """
    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)

        self.connect()

    def get(self):
        """
        Standard Arbiter interface implementation. Returns the grouped and sorted
        data report based on the config.
        """
        return GroupedDataReport(self._connection,
                                 self.options['groups'],
                                 self.options['fields'],
                                ).apply(sort=self.options.get('sortby', None))



def auth_credstore(obj):
    from vmtconnect.security import Credential

    return {'auth': Credential(obj['keyfile'], obj['credential']).decrypt()}


def multikeysort(items, columns):
    comparers = [
        ((ig(col[1:].strip()), -1) if col.startswith('-') else (ig(col.strip()), 1))
        for col in columns
    ]

    def cmp(x, y):
        return (x > y) - (x < y)

    def comparer(left, right):
        comparer_iter = (
            cmp(fn(left), fn(right)) * mult
            for fn, mult in comparers
        )
        return next((result for result in comparer_iter if result), 0)
    return sorted(items, key=cmp_to_key(comparer))



arbiter.HANDLERS.register('vmtconnect', Connection)
arbiter.HANDLERS.register('vmtgroupeddata', GroupedData)
arbiter.AUTH.register('credstore', auth_credstore)
