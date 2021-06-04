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
from functools import cmp_to_key
from operator import itemgetter as ig
import re
import traceback

import arbiter
import vmtconnect as vc
import vmtreport.util as vu
from vmtreport import stats
from vmtreport import actions
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
        return stats.GroupedDataReport(self._connection,
                                       self.options['groups'],
                                       self.options['fields'],
                                      ).apply()


class ActionData(Connection):
    """
    Action handler.

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
        return actions.ActionDataReport(self._connection, self.options).apply()


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
arbiter.HANDLERS.register('vmtactiondata', ActionData)
arbiter.AUTH.register('credstore', auth_credstore)
