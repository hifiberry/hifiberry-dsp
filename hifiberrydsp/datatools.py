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

import logging


def parse_frequency(f_str):
    f_str = f_str.lower()
    if f_str.endswith("hz"):
        f_str = f_str[0:-2]
    return float(f_str)


def parse_decibel(dbstr):
    dbstr = dbstr.lower()
    dbstr = dbstr.strip()
    if dbstr.endswith("db"):
        dbstr = dbstr[0:-2]
    return float(dbstr)


def parse_int(val):
    if val is None or len(val) == 0:
        return

    if val.startswith("0x"):
        return int(val, 16)
    else:
        return int(val)


def parse_int_length(val):
    if val is None or len(val) == 0:
        return (None, 0)

    try:
        if "/" in val:
            (addr, length) = val.split("/")
            addr = parse_int(addr)
            length = parse_int(length)
        else:
            addr = parse_int(val)
            length = 1
    except:
        addr = None
        length = 0
        logging.error("can't parse metadata %s", val)

    return (addr, length)


def parse_int_list(val):
    if val is None or val == "":
        return []

    try:
        res = []
        for v in val.split(","):
            if v.startswith("0x"):
                res.append(int(v, 16))
            else:
                res.append(int(v))
        return res
    except:
        logging.error("can't parse list %s", val)
        return None


def int_data(intval, length=4):
    octets = bytearray()
    for i in range(length, 0, -1):
        octets.append((intval >> (i - 1) * 8) & 0xff)

    return octets
