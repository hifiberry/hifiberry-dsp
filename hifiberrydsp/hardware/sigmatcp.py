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
import hashlib
import tempfile
import shutil
import getpass

from socketserver import BaseRequestHandler, TCPServer, ThreadingMixIn

import xmltodict
from hifiberrydsp.hardware import adau145x
from hifiberrydsp.datatools import parse_xml

# Original SigmaDSP operations
COMMAND_READ = 0x0a
COMMAND_READRESPONSE = 0x0b
COMMAND_WRITE = 0x09

# additional functionalities
COMMAND_EEPROM_FILE = 0xf0
COMMAND_CHECKSUM = 0xf1
COMMAND_CHECKSUM_RESPONSE = 0xf2
COMMAND_WRITE_EEPROM_CONTENT = 0xf3
COMMAND_XML = 0xf4
COMMAND_XML_RESPONSE = 0xf5
COMMAND_STORE_DATA = 0xf6
COMMAND_RESTORE_DATA = 0xf6
COMMAND_GET_META = 0xf7
COMMAND_META_RESPONSE = 0xf8
COMMAND_PROGMEM = 0xf9
COMMAND_PROGMEM_RESPONSE = 0xfa

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

    def write_memory(self, addr, data):
        if self.socket is None:
            if self.autoconnect:
                self.connect()
            else:
                raise SigmaTCPException("Not connected")

        packet = self.write_request(addr, data)
        self.socket.send(packet)

    def write_eeprom(self, filename):
        if self.socket is None:
            if self.autoconnect:
                self.connect()
            else:
                raise SigmaTCPException("Not connected")

        if (os.path.exists(filename)):
            packet = self.write_eeprom_request(os.path.abspath(filename))
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

    def get_decimal_repr(self, value):
        data = self.dsp.decimal_repr(value)
        return SigmaTCP.int_data(data, self.dsp.DECIMAL_LEN)

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

        return data

    @staticmethod
    def write_eeprom_request(filename):
        packet = bytearray(HEADER_SIZE)
        packet[0] = COMMAND_EEPROM_FILE
        packet[1] = len(filename)
        packet.extend(map(ord, filename))
        packet.extend([0])
        return packet

    @staticmethod
    def generic_request(request_type):
        packet = bytearray(HEADER_SIZE)
        packet[0] = request_type
        return packet

    def reset(self):
        self.write_memory(self.dsp.RESET_REGISTER,
                          SigmaTCP.int_data(0, self.dsp.REGISTER_WORD_LENGTH))
        time.sleep(0.5)
        self.write_memory(self.dsp.RESET_REGISTER,
                          SigmaTCP.int_data(1, self.dsp.REGISTER_WORD_LENGTH))

    def hibernate(self, onoff):
        if onoff:
            self.write_memory(self.dsp.HIBERNATE_REGISTER,
                              SigmaTCP.int_data(1, self.dsp.REGISTER_WORD_LENGTH))
        else:
            self.write_memory(self.dsp.HIBERNATE_REGISTER,
                              SigmaTCP.int_data(0, self.dsp.REGISTER_WORD_LENGTH))

    @staticmethod
    def int_data(intval, length=4):
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


class DSPFileStore():

    def __init__(self):
        if (getpass.getuser() == 0):
            self.dspprogramfile = "/etc/dspprogram.xml"
            self.paramaterfile = "/etc/dspparameters.dat"
        else:
            self.dspprogramfile = os.path.expanduser(
                "~/.dsptoolkit/dspprogram.xml")
            self.paramaterfile = os.path.expanduser(
                "~/.dsptoolkit/dspparameters.dat")

    def store_parameters(self, checksum, memory):
        with open(self.paramaterfile, "wb") as datafile:
            datafile.write(checksum)
            datafile.write(memory)

    def restore_parameters(self, checksum):
        with open(self.paramaterfile, "rb") as datafile:
            file_checksum = datafile.read(16)
            logging.debug("Checking checksum %s/%s",
                          checksum, file_checksum)
            if checksum != file_checksum:
                logging.error("checksums do not match, aborting")
                return

            return datafile.read()


