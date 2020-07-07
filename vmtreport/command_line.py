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

import argparse
import json
import sys

import arbiter
import vmtreport



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config',
                        default='./report.conf',
                        help='Configuration file to use')

    args = parser.parse_args()
    try:
        report = arbiter.Process(args.config)
        report.run()
    except json.decoder.JSONDecodeError:
        print('Error processing configuration file. Input must be valid JSON.')
    except Exception:
        raise



if __name__ == '__main__':
    main()
