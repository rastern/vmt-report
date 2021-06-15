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
import arbiter
import vmtconnect as vc
import vmtreport.util as vu
from vmtreport import stats
from vmtreport import actions
from vmtreport import targets
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
        kwargs = {}

        if isinstance(__auth, dict):
            kwargs['auth'] = __auth['auth']
        else:
            raise TypeError('Unknown authorization object returned.')

        if 'disable_hateoas' in self.options:
            kwargs['disable_hateoas'] = self.options['disable_hateoas']

        kwargs['ssl'] = self.secure
        _host = f"{self.host}:{self.port}"

        try:
            self._connection = vc.Session(_host, **kwargs)
        except vc.VMTConnectionError as e:
            print(f"Connection Error: {e}")
            exit(0)
        except Exception:
            raise


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
        return stats.GroupedDataReport(self._connection, self.options).apply()


class ActionData(Connection):
    """
    Data handler based on vmt-connect to pull and aggregate actions data based
    on Turbonomic scopes (markets, groups, entities). The handler accepts a list
    of field definitions used to determine the output of the report.

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


class TargetData(Connection):
    """
    """
    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)

        self.connect()

    def get(self):
        """
        Standard Arbiter interface implementation. Returns the grouped and sorted
        data report based on the config.
        """
        return actions.TargetDataReport(self._connection, self.options).apply()


def auth_credstore(obj):
    from vmtconnect.security import Credential

    return {'auth': Credential(obj['keyfile'], obj['credential']).decrypt()}



arbiter.HANDLERS.register('vmtconnect', Connection)
arbiter.HANDLERS.register('vmtgroupeddata', GroupedData)
arbiter.HANDLERS.register('vmtactiondata', ActionData)
#arbiter.HANDLERS.register('vmtactiondata', TargetData)
arbiter.AUTH.register('credstore', auth_credstore)
