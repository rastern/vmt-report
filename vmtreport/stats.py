# Copyright 2021 Turbonomic
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

from .common import FieldTypes, DataField, Options


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

_options = [
    Options.FIELDS,
    Options.GROUPS,
    Options.SORTBY,
    Options.STOP_ERROR
]



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
        '_groups',
        'conn',
        'type',
        'stop_error'
    ]

    def __init__(self, connection, config, stop_error=False):
        self.conn = connection
        self.type = config['type'].lower()
        self.stop_error = stop_error

        if config.get('stop_on_error'):
            self.stop_error = config['stop_on_error']

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
            if self.stop_error:
                raise ValueError(f"Unable to locate '{name}'")

            pass


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
        'fields',
        'stop_error'
    ]

    def __init__(self, conn, options):
        self.conn = conn
        self.stop_error = options.get(Options.STOP_ERROR, False)
        self.groups = Groups(conn, options[Options.GROUPS], self.stop_error)
        self.fields = {f['id']: DataField(f) for f in options[Options.FIELDS]}
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

    def apply(self):
        """
        Applies group (scope) boundaries and field definitions to the Turbonomic
        environment, and generates the data set defined for this report.
        """
        data = []
        #from pprint import pprint

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
            # for f in [x for x in self.fields.values() if x.label]:
            #     if f.id not in _row:
            #         _row[f.id] = None

            data = [*data, _row]

        if self.sort:
            data = multikeysort(data, self.sort)

        # replace labels and order columns
        for i, row in enumerate(data):
            _row = OrderedDict()
            for f in [x for x in self.fields.values() if x.label]:
                #_row[f.label] = row[f.id]
                _row[f.label] = row.get(f.id, None)

            data[i] = _row

        return data
