# Copyright 2020 Turbonomic
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
from .__about__ import (__author__, __copyright__, __description__,
                        __license__, __title__, __version__)



__all__ = [
    '__author__',
    '__copyright__',
    '__description__',
    '__license__',
    '__title__',
    '__version__',
    'VmtConnection',
    'auth_credstore'
]



class VmtConnection(arbiter.handlers.ConnectionHandler):
    """vmt-connect Handler for arbiter

    Provides a vmt-connect :py:class:`~vmtconnect.Connection` object for use as
    an input source in an :py:class:`arbiter.Report`.
    """
    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)

    def connect(self):
        import vmtconnect as vc
        from requests.packages.urllib3 import disable_warnings
        from requests.packages.urllib3.exceptions import InsecureRequestWarning

        disable_warnings(InsecureRequestWarning)

        return vc.Connection(self.hostname, auth=arbiter.get_auth(self.authentication))



def auth_credstore(obj):
    from turbo_api_creds import TurboCredStore

    return TurboCredStore().decrypt(obj['credential'], obj['keyfile'])



arbiter.HANDLERS.register('vmtconnect', VmtConnection)
arbiter.AUTH.register('credstore', auth_credstore)
