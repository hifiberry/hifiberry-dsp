#!/usr/bin/env python3

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
import argparse
import os
import time
import shutil
import sys

from hifiberrydsp.hardware.adau145x import Adau145x
from hifiberrydsp.hardware.sigmatcp import SigmaTCP
from hifiberrydsp.filtering.biquad import Biquad
from hifiberrydsp.filtering.volume import *

MODE_BOTH = 0
MODE_LEFT = 1
MODE_RIGHT = 2

GLOBAL_REGISTER_FILE = "/etc/dspparameter.dat"
GLOBAL_PROGRAM_FILE = "/etc/dspprogram.xml"


class REW():

    def __init__(self):
        pass

    @staticmethod
    def readfilters(filename, fs=48000):
        filters = []

        with open(filename) as file:
            for line in file.readlines():
                if line.startswith("Filter"):
                    parts = line.split()
                    if len(parts) >= 12 and parts[2] == "ON" and \
                            parts[4] == "Fc" and parts[6] == "Hz" and \
                            parts[7] == "Gain" and parts[9] == "dB" and \
                            parts[10] == "Q":

                        fc = float(parts[5])
                        gain = float(parts[8])
                        q = float(parts[11])
                        logging.info("Filter fc=%s, q=%s, gaion=%s, fs=%s",
                                     fc, q, gain, fs)
                        filters.append(
                            Biquad.peaking_eq(fc, q, gain, fs))

            return filters


