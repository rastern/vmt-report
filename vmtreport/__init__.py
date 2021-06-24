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
import base64
from email.message import EmailMessage
from email.utils import COMMASPACE
import mimetypes
import re
import smtplib

import arbiter
import vmtconnect as vc
from vmtconnect.security import Credential

from vmtreport import common
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

EMAIL_HTML_HEAD = '''
<!DOCTYPE html PUBLIC “-//W3C//DTD XHTML 1.0 Transitional//EN” “https://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd”>
<html xmlns=“https://www.w3.org/1999/xhtml”>
<head>
<title>{SUBJECT}</title>
<meta http–equiv=“Content-Type” content=“text/html; charset=UTF-8” />
<meta http–equiv=“X-UA-Compatible” content=“IE=edge” />
<meta name=“viewport” content=“width=device-width, initial-scale=1.0 “ />
<style>
{STYLE}
</style>
</head>
<body>
'''
EMAIL_HTML_FOOT = '''
</body>
</html>
'''



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
    Data handler for pulling Turbonomic Target infomration.

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
        return targets.TargetDataReport(self._connection, self.options).apply()


class DataResource(arbiter.handlers.FileHandler):
    """
    Output data handler for preparing data for use as the email message body.
    Requires use of a compatible Notification handler, as this handler does not
    write to a file.

    Arguments:
        config (dict): Dictionary of handler configuration data
        **kwargs: Additional handler specific options. These will override any
            in the `config` options.
    """
    __slots__ = ['filename']

    def __init__(self, config, **kwargs):
        config['resource'] = ''
        super().__init__(config, **kwargs)

        self.filename = None
        self.mimetype = self.options.get('type', 'text/plain')
        self.encoding = self.options.get('encoding', 'base64')

    def enc_txt(self):
        if self.encoding:
            return f";{self.encoding}"
        else:
            return ''

    def encode(self, data):
        if self.encoding == 'base64':
            return base64.b64encode(data.encode())
        elif self.encoding:
            return data.encode(encoding=self.encoding)
        else:
            return data

    def set(self, data):
        """
        Stores the conventional output in the 'filename' reference instead
        of writing to file.
        """
        if not data:
            pass

        if 'fieldnames' not in self.options:
            self.options['fieldnames'] = data[0].keys()

        data = self.encode(common.format(
                    self.options['format'].get('type', 'tabulate'),
                    data,
                    self.options['fieldnames'],
                    self.options.get('format')
                    )).decode()

        self.filename = f"data:{self.mimetype}{self.enc_txt()},{data}"

    def atexit(self):
        pass


class ExtendedEmailHandler(arbiter.handlers.EmailHandler):
    """
    An extension to the Arbiter EmailHandler. Adds HTML capability as well as
    support for data: URI resource definitions.
    """
    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)

        self._emailheaders.append('html_prologue')
        self._emailheaders.append('html_epilogue')

    @staticmethod
    def get_data_type(resource):
        try:
            if resource.startswith('data:'):
                m = re.search('(?:data:)([^;]+)(?:;(?:[\S]+))?,(?:.*)', resource)

                return m[1]
        except AttributeError:
            pass

        return resource

    @staticmethod
    def any_html(res_list):
        for res in res_list:
            if ExtendedEmailHandler.get_data_type(res) == 'text/html':
                return True

        return False

    @staticmethod
    def decode(resource):
        try:
            if resource.startswith('data:'):
                # 1 - type, 2 - encoding, 3 - data
                m = re.search('(?:data:)([^;]+)(?:;([\S]+))?,(.*)', resource)

                if m[2] == 'base64':
                    return base64.b64decode(m[3]).decode()
                elif m[2]:
                    return m[3].decode(encoding=m[2])
                else:
                    return m[3]
        except AttributeError:
            pass

        return resource

    @staticmethod
    def get_body(body, resources):
        _data = ''

        for res in resources:
            _data += ExtendedEmailHandler.decode(res)

        return arbiter.parse_string(body, data=_data)

    @staticmethod
    def set_headers(msg, options, headers):
        for k in options:
            if k in headers:
                if isinstance(options[k], list):
                    msg[k] = arbiter.parse_string(COMMASPACE.join(options[k]))
                else:
                    msg[k] = arbiter.parse_string(options[k])

        return msg

    @staticmethod
    def attach_files(msg, files):
        for file in files:
            ctype, encoding = mimetypes.guess_type(file)

            # unknown, treat as binary
            if ctype is None or encoding is not None:
                ctype = 'application/octet-stream'

            maintype, subtype = ctype.split('/', 1)

            with open(file, 'rb') as fp:
                msg.add_attachment(fp.read(),
                               maintype=maintype,
                               subtype=subtype,
                               filename=os.path.basename(file))

        return msg

    def send(self):
        msg = EmailMessage()
        msg = self.set_headers(msg, self.options['email'], self._emailheaders)

        if self.errors:
            error_msg = '\n\n'.join([str(x) for x in self.errors])
            body = self.options['email'].get('body_error', self.default_body_error)
            msg.set_content(arbiter.parse_string(body, errors=error_msg))
        else:
            data = []
            files = [x for x in self.files if x and not x.startswith('data:')]

            if self.options.get('embed_data_resource', True):
                data = [x for x in self.files if x and x.startswith('data:')]

            subs = {
                'STYLE': self.options.get('style', ''),
                'SUBJECT': arbiter.parse_string(self.options['email']['subject'])
            }
            body = self.get_body(self.options['email']['body'], data)

            if self.any_html(data) and self.options.get('html', False):
                p = self.options['email'].get('html_prologue',
                            arbiter.parse_string(EMAIL_HTML_HEAD, **subs))
                e = self.options['email'].get('html_epilogue', EMAIL_HTML_FOOT)
                msg.set_content(f"{p}{body}{e}", subtype='html')
            else:
                msg.set_content(body)

            if files:
                msg = self.attach_files(msg, files)

        if self.options['smtp'].get('ssl', False):
            klass = smtplib.SMTP_SSL
        elif self.options['smtp'].get('lmtp', False):
            klass = smtplib.LMTP
        else:
            klass = smtplib.SMTP

        _smtp_opts = self._EmailHandler__smtp_options()

        with klass(host=self.options['smtp']['host'], **_smtp_opts) as smtp:
            if self.options['smtp'].get('tls', False):
                tlsargs = {
                    x: self.options['smtp'][x] for x in self.options['smtp']
                        if x in ['keyfile', 'certfile']
                }
                smtp.starttls(**tlsargs)

            if self.options['smtp'].get('username', None) \
            and self.options['smtp'].get('password', None):
                smtp.login(self.options['smtp']['username'], self.options['smtp']['password'])

            smtp.send_message(msg)



def auth_credstore(obj):
    return {'auth': Credential(obj['keyfile'], obj['credential']).decrypt()}



arbiter.HANDLERS.register('vmtconnect', Connection)
arbiter.HANDLERS.register('vmtgroupeddata', GroupedData)
arbiter.HANDLERS.register('vmtactiondata', ActionData)
arbiter.HANDLERS.register('vmttargetdata', TargetData)
arbiter.HANDLERS.register('dataresource', DataResource)
arbiter.HANDLERS.register('extendedemail', ExtendedEmailHandler)

arbiter.AUTH.register('credstore', auth_credstore)