class SigmaTCPHandler(BaseRequestHandler):

    spi = None

    def __init__(self, request, client_address, server):
        logging.debug("__init__")
        self.filestore = DSPFileStore()

        BaseRequestHandler.__init__(self, request, client_address, server)

    def setup(self):
        import spidev

        logging.debug("setup")
        if SigmaTCPHandler.spi is None:
            SigmaTCPHandler.spi = spidev.SpiDev()
            SigmaTCPHandler.spi.open(0, 0)
            SigmaTCPHandler.spi.bits_per_word = 8
            SigmaTCPHandler.spi.max_speed_hz = 1000000
            SigmaTCPHandler.spi.mode = 0
            logging.debug("spi initialized %s", self.spi)

        self.dsp = adau145x.Adau145x

        logging.debug("setup finished")

    def handle(self):

        if self.request is None:
            # Not a real request to handle:
            return

        logging.debug('handle')
        finished = False
        data = None
        read_more = False

        while not(finished):
            # Read dara
            try:
                buffer = None

                if data is None:
                    data = self.request.recv(65536)
                    if len(data) == 0:
                        finished = True
                        continue

                if read_more:
                    logging.debug("waiting for more data")
                    d2 = self.request.recv(65536)
                    data = data + d2
                    read_more = False

                # Not an expected header?
                if len(data) > 0 and len(data) < 14:
                    read_more = True
                    continue

                if data[0] == COMMAND_READ:
                    command_length = int.from_bytes(
                        data[1:5], byteorder='big')
                    if (command_length > 0) and (len(data) < command_length):
                        read_more = True
                        logging.debug(
                            "Expect %s bytes from header information (read), but have only %s", command_length, len(data))
                        continue

                    result = self.handle_read(data)

                elif data[0] == COMMAND_WRITE:
                    command_length = int.from_bytes(
                        data[3:7], byteorder='big')

                    logging.debug("Len (data, header info): %s %s",
                                  len(data), command_length)

                    if command_length < len(data):
                        buffer = data[command_length:]
                        data = data[0:command_length]

                    if (command_length > 0) and (len(data) < command_length):
                        read_more = True
                        logging.debug(
                            "Expect %s bytes from header information (write), but have only %s", command_length, len(data))
                        continue

                    self.handle_write(data)
                    result = None

                elif data[0] == COMMAND_EEPROM_FILE:
                    filename_length = data[1]
                    filename = "".join(map(chr, data[14:14 + filename_length]))
                    result = self.write_eeprom_file(filename)

                elif data[0] == COMMAND_STORE_DATA:
                    self.save_data_memory()

                elif data[0] == COMMAND_RESTORE_DATA:
                    self.restore_data_memory()

                elif data[0] == COMMAND_EEPROM_FILE:
                    filename_length = data[1]
                    filename = "".join(map(chr, data[14:14 + filename_length]))
                    result = self.write_eeprom_file(filename)

                elif data[0] == COMMAND_CHECKSUM:
                    result = self._response_packet(
                        COMMAND_CHECKSUM_RESPONSE, 0, 16) + self.program_checksum()

                elif data[0] == COMMAND_XML:
                    try:
                        data = self.get_and_check_xml()
                    except IOError:
                        data = ""  # empty response

                    if data is not None:
                        result = self._response_packet(
                            COMMAND_XML_RESPONSE, 0, len(data)) + data
                    else:
                        result = self._response_packet(
                            COMMAND_XML_RESPONSE, 0, 0)

                elif data[0] == COMMAND_PROGMEM:
                    try:
                        data = self.get_program_memory()
                        print(data)
                    except IOError:
                        data = []  # empty response

                    # format program memory dump
                    dump = ""
                    for i in range(0, len(data), 4):
                        dump += "{:02X}{:02X}{:02X}{:02X}\n".format(
                            data[i], data[i + 1], data[i + 2], data[i + 3])

                    result = self._response_packet(
                        COMMAND_PROGMEM_RESPONSE, 0, len(dump)) + \
                        dump.encode('ascii')

                elif data[0] == COMMAND_GET_META:
                    length = int.from_bytes(data[1:5], byteorder='big')

                    if length < len(data):
                        buffer = data[command_length:]
                        data = data[0:command_length]

                    attribute = data[14:length].decode("utf-8")
                    value = self.get_meta(attribute)
                    logging.debug("metadata request for %s = %s",
                                  attribute, value)

                    if value is None:
                        value = ""

                    value = value.encode('utf-8')

                    result = self._response_packet(
                        COMMAND_META_RESPONSE, 0, len(value))
                    result += value

                elif data[0] == COMMAND_WRITE_EEPROM_CONTENT:
                    command_length = int.from_bytes(
                        data[3:7], byteorder='big')

                    logging.debug("Len (data, header info): %s %s",
                                  len(data), command_length)

                    if command_length < len(data):
                        buffer = data[command_length:]
                        data = data[0:command_length]

                    if (command_length > 0) and (len(data) < command_length):
                        read_more = True
                        logging.debug(
                            "Expect %s bytes from header information (write), but have only %s", command_length, len(data))
                        continue

                    result = self.write_eeprom_content(data[14:command_length])

                if (result is not None) and (len(result) > 0):
                    logging.debug(
                        "Sending %s bytes answer to client", len(result))
                    self.request.send(result)

                # Still got data that hasn't been processed?
                if buffer is not None:
                    data = buffer
                else:
                    data = None

            except ConnectionResetError:
                finished = True
            except BrokenPipeError:
                finished = True

    def get_and_check_xml(self):

        class Foo(object):

            def __init__(self):
                pass

        res = Foo()
        logging.debug("reading profile %s",
                      self.filestore.dspprogramfile)
        parse_xml(res, self.filestore.dspprogramfile)

        try:
            cs = res.checksum
            if cs is not None:
                checksum_xml = bytearray()
                for i in range(0, len(cs), 2):
                    octet = int(cs[i:i + 2], 16)
                    checksum_xml.append(octet)
            else:
                checksum_xml = None

        except AttributeError:
            checksum_xml = 0

        checksum_mem = self.program_checksum()
        logging.debug("checksum memory: %s, xmlfile: %s",
                      checksum_mem,
                      checksum_xml)

        if (checksum_xml is not None) and (checksum_xml != 0):
            if (checksum_xml != checksum_mem):
                logging.error("checksums do not match, aborting")
                return None
        else:
            logging.info("DSP profile doesn't have a checksum, "
                         "might be different from the program running now")

        data = open(self.filestore.dspprogramfile, "rb").read()

        return data

    def get_meta(self, attribute):
        xml = self.get_and_check_xml()
        doc = xmltodict.parse(xml)
        for metadata in doc["ROM"]["beometa"]["metadata"]:
            t = metadata["@type"]
            logging.debug(t)
            if (t == attribute):
                return metadata["#text"]

        return None

    def handle_read(self, data):
        addr = int.from_bytes(data[10:12], byteorder='big')
        length = int.from_bytes(data[6:10], byteorder='big')

        logging.debug("read {} bytes from {}".format(length, addr))

        return self.spi_read(addr, length)

    def spi_read(self, addr, length, add_header=True):

        spi_request = []
        a0 = addr & 0xff
        a1 = (addr >> 8) & 0xff

        spi_request.append(1)
        spi_request.append(a1)
        spi_request.append(a0)

        for _i in range(0, length):
            spi_request.append(0)

        spi_response = SigmaTCPHandler.spi.xfer(spi_request)  # SPI read
        logging.debug("spi read %s bytes from %s", len(spi_request), addr)

        if add_header:
            res = self._response_packet(COMMAND_READRESPONSE,
                                        addr,
                                        len(spi_response[3:]))
        else:
            res = bytearray()

        for b in spi_response[3:]:
            res.append(b)

        return res

    def handle_write(self, data):
        addr = int.from_bytes(data[12:14], byteorder='big')
        length = int.from_bytes(data[8:12], byteorder='big')
        if (length == 0):
            # Client might not implement length correctly and leave
            # it empty
            length = length(data) - 14

        safeload = data[1]  # TODO: use this

        logging.debug("writing {} bytes to {}".format(length, addr))
        return self.write_data(addr, data[14:])

    def write_eeprom_content(self, data):
        tempfile = tempfile.NamedTemporaryFile(mode='w+b',
                                               delete=False)
        filename = tempfile.name
        try:
            tempfile.write(data)
            tempfile.close()
            result = self.write_eeprom_file(filename)
        except IOError:
            result = b'\00'

        try:
            os.remove(filename)
        except:
            pass

        return result

    def write_eeprom_file(self, filename):
        try:
            with open(filename) as fd:
                doc = xmltodict.parse(fd.read())

            for action in doc["ROM"]["page"]["action"]:
                instr = action["@instr"]

                if instr == "writeXbytes":
                    addr = int(action["@addr"])
                    paramname = action["@ParamName"]
                    data = []
                    for d in action["#text"].split(" "):
                        value = int(d, 16)
                        data.append(value)

                    self.write_data(addr, data)

                    # Sleep after erase operations
                    if ("g_Erase" in paramname):
                        time.sleep(10)

                if instr == "delay":
                    time.sleep(1)

            if (filename != self.filestore.dspprogramfile):
                shutil.copy(filename, self.filestore.dspprogramfile)
                logging.debug("copied %s to %s",
                              filename,
                              self.filestore.dspprogramfile)

        except IOError:
            return b'\00'

        return b'\01'

    def write_data(self, addr, data):

        a0 = addr & 0xff
        a1 = (addr >> 8) & 0xff

        spi_request = []
        spi_request.append(0)
        spi_request.append(a1)
        spi_request.append(a0)
        for d in data:
            spi_request.append(d)

        if len(spi_request) < 4096:
            SigmaTCPHandler.spi.xfer(spi_request)
            logging.debug("spi write %s bytes",  len(spi_request) - 3)
        else:
            finished = False
            while not finished:
                if len(spi_request) < 4096:
                    SigmaTCPHandler.spi.xfer(spi_request)
                    logging.debug("spi write %s bytes", len(spi_request) - 3)
                    finished = True
                else:
                    short_request = spi_request[:4003]
                    SigmaTCPHandler.spi.xfer(short_request)
                    logging.debug("spi write %s bytes", len(short_request) - 3)

                    # skip forward 1000 cells
                    addr = addr + 1000  # each memory cell is 4 bytes long
                    a0 = addr & 0xff
                    a1 = (addr >> 8) & 0xff
                    new_request = []
                    new_request.append(0)
                    new_request.append(a1)
                    new_request.append(a0)
                    new_request.extend(spi_request[4003:])

                    spi_request = new_request

        return data

    def save_data_memory(self):
        checksum = self.program_checksum()
        memory = self.get_memory_block(self.dsp.DATA_ADDR,
                                       self.dsp.DATA_LENGTH)
        self.filestore.store_parameters(checksum, memory)

    def restore_data_memory(self):

        checksum = self.program_checksum()
        memory = self.filestore.restore_parameters(checksum)

        if memory is None:
            return

        if (len(memory) > self.dsp.DATA_LENGTH * self.dsp.WORD_LENGTH):
            logging.error("Got %s bytes to restore, but memory is only %s",
                          len(memory),
                          self.dsp.DATA_LENGTH * self.dsp.WORD_LENGTH)

        # Make sure DSP isn't running for this operation
        self._kill_dsp()
        self.write_data(self.dsp.DATA_ADDR, memory)
        # Restart the core
        self._start_dsp()

    def get_memory_block(self, addr, length):
        block_size = 2048

        logging.debug("reading %s bytes from memory",
                      length * self.dsp.WORD_LENGTH)

        # Must kill the core to read program memory, but it doesn't
        # hurt doing it also for other memory types :(
        self._kill_dsp()

        memory = bytearray()

        while len(memory) < length * self.dsp.WORD_LENGTH:
            logging.debug("reading program code block from addr %s", addr)
            data = self.spi_read(addr, block_size, add_header=False)
            # logging.debug("%s", data)
            memory += data
            addr = addr + int(block_size / self.dsp.WORD_LENGTH)

        # Restart the core
        self._start_dsp()

        return memory[0:length * self.dsp.WORD_LENGTH]

    def get_program_memory(self):
        '''
        Calculate a checksum of the program memory of the DSP
        '''
        memory = self.get_memory_block(self.dsp.PROGRAM_ADDR,
                                       self.dsp.PROGRAM_LENGTH)

        end_index = memory.find(self.dsp.PROGRAM_END_SIGNATURE)

        if end_index < 0:
            logging.error("couldn't find program end signature, "
                          "something is wrong with the DSP program memory")
            return None
        else:
            end_index = end_index + len(self.dsp.PROGRAM_END_SIGNATURE)

        logging.debug("Program lengths = %s words",
                      end_index / self.dsp.WORD_LENGTH)

        # logging.debug("%s", memory[0:end_index])
        return memory[0:end_index]

    def program_checksum(self):
        data = self.get_program_memory()
        m = hashlib.md5()
        m.update(data)

        logging.debug("length: %s, digest: %s", len(data), m.digest())
        return m.digest()

    def finish(self):
        logging.debug('finish')

    def _list_str(self, int_list):
        formatted_list = [str(item) for item in int_list]
        return "[" + ','.join(formatted_list) + "]"

    def _response_packet(self, command, addr, data_length):
        packet = bytearray(HEADER_SIZE)
        packet[0] = command
        packet[4] = 14  # header length
        packet[5] = 1  # chip address

        packet[9] = data_length & 0xff
        packet[8] = (data_length >> 8) & 0xff
        packet[7] = (data_length >> 16) & 0xff
        packet[6] = (data_length >> 24) & 0xff

        packet[11] = addr & 0xff
        packet[10] = (addr >> 8) & 0xff

        return packet

    def _kill_dsp(self):
        logging.debug("killing DSP core")
        self.write_data(self.dsp.HIBERNATE_REGISTER,
                        SigmaTCP.int_data(1, self.dsp.REGISTER_WORD_LENGTH))
        time.sleep(0.0001)
        self.write_data(self.dsp.KILLCORE_REGISTER,
                        SigmaTCP.int_data(0, self.dsp.REGISTER_WORD_LENGTH))
        time.sleep(0.0001)
        self.write_data(self.dsp.KILLCORE_REGISTER,
                        SigmaTCP.int_data(1, self.dsp.REGISTER_WORD_LENGTH))

    def _start_dsp(self):
        logging.debug("starting DSP core")
        self.write_data(self.dsp.KILLCORE_REGISTER,
                        SigmaTCP.int_data(0, self.dsp.REGISTER_WORD_LENGTH))
        time.sleep(0.0001)
        self.write_data(self.dsp.STARTCORE_REGISTER,
                        SigmaTCP.int_data(0, self.dsp.REGISTER_WORD_LENGTH))
        time.sleep(0.0001)
        self.write_data(self.dsp.STARTCORE_REGISTER,
                        SigmaTCP.int_data(1, self.dsp.REGISTER_WORD_LENGTH))
        time.sleep(0.0001)
        self.write_data(self.dsp.HIBERNATE_REGISTER,
                        SigmaTCP.int_data(0, self.dsp.REGISTER_WORD_LENGTH))


class SigmaTCPServer(ThreadingMixIn, TCPServer):

    def __init__(self,
                 server_address=("0.0.0.0", DEFAULT_PORT),
                 RequestHandlerClass=SigmaTCPHandler):
        self.allow_reuse_address = True

        TCPServer.__init__(self, server_address, RequestHandlerClass)

    def server_activate(self):
        # TODO: read memory
        rh = SigmaTCPHandler(None, None, None)
        logging.debug("restoring saved data memory")
        try:
            rh.restore_data_memory()
        except IOError:
            logging.debug("no saved data found")
        TCPServer.server_activate(self)

    def server_close(self):
        # TODO: Store RAM
        rh = SigmaTCPHandler(None, None, None)
        logging.debug("saving DSP data memory")
        rh.save_data_memory()
        TCPServer.server_close(self)