class DSPToolkit():

    def __init__(self,
                 xmlfile=None,
                 ip="127.0.0.1",
                 dsp=Adau145x()):
        self.dsp = dsp
        self.xmlfile = xmlfile
        self.ip = ip
        self.volumectl = None
        self.volumelimit = None
        self.volctlrange = 60
        self.filterleft = []
        self.filterright = []
        self.mutegio = None
        self.muteRegister = None
        self.invertmute = False
        self.sigmatcp = SigmaTCP(self.dsp, self.ip)
        self.parse_xml()
        self.resetgpio = None

    def read_config(self, configfile="~/.dsptoolkit/dsptoolkit.conf"):
        import configparser
        config = configparser.ConfigParser()
        try:
            config.read(os.path.expanduser(configfile))
        except Exception as e:
            logging.info("Can't read config file %s (%s)",
                         configfile, e)

        try:
            self.set_ip(config["host"].get("ip"))

        except:
            logging.info("Config: IP not defined")

        try:
            self.resetgpio = int(config["dsp"].get("reset_gpio"))
        except:
            logging.info("Config: Reset GPIO not defined")

        try:
            self.xmlfile = os.path.expanduser(config["dsp"].get("program"))
            # If there is an program defined, parse it
            self.parse_xml()
        except:
            logging.info("Config: Can't read DSP program")

    def parse_xml(self):
        import xmltodict

        if self.xmlfile is None:
            return

        with open(self.xmlfile) as fd:
            doc = xmltodict.parse(fd.read())

        self.volumectl = None
        self.volumelimit = None
        self.filterleft = None
        self.filterright = None
        self.muteRegister = None
        self.volctlrange = None

        for metadata in doc["ROM"]["beometa"]["metadata"]:
            t = metadata["@type"]

            if (t == "volumeControlRegister"):
                self.volumectl = self.parse_int(metadata)

            if (t == "volumeLimitRegister"):
                self.volumelimit = self.parse_int(metadata)

            if (t == "volumeControlRangeDb"):
                try:
                    strval = metadata["#text"]
                    self.volctlrange = float(strval)
                except:
                    logging.error("Can't parse metadata volumeControlRangeDb")

            if (t == "customFilterBankLeft"):
                self.filterleft = self.parse_int_list(metadata)

            if (t == "customFilterBankRight"):
                self.filterright = self.parse_int_list(metadata)

            if (t == "muteRegister"):
                self.muteRegister = self.parse_int(metadata)

        self._collect_registers()

    def set_ip(self, ip):
        self.ip = ip
        self.sigmatcp = SigmaTCP(self.dsp, self.ip)

    def parse_int(self, metadata):
        try:
            strval = metadata["#text"]
            if strval.startswith("0x"):
                return int(strval, 16)
            else:
                return int(strval)
        except:
            logging.error("Can't parse metadata %s", metadata["@type"])
            return None

    def parse_int_list(self, metadata):
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
            logging.error("Can't parse metadata %s", metadata["@type"])
            return None

    def set_volume(self, volume):
        if self.volumectl is not None:
            self.sigmatcp.write_decimal(self.volumectl, volume)

    def set_limit(self, volume):
        if self.volumelimit is not None:
            self.sigmatcp.write_decimal(self.volumelimit, volume)

    def get_volume(self):
        if self.volumectl:
            return self.sigmatcp.read_decimal(self.volumectl)

    def write_biquad(self, index, bq_params, mode=MODE_BOTH):
        if mode == MODE_BOTH or mode == MODE_LEFT:
            addr = self.filterleft[index]
            #print(addr, bq_params)
            self.sigmatcp.write_biquad(addr, bq_params)

        if mode == MODE_BOTH or mode == MODE_RIGHT:
            addr = self.filterright[index]
            #print(addr, bq_params)
            self.sigmatcp.write_biquad(addr, bq_params)

    def store_values(self, filename):
        with open(filename, "w") as outfile:
            for reg in self.registers:
                length = self.registers[reg]
                data = self.sigmatcp.data_int(
                    self.sigmatcp.read_memory(reg, length))
                outfile.write("{}:{}:{}\n".format(reg, length, data))

    def read_values(self, filename):
        with open(filename, "r") as infile:
            self.mute(True)
            for line in infile:
                try:
                    [addr, length, data] = line.split(":")
                    addr = int(addr)
                    length = int(length)
                    data = self.sigmatcp.int_data(int(data), length)
                    self.sigmatcp.write_memory(addr, data)
                except:
                    pass
            self.mute(False)

    def set_filters(self, filters, mode=MODE_BOTH):
        index = 0
        for f in filters:
            logging.debug(f)
            self.write_biquad(index, f, mode)
            index += 1
        time.sleep(1)

    def clear_filters(self, mode=MODE_BOTH):

        if mode == MODE_BOTH:
            regs = self.filterleft + self.filterright
        elif mode == MODE_LEFT:
            regs = self.filterleft
        elif mode == MODE_RIGHT:
            regs = self.filterright

        nullfilter = Biquad.plain()
        for reg in regs:
            self.sigmatcp.write_biquad(reg, nullfilter)

    def mute(self, mute=True):
        if self.muteRegister is not None:
            if mute:
                self.sigmatcp.write_memory(
                    self.muteRegister, self.sigmatcp.int_data(1))
            else:
                self.sigmatcp.write_memory(
                    self.muteRegister, self.sigmatcp.int_data(0))

    def _collect_registers(self):
        '''
        Create a list of registers that are managed by the DSP toolkit
        This is used to store/restore the data
        '''
        self.registers = {}
        if self.volumectl is not None:
            self.registers[self.volumectl] = self.dsp.DECIMAL_LEN
        if self.volumelimit is not None:
            self.registers[self.volumectl] = self.dsp.DECIMAL_LEN
        for reg in self.filterleft + self.filterright:
            for i in range(0, 5):
                self.registers[reg + i] = self.dsp.DECIMAL_LEN

    def reset(self):
        self.sigmatcp.reset()

    def hibernate(self, hibernate=True):
        self.sigmatcp.hibernate(hibernate)
        time.sleep(0.5)


def register_file():
    return os.path.expanduser("~/.dsptoolkit/registers.dat")


def string_to_volume(strval):
    strval = strval.lower()
    vol = 0
    if strval.endswith("db"):
        try:
            dbval = - float(strval[0:-2])
            print(dbval)
            vol = decibel2amplification(dbval)
        except:
            logging.error("Can't parse db value {}", strval)
            return None
        # TODO
    elif strval.endswith("%"):
        try:
            pval = - float(strval[0:-1])
            print(pval)
            vol = percent2amplification(pval)
        except:
            logging.error("Can't parse db value {}", strval)
            return None
    else:
        vol = float(strval)

    return vol


def print_filters(filters):
    for f in filters:
        print (f.description)


