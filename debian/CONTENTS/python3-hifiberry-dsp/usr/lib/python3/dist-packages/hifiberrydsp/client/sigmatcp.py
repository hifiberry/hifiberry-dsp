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

import socket
import time
import os
import logging


from hifiberrydsp.datatools import int_data
from hifiberrydsp import datatools

from hifiberrydsp.server.constants import \
    COMMAND_READ, COMMAND_WRITE, COMMAND_EEPROM_FILE, COMMAND_CHECKSUM, \
    COMMAND_WRITE_EEPROM_CONTENT, COMMAND_GET_META, \
    COMMAND_META_RESPONSE, COMMAND_GPIO, COMMAND_GPIO_RESPONSE, \
    DEFAULT_PORT, \
    HEADER_SIZE, \
    SigmaTCPException


class SigmaTCPClient():

    def __init__(self, dsp, ip, port=DEFAULT_PORT, autoconnect=True):
        self.ip = ip
        self.port = port
        self.dsp = dsp
        self.autoconnect = autoconnect
        self.socket = None

    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.ip, self.port))
        except IOError:
            self.socket = None
            raise SigmaTCPException(
                "Could not connect to {}:{}".format(self.ip, self.port))

    def disconnect(self):
        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def read_memory(self, addr, length):
        if self.socket is None:
            if self.autoconnect:
                self.connect()
            else:
                raise SigmaTCPException("Not connected")

        packet = self.read_request(addr, length)
        self.socket.send(packet)
        data = self.socket.recv(HEADER_SIZE + length)
        # remove the header
        data = data[HEADER_SIZE:]
        return data

    def program_checksum(self):
        if self.socket is None:
            if self.autoconnect:
                self.connect()
            else:
                raise SigmaTCPException("Not connected")

        packet = self.generic_request(COMMAND_CHECKSUM)
        self.socket.send(packet)
        data = self.socket.recv(HEADER_SIZE + 16)
        # remove the header
        data = data[HEADER_SIZE:]
        return data

    def readwrite_gpio(self, rw, pin, value):
        if self.socket is None:
            if self.autoconnect:
                self.connect()
            else:
                raise SigmaTCPException("Not connected")

        packet = self.gpio_request(rw, pin, value)
        self.socket.send(packet)
        data = self.socket.recv(HEADER_SIZE + 1)
        # remove the header
        data = data[HEADER_SIZE:]
        return data

    def write_memory(self, addr, data):
        if self.socket is None:
            if self.autoconnect:
                self.connect()
            else:
                raise SigmaTCPException("Not connected")

        packet = self.write_request(addr, data)
        self.socket.send(packet)

    def write_eeprom_from_file(self, filename):
        if self.socket is None:
            if self.autoconnect:
                self.connect()
            else:
                raise SigmaTCPException("Not connected")

        if (os.path.exists(filename)):
            packet = self.write_eeprom_file_request(os.path.abspath(filename))
            self.socket.send(packet)
            result = int.from_bytes(self.socket.recv(1),
                                    byteorder='big',
                                    signed=False)
            if result == 1:
                return(True)
            else:
                return False
        else:
            raise IOError("{} does not exist".format(filename))

    def write_eeprom_from_xml(self, xmldata):
        if self.socket is None:
            if self.autoconnect:
                self.connect()
            else:
                raise SigmaTCPException("Not connected")

        packet = self.write_eeprom_content_request(xmldata)
        self.socket.send(packet)
        result = int.from_bytes(self.socket.recv(1),
                                byteorder='big',
                                signed=False)
        if result == 1:
            return(True)
        else:
            return False

    def get_decimal_repr(self, value):
        data = self.dsp.decimal_repr(value)
        return int_data(data, self.dsp.DECIMAL_LEN)

    def write_decimal(self, addr, value):
        self.write_memory(addr, self.get_decimal_repr(value))

    def read_decimal(self, addr):
        data = self.read_memory(addr, self.dsp.DECIMAL_LEN)
        return self.dsp.decimal_val(self.data_int(data))

    def read_data(self, addr, length=None):
        if length == None:
            length = self.dsp.DECIMAL_LEN
        return self.read_memory(addr, length)

    def write_biquad(self, start_addr, bq):

        bqn = bq.normalized()
        bq_params = []
        bq_params.append(-bqn.a1)
        bq_params.append(-bqn.a2)
        bq_params.append(bqn.b0)
        bq_params.append(bqn.b1)
        bq_params.append(bqn.b2)

        reg = start_addr + 4
        for param in bq_params:
            self.write_decimal(reg, param)
            reg = reg - 1

        # reset a1/a2 to their original values
        bq_params[0] = -bq_params[0]
        bq_params[1] = -bq_params[1]

    def write_decibel(self, addr, db):
        amplification = pow(10, db / 20)
        self.write_decimal(addr, amplification)

    def read_request(self, addr, length):
        packet = bytearray(HEADER_SIZE)
        packet[0] = COMMAND_READ
        packet[4] = 14  # packet length
        packet[9] = length & 0xff
        packet[8] = (length >> 8) & 0xff
        packet[11] = addr & 0xff
        packet[10] = (addr >> 8) & 0xff

        return packet

    @staticmethod
    def metadata_request(attribute):
        attribute = attribute.encode("utf-8")
        length = 14 + len(attribute)
        packet = bytearray(HEADER_SIZE)
        packet[0] = COMMAND_GET_META
        packet[3] = (length >> 8) & 0xff
        packet[4] = length & 0xff
        return packet + attribute

    @staticmethod
    def gpio_request(readwrite, pin, value):
        length = 17
        packet = bytearray(length)
        packet[0] = COMMAND_GPIO
        packet[3] = (length >> 8) & 0xff
        packet[4] = length & 0xff
        packet[14] = readwrite
        packet[15] = pin
        packet[16] = value
        return packet

    @staticmethod
    def write_request(addr, data):
        length = len(data)
        packet = bytearray(HEADER_SIZE)
        packet[0] = COMMAND_WRITE
        packet[11] = length & 0xff
        packet[10] = (length >> 8) & 0xff
        packet[13] = addr & 0xff
        packet[12] = (addr >> 8) & 0xff
        for d in data:
            packet.append(d)

        packet_length = len(packet)
        packet[6] = packet_length & 0xff
        packet[5] = (packet_length >> 8) & 0xff

        return packet

    def request_generic(self, request_code, response_code=None):
        if self.socket is None:
            if self.autoconnect:
                self.connect()
            else:
                raise SigmaTCPException("Not connected")

        packet = self.generic_request(request_code)
        self.socket.send(packet)

        if response_code is not None:
            # read header and get length field
            data = self.socket.recv(HEADER_SIZE)
            length = int.from_bytes(data[6:10], byteorder='big')

            if (data[0] != response_code):
                logging.error("Expected response code %s, but got %s",
                              response_code,
                              data[0])

            # read data
            data = bytearray()
            while (len(data) < length):
                packet = self.socket.recv(length - len(data))
                data = data + packet

            return data

    def request_metadata(self, attribute):
        if self.socket is None:
            if self.autoconnect:
                self.connect()
            else:
                raise SigmaTCPException("Not connected")

        packet = self.metadata_request(attribute)
        self.socket.send(packet)

        data = self.socket.recv(HEADER_SIZE)
        length = int.from_bytes(data[6:10], byteorder='big')

        if (data[0] != COMMAND_META_RESPONSE):
            logging.error("Expected response code %s, but got %s",
                          COMMAND_META_RESPONSE,
                          data[0])
            return

        # read data
        data = bytearray()
        while (len(data) < length):
            packet = self.socket.recv(length - len(data))
            data = data + packet

        return data.decode("utf-8")

    @staticmethod
    def write_eeprom_file_request(filename):
        packet = bytearray(HEADER_SIZE)
        packet[0] = COMMAND_EEPROM_FILE
        packet[1] = len(filename)
        packet.extend(map(ord, filename))
        packet.extend([0])
        return packet

    @staticmethod
    def write_eeprom_content_request(data):
        if isinstance(data, str):
            data = data.encode("utf-8")

        packet = bytearray(HEADER_SIZE)
        packet[0] = COMMAND_WRITE_EEPROM_CONTENT
        packet[3:7] = datatools.int_data(len(data) + HEADER_SIZE, 4)
        packet.extend(bytearray(data))
        return packet

    @staticmethod
    def generic_request(request_type):
        packet = bytearray(HEADER_SIZE)
        packet[0] = request_type
        return packet

    def reset(self):
        self.write_memory(self.dsp.RESET_REGISTER,
                          int_data(0, self.dsp.REGISTER_WORD_LENGTH))
        time.sleep(0.5)
        self.write_memory(self.dsp.RESET_REGISTER,
                          int_data(1, self.dsp.REGISTER_WORD_LENGTH))

    def hibernate(self, onoff):
        if onoff:
            self.write_memory(self.dsp.HIBERNATE_REGISTER,
                              int_data(1, self.dsp.REGISTER_WORD_LENGTH))
        else:
            self.write_memory(self.dsp.HIBERNATE_REGISTER,
                              int_data(0, self.dsp.REGISTER_WORD_LENGTH))

    def data_int(self, data):
        res = 0
        for d in data:
            res = res * 256
            res += d
        return res
