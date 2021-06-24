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
from dataclasses import dataclass
from enum import Enum
import re

import vmtreport.util as vu



@dataclass
class HTML:
    TABLE: str = 'table'
    TBODY: str = 'tbody'
    TD: str = 'td'
    TH: str = 'th'
    THEAD: str = 'thead'
    TR: str = 'tr'


class Options(Enum):
    #:
    FIELDS = 'fields'
    #:
    FILTERS = 'filters'
    #:
    GROUPS = 'groups'
    #:
    RESPONSE_FILTER = 'response_filter'
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



def html_attr(attr, v, delim=' '):
    if v:
        v = [v] if isinstance(v, str) else [x for x in v if x]
        return f" {attr}=\"{delim.join(v)}\"" if v else ''

    return ''


def html_tag(tag, data, classes=None, styles=None):
    attr = ''
    attr += html_attr('class', classes)
    attr += html_attr('style', styles, '; ')

    return f"<{tag}{attr}>{data}</{tag}>"


# a replacement for tabulate's function
def _html_row(tag, unsafe, css_cls, css_style, cell_values, colwidths, colaligns):
    try:
        from html import escape as htmlescape
    except ImportError:
        from cgi import escape as htmlescape

    if not css_cls:
        css_cls = {}

    if not css_style:
        css_style = {}

    cols = []
    typ = 'header_cols' if tag == HTML.TH else 'cols'

    for i, v in enumerate(cell_values):
        v = v if unsafe else htmlescape(v)

        cols.append(html_tag(tag, v.strip(),
                             css_cls.get(typ, [None]*(i+1))[i],
                             css_style.get(typ, [None]*(i+1))[i]))

    row = html_tag(HTML.TR, ''.join(cols).strip(),
                   css_cls.get('row'),
                   css_style.get('row'))

    if tag == HTML.TH:
        return f"<{HTML.TABLE}>\n<{HTML.THEAD}>\n{row}\n</{HTML.THEAD}>\n<{HTML.TBODY}>"
    else:
        return row


def format(type, data, fields, options=None):
    try:
        _func = _formatters[type.lower()]

        return _func(data, fields, options)
    except KeyError:
        raise NameError(f"Unknown format type: {type}")


def fmt_tabulate(data, fields, options=None):
    from tabulate import tabulate

    kwargs = {'headers': fields}

    if options:
        kwargs.update({x: options[x] for x in options
                            if x not in ['type']
                      })

    return tabulate([[r[_] for _ in r] for r in data], **kwargs)


def fmt_htmltable(data, fields, options=None):
    from functools import partial
    import tabulate

    # tabulate uses namedtuples, so we're gonna monkeypatch it
    # tabulate should probably use a dataclass
    # (tag, unsafe, styles, values, colwidths, colaligns)
    fmt = tabulate._table_formats['html']
    fmt = fmt._replace(headerrow = partial(_html_row, HTML.TH,
                                           not options.get('htmlsafe', True),
                                           options.get('classes'),
                                           options.get('styles')))
    fmt = fmt._replace(datarow = partial(_html_row, HTML.TD,
                                         not options.get('htmlsafe', True),
                                         options.get('classes'),
                                         options.get('styles')))
    tabulate._table_formats['html'] = fmt
    kwargs = {'headers': fields, 'tablefmt': 'html'}

    if options:
        kwargs.update({x: options[x] for x in options
                            if x not in ['type', 'htmlsafe', 'classes', 'styles']
                      })

    return tabulate.tabulate([[r[_] for _ in r] for r in data], **kwargs)



_formatters = {
    'tabulate': fmt_tabulate,
    'htmltable': fmt_htmltable
}