def main():

    parser = argparse.ArgumentParser(description='HiFiBerry DSP toolkit')
    parser.add_argument('value', nargs='?')
    parser.add_argument('--command', dest='command',
                        choices=["store", "restore",
                                 "store-global", "restore-global"
                                 "set-volume", "get-volume",
                                 "set-limit", "get_limit",
                                 "set-rew-filters",
                                 "set-rew-filters-left",
                                 "set-rew-filters-right",
                                 "clear-filters",
                                 "reset"],
                        help='command')

    args = parser.parse_args()
    dsptk = DSPToolkit()
    dsptk.read_config()

    if dsptk.xmlfile is None:
        dsptk.xmlfile = os.path.expanduser("~/.dsptoolkit/dspprogram.xml")

    try:
        dsptk.parse_xml()
    except IOError:
        print("Can't read or parse {}".format(dsptk.xmlfile))
        sys.exit(1)

    if args.command == "store":
        dsptk.store_values(register_file())
        print("Settings stored to {}".format(register_file()))
    elif args.command == "restore":
        dsptk.mute(True)
        dsptk.hibernate(True)
        dsptk.read_values(register_file())
        dsptk.hibernate(False)
        dsptk.mute(False)
        print("Settings restored from {}".format(register_file()))
    elif args.command == "store-global":
        dsptk.store_values(GLOBAL_REGISTER_FILE)
        shutil.copy(dsptk.xmlfile, GLOBAL_REGISTER_FILE)
        print("Settings stored to {}".format(GLOBAL_REGISTER_FILE))
        print("DSP program copied to {}".format(GLOBAL_REGISTER_FILE))
    elif args.command == "restore-global":
        dsptk.xmlfile = GLOBAL_PROGRAM_FILE
        dsptk.parse_xml()
        dsptk.mute(True)
        dsptk.hibernate(True)
        dsptk.read_values(GLOBAL_REGISTER_FILE)
        dsptk.hibernate(False)
        dsptk.mute(False)
        print("Settings restored from {},{}".format(GLOBAL_PROGRAM_FILE,
                                                    GLOBAL_REGISTER_FILE))
    elif args.command == "set-volume":
        vol = string_to_volume(args.value)
        if vol is not None:
            dsptk.set_volume(vol)
            print("Volume set to {}dB".format(amplification2decibel(vol)))
    elif args.command == "set-limit":
        vol = string_to_volume(args.value)
        if vol is not None:
            dsptk.set_limit(vol)
            print("Limit set to {}dB".format(amplification2decibel(vol)))
    elif args.command == "get-volume":
        vol = dsptk.get_volume()
        if vol is not None:
            print("Volume: {:.4f} / {:.0f}% / {:.0f}db".format(
                vol,
                amplification2percent(vol),
                amplification2decibel(vol)))
    elif args.command == "reset":
        dsptk.reset()
        print("Resetting DSP")
    elif args.command == "clear-filters":
        dsptk.mute(True)
        dsptk.hibernate(True)
        dsptk.clear_filters(MODE_BOTH)
        dsptk.hibernate(False)
        dsptk.mute(False)
        print("Filters removed")
    elif args.command == "set-rew-filters":
        dsptk.mute(True)
        dsptk.hibernate(True)
        filters = REW.readfilters(args.value)
        dsptk.clear_filters(MODE_BOTH)
        dsptk.set_filters(filters, MODE_BOTH)
        print("Filters configured on both channels:")
        print_filters(filters)
        dsptk.hibernate(False)
        dsptk.mute(False)
    elif args.command == "set-rew-filters-left":
        dsptk.mute(True)
        dsptk.hibernate(True)
        filters = REW.readfilters(args.value)
        dsptk.clear_filters(MODE_LEFT)
        filters = dsptk.set_filters(filters, MODE_LEFT)
        print("Filters configured on left channel:")
        print_filters(filters)
        dsptk.hibernate(False)
        dsptk.mute(False)
    elif args.command == "set-rew-filters-right":
        dsptk.mute(True)
        dsptk.hibernate(True)
        filters = REW.readfilters(args.value)
        dsptk.clear_filters(MODE_RIGHT)
        dsptk.set_filters(filters, MODE_RIGHT)
        print("Filters configured on right channel:")
        print_filters(filters)
        dsptk.hibernate(False)
        dsptk.mute(False)


if __name__ == "__main__":
    main()
