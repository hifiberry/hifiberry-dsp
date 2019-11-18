'''
Copyright (c) 2018 Modul 9/HiFiBerry

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

import csv
import logging

import requests

BASEURL = "http://localhost:6981/api"


def read_csv(filename):

    f = []
    db = []
    phase = []

    with open(filename) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        for row in csv_reader:
            try:
                f.append(float(row[0]))
                db.append(float(row[1]))
                if len(row) > 2:
                    phase.append(float(row[2]))
                else:
                    phase.append(0)
            except:
                logging.warning("Could not parse line %s", row)

    return {"f": f, "db": db, "phase":phase }


def call_api(command, data, params={}):
    url = BASEURL + "/" + command

    result = requests.post(url, json={"measurement": data, **params})
    if result.status_code != 200:
        return None

    return result.json()


def main():

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--url',
                        default="https;//optimizer.hifiberry.com",
                        help='URL of he optimizer')
    parser.add_argument('-v', '--verbose',
                        help="increase output verbosity",
                        action="store_true")
    parser.add_argument('-f', '--filtercount',
                        type=int,
                        default=4,
                        help='number of filters to use')
    parser.add_argument('-s', '--samplerate',
                        type=int,
                        default=48000,
                        help='sample rate')
    parser.add_argument('-o', '--optimizer',
                        default="default",
                        help='optimizer settings to use')
    parser.add_argument('-c', '--curve',
                        default="flat",
                        help='target curve')
    parser.add_argument("--json",
                        action="store_true")
    parser.add_argument("command",
                        choices=['range', 'optimize'],
                        help="command")
    parser.add_argument("responsefile",
                        help="name of the file that contains the frequency response measurements")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(format='%(levelname)s: %(module)s - %(message)s',
                            level=logging.DEBUG)
        logging.debug("enabled verbose logging")
    else:
        logging.basicConfig(format='%(levelname)s: %(module)s - %(message)s',
                            level=logging.INFO)

    data = read_csv(args.responsefile)

    params = {
        "optimizer": args.optimizer,
        "curve": args.curve,
        "filtercount": args.filtercount
        }

    res = call_api(args.command, data, params)
    if args.json:
        print(res)
    else:
        if args.command == "range":
            print("{}-{}Hz".format(res["f_min"], res["f_max"]))
        elif args.command == "optimize":
            for eq in res["eqdefinitions"]:
                print(eq)


main()
