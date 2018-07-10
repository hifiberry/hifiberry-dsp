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
import urllib.request

from hifiberrydsp.hardware.adau145x import Adau145x
from hifiberrydsp.hardware.sigmatcp import SigmaTCP
from hifiberrydsp.filtering.biquad import Biquad
from hifiberrydsp.filtering.volume import *
from hifiberrydsp.hardware import sigmatcp

from hifiberrydsp.datatools import parse_int, parse_xml


MODE_BOTH = 0
MODE_LEFT = 1
MODE_RIGHT = 2

DISPLAY_FLOAT = 0
DISPLAY_INT = 1
DISPLAY_HEX = 2
DISPLAY_BIN = 2

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


class DSPError(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


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
        self.firleft = None
        self.firright = None
        self.firleft_len = 0
        self.firright_len = 0
        self.checksum = 0

        self.mutegio = None
        self.muteRegister = None
        self.invertmute = False
        self.sigmatcp = SigmaTCP(self.dsp, self.ip)
        parse_xml(self, xmlfile)
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
            parse_xml(self, self.xmlfile)

        except:
            logging.info("Config: Can't read DSP program")

    def set_ip(self, ip):
        self.ip = ip
        self.sigmatcp = SigmaTCP(self.dsp, self.ip)

    def set_volume(self, volume):
        if self.volumectl is not None:
            self.sigmatcp.write_decimal(self.volumectl, volume)

    def set_limit(self, volume):
        if self.volumelimit is not None:
            self.sigmatcp.write_decimal(self.volumelimit, volume)

    def get_volume(self):
        if self.volumectl:
            return self.sigmatcp.read_decimal(self.volumectl)

    def set_balance(self, value):
        '''
        Sets the balance of left/right channels.
        Value ranges from 0 (only left channel) to 2 (only right channel)
        at balance=1 the volume setting on both channels is equal
        '''
        if (value < 0) or (value > 2):
            raise RuntimeError("Balance value must be between 0 and 2")

        if self.balancectl is not None:
            self.sigmatcp.write_decimal(self.balancectl, value)

    def write_biquad(self, index, bq_params, mode=MODE_BOTH):
        if mode == MODE_BOTH or mode == MODE_LEFT:
            addr = self.filterleft[index]
            self.sigmatcp.write_biquad(addr, bq_params)

        if mode == MODE_BOTH or mode == MODE_RIGHT:
            addr = self.filterright[index]
            self.sigmatcp.write_biquad(addr, bq_params)

    def write_fir(self, coefficients, mode=MODE_BOTH):
        if mode == MODE_BOTH or mode == MODE_LEFT:
            self.write_coefficients(self.firleft,
                                    self.firleft_len,
                                    coefficients)

        if mode == MODE_BOTH or mode == MODE_RIGHT:
            self.write_coefficients(self.firright,
                                    self.firright_len,
                                    coefficients)

    def write_coefficients(self, addr, length, coefficients, fill_zero=True):
        if len(coefficients) > length:
            logging.error("Can't deploy coefficients {} > {}",
                          len(coefficients), length)
            return

        data = []
        for coeff in coefficients:
            x = list(self.sigmatcp.get_decimal_repr(coeff))
            print(x)
            data[0:0] = x

        x = list(self.sigmatcp.get_decimal_repr(0))
        for i in range(len(coefficients), length):
            data[0:0] = x

        self.sigmatcp.write_memory(addr, data)

    def get_checksum(self):
        return self.sigmatcp.program_checksum()

    def generic_request(self, request_code, response_code):
        return self.sigmatcp.request_generic(request_code, response_code)

    def set_filters(self, filters, mode=MODE_BOTH):

        index = 0
        if self.filterleft is None:
            l1 = 0
        else:
            l1 = len(self.filterleft)

        if self.filterright is None:
            l2 = 0
        else:
            l2 = len(self.filterright)

        if mode == MODE_LEFT:
            maxlen = l1
        elif mode == MODE_RIGHT:
            maxlen = l2
        else:
            maxlen = min(l1, l2)

        if len(filters) > maxlen:
            raise(DSPError("{} filters given, but filter bank has only {} slots".format(
                len(filters), maxlen)))

        self.hibernate(True)

        for f in filters:
            logging.debug(f)
            self.write_biquad(index, f, mode)
            index += 1

        self.hibernate(False)

    def clear_filters(self, mode=MODE_BOTH):

        self.hibernate(True)

        if mode == MODE_BOTH:
            if (self.filterleft) is None:
                regs = self.filterright
            elif (self.filterright) is None:
                regs = self.filterleft
            else:
                regs = self.filterleft + self.filterright
        elif mode == MODE_LEFT:
            regs = self.filterleft
        elif mode == MODE_RIGHT:
            regs = self.filterright

        if regs is None:
            return

        nullfilter = Biquad.plain()
        for reg in regs:
            self.sigmatcp.write_biquad(reg, nullfilter)

        self.hibernate(False)

    def install_profile(self):
        return self.sigmatcp.write_eeprom(self.xmlfile)

    def mute(self, mute=True):
        if self.muteRegister is not None:
            if mute:
                self.sigmatcp.write_memory(
                    self.muteRegister, self.sigmatcp.int_data(1))
            else:
                self.sigmatcp.write_memory(
                    self.muteRegister, self.sigmatcp.int_data(0))

    def reset(self):
        self.sigmatcp.reset()

    def hibernate(self, hibernate=True):
        self.sigmatcp.hibernate(hibernate)
        time.sleep(0.001)


class CommandLine():

    def __init__(self):
        self.command_map = {
            "store":  self.cmd_store,
            "restore": self.cmd_restore,
            "install-profile": self.cmd_install_profile,
            "set-volume": self.cmd_set_volume,
            "get-volume": self.cmd_get_volume,
            "set-limit": self.cmd_set_limit,
            "get_limit": self.cmd_get_limit,
            "set-rew-filters": self.cmd_set_rew_filters,
            "set-rew-filters-left": self.cmd_set_rew_filters_left,
            "set-rew-filters-right": self.cmd_set_rew_filters_right,
            "set-fir-filters": self.cmd_set_fir_filters,
            "set-fir-filter-right": self.cmd_set_fir_filter_right,
            "set-fir-filter-left": self.cmd_set_fir_filter_left,
            "clear-filters": self.cmd_clear_filters,
            "reset": self.cmd_reset,
            "read-dec": self.cmd_read,
            "loop-read-dec": self.cmd_loop_read_dec,
            "read-int": self.cmd_read_int,
            "loop-read-int": self.cmd_loop_read_int,
            "read-hex": self.cmd_read_hex,
            "loop-read-hex": self.cmd_loop_read_hex,
            "read-reg": self.cmd_read_reg,
            "loop-read-reg": self.cmd_loop_read_reg,
            "get-checksum": self.cmd_checksum,
            "write-reg": self.cmd_write_reg,
            "get-xml": self.cmd_get_xml,
            "get-meta": self.cmd_get_meta
        }
        self.dsptk = DSPToolkit()

    def register_file(self):
        return os.path.expanduser("~/.dsptoolkit/registers.dat")

    def string_to_volume(self, strval):
        strval = strval.lower()
        vol = 0
        if strval.endswith("db"):
            try:
                dbval = float(strval[0:-2])
                vol = decibel2amplification(dbval)
            except:
                logging.error("Can't parse db value {}", strval)
                return None
            # TODO
        elif strval.endswith("%"):
            try:
                pval = float(strval[0:-1])
                vol = percent2amplification(pval)
            except:
                logging.error("Can't parse db value {}", strval)
                return None
        else:
            vol = float(strval)

        return vol

    def read_and_parse_xml(self):
        try:
            parse_xml(self.dsptk, self.dsptk.xmlfile)
        except IOError:
            print("Can't read or parse {}".format(self.dsptk.xmlfile))
            sys.exit(1)

    def cmd_set_volume(self):
        self.read_and_parse_xml()
        if len(self.args.parameters) > 0:
            vol = self.string_to_volume(self.args.parameters[0])
        else:
            print("Volume parameter missing")
            sys.exit(1)

        if vol is not None:
            if self.dsptk.volumectl is None:
                print("Profile doesn't support volume control")
            else:
                self.dsptk.set_volume(vol)
                print("Volume set to {}dB".format(
                    amplification2decibel(vol)))

    def cmd_set_limit(self):
        self.read_and_parse_xml()
        if len(self.args.parameters) > 0:
            vol = self.string_to_volume(self.args.parameters[0])
        else:
            print("Volume parameter missing")
            sys.exit(1)

        if vol is not None:
            if self.dsptk.volumelimit is None:
                print("Profile doesn't support volume control")
            else:
                self.dsptk.set_limit(vol)
            print("Limit set to {}dB".format(amplification2decibel(vol)))

    def cmd_get_volume(self):
        self.read_and_parse_xml()
        vol = self.dsptk.get_volume()
        if vol is not None:
            print("Volume: {:.4f} / {:.0f}% / {:.0f}db".format(
                vol,
                amplification2percent(vol),
                amplification2decibel(vol)))

    def cmd_get_limit(self):
        self.read_and_parse_xml()
        vol = self.dsptk.get_limit()
        if vol is not None:
            print("Limit: {:.4f} / {:.0f}% / {:.0f}db".format(
                vol,
                amplification2percent(vol),
                amplification2decibel(vol)))

    def cmd_read(self, display=DISPLAY_FLOAT, loop=False, length=None):
        self.read_and_parse_xml()
        try:
            addr = parse_int(self.args.parameters[0])
        except:
            print("Can't parse address {}".format(self.args.parameters))
            sys.exit(1)

        while True:
            if display == DISPLAY_FLOAT:
                val = self.dsptk.sigmatcp.read_decimal(addr)
                print("{:.8f}".format(val))
            elif display == DISPLAY_INT:
                val = 0
                for i in self.dsptk.sigmatcp.read_data(addr, length):
                    val *= 256
                    val += i
                print(val)
            elif display == DISPLAY_HEX:
                val = self.dsptk.sigmatcp.read_data(addr, length)
                print(''.join(["%02X " % x for x in val]))

            if not loop:
                break

            try:
                time.sleep(float(self.args.delay) / 1000)
            except KeyboardInterrupt:
                break

    def cmd_loop_read_dec(self):
        self.cmd_read(DISPLAY_FLOAT, True)

    def cmd_read_int(self):
        self.cmd_read(DISPLAY_INT, False)

    def cmd_loop_read_int(self):
        self.cmd_read(DISPLAY_INT, True)

    def cmd_read_hex(self):
        self.cmd_read(DISPLAY_HEX, False)

    def cmd_loop_read_hex(self):
        self.cmd_read(DISPLAY_HEX, True)

    def cmd_read_reg(self):
        self.cmd_read(DISPLAY_HEX,
                      False,
                      self.dsptk.dsp.REGISTER_WORD_LENGTH)

    def cmd_loop_read_reg(self):
        self.cmd_read(DISPLAY_HEX,
                      True,
                      self.dsptk.dsp.REGISTER_WORD_LENGTH)

    def cmd_reset(self):
        self.read_and_parse_xml()
        self.dsptk.reset()
        print("Resetting DSP")

    def cmd_clear_filters(self):
        self.read_and_parse_xml()
        self.dsptk.clear_filters(MODE_BOTH)
        print("Filters removed")

    def cmd_set_rew_filters(self, mode=MODE_BOTH):
        self.read_and_parse_xml()
        filters = REW.readfilters(self.args.value)
        self.dsptk.clear_filters(mode)
        try:
            self.dsptk.set_filters(filters, mode)
            print("Filters configured on both channels:")
            for f in filters:
                print (f.description)
        except DSPError as e:
            print(e)

    def cmd_set_rew_filters_left(self):
        self.set_rew_filters(mode=MODE_LEFT)

    def cmd_set_rew_filters_right(self):
        self.set_rew_filters(mode=MODE_RIGHT)

    def cmd_set_fir_filters(self, mode=MODE_BOTH):
        self.read_and_parse_xml()
        if len(self.args.parameters) > 0:
            filename = self.args.parameters[0]
        else:
            print("FIR filename missing")
            sys.exit(1)

        coefficients = []
        with open(filename) as firfile:
            for line in firfile:
                coeff = float(line)
                coefficients.append(coeff)

        self.dsptk.hibernate(True)
        self.dsptk.write_fir(coefficients, mode)
        self.dsptk.hibernate(False)

    def cmd_set_fir_filter_left(self):
        self.cmd_set_fir_filters(MODE_LEFT)

    def cmd_set_fir_filter_right(self):
        self.cmd_set_fir_filters(MODE_RIGHT)

    def cmd_checksum(self):
        checksum = self.dsptk.sigmatcp.program_checksum()

        print(''.join(["%02X" % x for x in checksum]))

    def cmd_get_xml(self):
        xml = self.dsptk.generic_request(sigmatcp.COMMAND_XML,
                                         sigmatcp.COMMAND_XML_RESPONSE)
        print(xml.decode("utf-8", errors="replace"))

    def cmd_get_meta(self):
        if len(self.args.parameters) > 0:
            attribute = self.args.parameters[0]
        value = self.dsptk.sigmatcp.request_metadata(attribute)
        print(value.decode("utf-8"))

    def cmd_store(self):
        self.dsptk.generic_request(sigmatcp.COMMAND_STORE_DATA)

    def cmd_restore(self):
        self.dsptk.generic_request(sigmatcp.COMMAND_RESTORE_DATA)

    def cmd_install_profile(self):
        self.read_and_parse_xml()
        if len(self.args.parameters) > 0:
            filename = self.args.parameters[0]
        else:
            print("profile filename missing")
            sys.exit(1)

        default_location = self.dsptk.xmlfile
        if (filename.startswith("http://") or
                filename.startswith("https://")):
            # Download and store a local copy
            try:
                localname = os.path.expanduser(
                    "~/.dsptoolkit/" + os.path.basename(filename))
                urllib.request.urlretrieve(filename, localname)
                defaultname = self.dsptk.xmlfile
                shutil.copy(localname, self.dsptk.xmlfile)
                print("Stored profile {} as {}".format(
                    localname, defaultname))
                filename = localname
            except IOError:
                print("Couldn't download {}".format(filename))
                sys.exit(1)
        self.dsptk.xmlfile = filename
        res = self.dsptk.install_profile()
        if res:
            print("DSP profile {} installed".format(filename))
        else:
            print("Failed to install DSP profile {}".format(self.dsptk.xmlfile))

    def cmd_write_reg(self):
        if len(self.args.parameters) > 1:
            reg = parse_int(self.args.parameters[0])
            value = parse_int(self.args.parameters[1])
        else:
            print("parameter missing, need addr value")

        data = [(value >> 8) & 0xff, value & 0xff]
        self.dsptk.sigmatcp.write_memory(reg, data)
        sys.exit(1)

    def main(self):

        parser = argparse.ArgumentParser(description='HiFiBerry DSP toolkit')
        parser.add_argument('--delay',
                            help='delay for loop operations in ms',
                            nargs='?',
                            type=int,
                            default=1000)
        parser.add_argument('command',
                            choices=sorted(self.command_map.keys()))
        parser.add_argument('parameters', nargs='*')

        self.args = parser.parse_args()

        self.dsptk.read_config()

        if self.dsptk.xmlfile is None:
            self.dsptk.xmlfile = os.path.expanduser(
                "~/.dsptoolkit/dspprogram.xml")

        self.command_map[self.args.command]()


if __name__ == "__main__":
    cmdline = CommandLine()
    cmdline.main()
