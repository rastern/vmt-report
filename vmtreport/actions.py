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
from collections import OrderedDict
from collections.abc import Iterable
from enum import Enum
import json

import vmtconnect as vc

from .common import FieldTypes, DataField, Options
from .util import multikeysort



_default_scope = {'id': 'Market', 'type': 'market'}

_filter_exclusions = ['scope', 'scopes']

_options = [
    Options.FIELDS,
    Options.FILTERS,
    Options.SORTBY,
    Options.STOP_ERROR
]



class FilterSet:
    __slots__ = [
        'values'
    ]

    def __init__(self, config, base=None):
        self.values = self.merge(base.values, config) if base else self.merge(config)

    @staticmethod
    def merge(default, override=None):
        target = vc.util.to_defaultdict(lambda: None, {k: v for k,v in default.items() if k.lower() not in _filter_exclusions})

        if override is None:
            return target

        if all(isinstance(x, Iterable) for x in [override, target]):
            for k in override:
                if isinstance(override[k], dict) and k in default:
                    target[k] = FilterSet.merge(default[k], override[k])
                else:
                    target[k] = override[k]
        else:
            target = override

        return target


class ScopeTypes(Enum):
    #: Market
    MARKET = 'market'
    #: Group
    GROUP = 'group'
    #: Entities
    ENTITY = 'entity'
    #: Targets
    TARGET = 'target'


# data groups (clusters or entity groups)
# all groups must be of the same type
class Scope:
    """Provides scope to a :py:class:`~vmtreport.ActionDataReport` handler. This
    may be of type **entity**, **group**, or **market**, and optionally may contain a list of
    names/uuids.

    Arguments:
        connection (:py:class:`~vmtconnect.Connection`): vmtconnect Connection class
        config (dict): Dictionary of group configuration parameters.
    """
    __slots__ = [
        'conn',
        'type',
        'uuid',
        'stop_error'
    ]

    def __init__(self, connection, config, stop_error=False):
        self.conn = connection
        self.uuid = config['id']
        self.type = None

        if config.get('type'):
            self.type = ScopeTypes(config['type'].lower())
        else:
            self.type = self.get_scope_type()

        if not self.type and stop_error:
            raise ValueError(f"Scope {self.uuid} is not of a valid type")

    @staticmethod
    def __try_method(method, **kwargs):
        try:
            if method(**kwargs):
                return True
        except vc.HTTP400Error as e:
            pass

        return False

    def get_scope_type(self):
        if self.type:
            return self.type

        if self.__try_method(self.conn.get_markets, uuid=self.uuid):
            return ScopeTypes.MARKET
        elif self.__try_method(self.conn.get_entities, uuid=self.uuid):
            return ScopeTypes.ENTITY
        elif self.__try_method(self.conn.get_groups, uuid=self.uuid):
            return ScopeTypes.GROUP
        elif self.__try_method(self.conn.get_targets, uuid=self.uuid):
            return ScopeTypes.TARGET
        else:
            return None


class ActionSet:
    """ x """
    __slots__ = [
        'conn',
        'dto',
        'filter',
        'resp_filter',
        'scope',
        'stop_error',
    ]

    def __init__(self, connection, scope, filter=None, response_filter=None, stop_error=False):
        self.conn = connection
        self.scope = Scope(self.conn, scope, stop_error)
        self.resp_filter = response_filter
        self.stop_error = stop_error

        if filter and isinstance(filter, FilterSet):
            self.dto = filter.values
        else:
            self.dto = filter

    @staticmethod
    def __call(conn, scope, response_filter, post_data=None):
        kwargs = {
            'uuid': scope.uuid,
            'filter': response_filter,
            'pager': True
        }

        if post_data:
            kwargs['dto'] = json.dumps(post_data)

        if scope.type == ScopeTypes.MARKET:
            kwargs['market'] = scope.uuid
            kwargs['uuid'] = None
            _vc_method = conn.get_actions
        elif scope.type == ScopeTypes.ENTITY:
            _vc_method = conn.get_entity_actions
        elif scope.type == ScopeTypes.GROUP:
            _vc_method = conn.get_group_actions
        elif scope.type == ScopeTypes.TARGET:
            _vc_method = conn.get_target_actions
        else:
            raise TypeError(f"Unknown type {scope.type} for action data")

        return _vc_method(**kwargs)

    def get_actions(self):
        actions = []
        resp = self.__call(self.conn, self.scope, self.resp_filter, self.dto)

        try:
            while not resp.complete:
                actions.extend(resp.next)
        except Exception:
            if self.stop_error:
                raise
            else:
                pass

        return actions


# data aggregator
class ActionDataReport:
    """
    Data processor for generating tabular data from actions.

    Arguments:
        conn (:py:class:`~vmtconnect.Connection`): Connection object.
        filters (dict): Filtering parameters to narrow the scope of actions.
        fields (list): List of field definition dictionaries.
    """
    __slots__ = [
        '__sets',
        'conn',
        'fields',
        'filters',
        'resp_filter',
        'sortby',
        'stop_error'
    ]

    def __init__(self, conn, options):
        self.conn = conn
        self.fields = {f['id']: DataField(f) for f in options[Options.FIELDS.value]}
        self.resp_filter = self._response_filter()
        self.filters = None
        self.sortby = options.get(Options.SORTBY.value)
        self.stop_error = options[Options.STOP_ERROR.value]
        self.__sets = {}

        if options.get(Options.FILTERS.value):
            self.filters = FilterSet(options[Options.FILTERS.value])

        try:
            if options[Options.FILTERS.value]:
                scopes = options[Options.FILTERS.value][Options.SCOPES.value]
            else:
                scopes = _default_scope

            for s in scopes:
                self.__sets[s['id']] = ActionSet(
                    self.conn,
                    s,
                    FilterSet(s.get('filters'), self.filters),
                    self.resp_filter,
                    self.stop_error
                )
        except Exception:
            if self.stop_error:
                raise
            else:
                pass

    def _response_filter(self):
        filter = []

        for f in self.fields.values():
            if f.type == FieldTypes.PROPERTY:
                filter.append(f.value.replace(':', '.'))

        return filter

    def apply(self):
        """
        Applies scope boundaries and field definitions to the Turbonomic
        environment, and generates the data set defined for this report.
        """
        data = []

        for actionset in self.__sets.values():
            _cache = actionset.get_actions()

            for action in _cache:
                _row = {}

                # populate properties & literals
                for f in [x for x in self.fields.values() if x.type == FieldTypes.STRING]:
                    _row[f.id] = f.value

                for f in [x for x in self.fields.values() if x.type == FieldTypes.PROPERTY]:
                    _row[f.id] = f.tree_get(action)

                # build calculated fields
                for f in [x for x in self.fields.values() if x.type == FieldTypes.COMPUTED]:
                    _row[f.id] = f.compute(_row)

                data = [*data, _row]

        if self.sortby:
           data = multikeysort(data, self.sortby)

        # replace labels and order columns
        for i, row in enumerate(data):
            _row = OrderedDict()
            for f in [x for x in self.fields.values() if x.label]:
                _row[f.label] = row.get(f.id, None)

            data[i] = _row

        return data
