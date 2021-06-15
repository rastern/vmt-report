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
import traceback

import vmtconnect as vc

from .common import FieldTypes, DataField, Options
from .util import multikeysort



# data groups (clusters or entity groups)
# all groups must be of the same type
class Targets:
    """Provides scope to a :py:class:`~vmtreport.GroupedDataReport` handler. This
    may be either of type **cluster**, or **group**, and optionally may contain a list of
    names/uuids.

    Arguments:
        connection (:py:class:`~vmtconnect.Connection`): vmtconnect Connection class
        config (dict): Dictionary of group configuration parameters.
    """
    __slots__ = [
        '_targets',
        'conn',
        'resp_filter',
        'stop_error'
    ]

    def __init__(self, connection, config, response_filter=None, stop_error=False):
        self.conn = connection
        self.stop_error = stop_error
        self.resp_filter = response_filter
        self._targets = []

        if config.get('stop_on_error'):
            self.stop_error = config['stop_on_error']

        self._get()

    def _get(self):
        kwargs = {'pager': True}

        if self.resp_filter:
            kwargs['filter'] = self.resp_filter

        resp = self.conn.get_targets(**kwargs)

        try:
            while not resp.complete:
                self._targets.extend(resp.next)
        except Exception:
            if self.stop_error:
                raise
            else:
                pass

    def get(self):
        return self._targets


# data aggregator
class TargetDataReport:
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
        'resp_filter',
        'sortby',
        'stop_error'
    ]

    def __init__(self, conn, options):
        self.conn = conn
        self.fields = {f['id']: DataField(f) for f in options[Options.FIELDS.value]}
        self.resp_filter = self._response_filter()
        self.sortby = options.get(Options.SORTBY.value)
        self.stop_error = options[Options.STOP_ERROR.value]

        try:
            self.__actions = Targets(self.conn, self.resp_filter, self.stop_error)
        except Exception:
            if self.stop_error:
                raise
            else:
                self.__actions = {}
                pass

    def _response_filter(self):
        filter = []

        for f in self.fields.values():
            if f.type == FieldTypes.PROPERTY:
                filter.append(f.value.replace(':', '.'))

        return filter

    def apply(self):
        """
        Applies field definitions to the Turbonomic environment, and generates
        the data set defined for this report.
        """
        data = []

        for target in self.__sets.values():
            _cache = target.gets()

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
