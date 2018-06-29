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

COMMAND_READ = 0x0a
COMMAND_WRITE = 0x09
COMMAND_EEPROM = 0xf0

HEADER_SIZE = 14

DEFAULT_PORT = 8086

MAX_READ_SIZE = 1024 * 2


class SigmaTCPException(IOError):

    def __init__(self, message):
        super(SigmaTCPException, self).__init__(message)


class SigmaTCP():

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

    def write_memory(self, addr, data):
        if self.socket is None:
            if self.autoconnect:
                self.connect()
            else:
                raise SigmaTCPException("Not connected")

        packet = self.write_request(addr, data)
        print(addr, data)
        self.socket.send(packet)

    def write_decimal(self, addr, value):
        data = self.dsp.decimal_repr(value)
        self.write_memory(addr, self.int_data(data,
                                              self.dsp.DECIMAL_LEN))

    def read_decimal(self, addr):
        data = self.read_memory(addr, self.dsp.DECIMAL_LEN)
        return self.dsp.decimal_val(self.data_int(data))

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
        packet[9] = length & 0xff
        packet[8] = (length >> 8) & 0xff
        packet[11] = addr & 0xff
        packet[10] = (addr >> 8) & 0xff
        return packet

    def write_request(self, addr, data):
        length = len(data)
        packet = bytearray(HEADER_SIZE)
        packet[0] = COMMAND_WRITE
        packet[11] = length & 0xff
        packet[10] = (length >> 8) & 0xff
        packet[13] = addr & 0xff
        packet[12] = (addr >> 8) & 0xff
        for d in data:
            packet.append(d)
        return packet

    def reset(self):
        (register, length) = self.dsp.reset_register()
        self.write_memory(register, self.int_data(0, length))
        time.sleep(0.5)
        self.write_memory(register, self.int_data(1, length))

    def hibernate(self, onoff):
        (register, length) = self.dsp.hibernate_register()
        if onoff:
            self.write_memory(register, self.int_data(1, length))
        else:
            self.write_memory(register, self.int_data(0, length))

    def int_data(self, intval, length=4):
        octets = bytearray()
        for i in range(length, 0, -1):
            octets.append((intval >> (i - 1) * 8) & 0xff)

        return octets

    def data_int(self, data):
        res = 0
        for d in data:
            res = res * 256
            res += d
        return res
