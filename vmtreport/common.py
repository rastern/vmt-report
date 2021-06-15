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
from enum import Enum
import re



class Options(Enum):
    #:
    FIELDS = 'fields'
    #:
    FILTERS = 'filters'
    #:
    GROUPS = 'groups'
    #:
    SCOPES = 'scopes'
    #:
    SORTBY = 'sortby'
    #:
    STOP_ERROR = 'stop_on_error'


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


# data fields
class DataField:
    """Report field representation. Each field must contain an **id**, **type**,
    and **value**. The **label** field is optional, and should only be set for
    fields that are to be represented in the output; all other fields will be
    truncated after calculated fields processing. Calculated fields are processed
    after all commodity and property fields are populated. The id field can be
    any valid string containing numbers and letters, and may be referenced by
    calculated fields using '$'.

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
            calculated field.
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
