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
import xmltodict

ATTRIBUTE_CHECKSUM = "checksum"
ATTRIBUTE_VOL_CTL = "volumeControlRegister"
ATTRIBUTE_VOL_LIMIT = "volumeLimitRegister"
ATTRIBUTE_BALANCE = "balanceRegister"
ATTRIBUTE_VOL_RANGE = "volumeControlRangeDb"
ATTRIBUTE_IIR_FILTER_LEFT = "customFilterBankLeft"
ATTRIBUTE_IIR_FILTER_RIGHT = "customFilterBankRight"
ATTRIBUTE_FIR_FILTER_LEFT = "customFirFilterLeft"
ATTRIBUTE_FIR_FILTER_RIGHT = "customFirFilterRight"
ATTRIBUTE_MUTE_REG = "muteRegister"


def parse_int(val):
    if val.startswith("0x"):
        return int(val, 16)
    else:
        return int(val)


def parse_meta_int(metadata):
    try:
        return parse_int(metadata["#text"])
    except:
        logging.error("can't parse metadata %s", metadata["@type"])
        return None


def parse_meta_int_length(metadata):
    try:
        strval = metadata["#text"]
        (addr, length) = strval.split("/")

        addr = parse_int(addr)
        length = parse_int(length)

    except:
        addr = None
        length = 0
        logging.error("can't parse metadata %s", metadata["@type"])

    return (addr, length)


def parse_int_list(metadata):
    try:
        res = []
        vals = metadata["#text"].split(",")
        for v in vals:
            if v.startswith("0x"):
                res.append(int(v, 16))
            else:
                res.append(int(v))
        return res
    except:
        logging.error("can't parse metadata %s", metadata["@type"])
        return None


def parse_xml(resultObject, xmlfile):

    if xmlfile is None:
        return

    with open(xmlfile) as fd:
        doc = xmltodict.parse(fd.read())

    resultObject.volumectl = None
    resultObject.volumelimit = None
    resultObject.filterleft = None
    resultObject.filterright = None
    resultObject.muteRegister = None
    resultObject.volctlrange = None
    resultObject.balancectl = None
    resultObject.firleft = None
    resultObject.firright = None
    resultObject.firleft_len = 0
    resultObject.firright_len = 0

    for metadata in doc["ROM"]["beometa"]["metadata"]:
        t = metadata["@type"]

        if (t == ATTRIBUTE_CHECKSUM):
            resultObject.checksum = metadata["#text"]

        if (t == ATTRIBUTE_VOL_CTL):
            resultObject.volumectl = parse_meta_int(metadata)

        if (t == ATTRIBUTE_VOL_LIMIT):
            resultObject.volumelimit = parse_meta_int(metadata)

        if (t == ATTRIBUTE_BALANCE):
            resultObject.balancectl = parse_meta_int(metadata)

        if (t == ATTRIBUTE_VOL_RANGE):
            try:
                strval = metadata["#text"]
                resultObject.volctlrange = float(strval)
            except:
                logging.error("Can't parse metadata volumeControlRangeDb")

        if (t == ATTRIBUTE_IIR_FILTER_LEFT):
            resultObject.filterleft = parse_int_list(metadata)

        if (t == ATTRIBUTE_IIR_FILTER_RIGHT):
            resultObject.filterright = parse_int_list(metadata)

        if (t == ATTRIBUTE_FIR_FILTER_LEFT):
            (resultObject.firleft,
             resultObject.firleft_len) = parse_meta_int_length(metadata)

        if (t == ATTRIBUTE_FIR_FILTER_RIGHT):
            (resultObject.firright,
             resultObject.firright_len) = parse_meta_int_length(metadata)

        if (t == ATTRIBUTE_MUTE_REG):
            resultObject.muteRegister = resultObject.parse_meta_int(metadata)
