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
