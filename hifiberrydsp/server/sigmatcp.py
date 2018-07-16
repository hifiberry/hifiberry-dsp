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
import sys
import logging
import hashlib
import getpass

from threading import Thread

from socketserver import BaseRequestHandler, TCPServer, ThreadingMixIn

from zeroconf import ServiceInfo, Zeroconf
import xmltodict

from hifiberrydsp.hardware import adau145x
from hifiberrydsp.hardware.spi import SpiHandler
from hifiberrydsp.datatools import int_data
from hifiberrydsp.xmlprofile import ATTRIBUTE_CHECKSUM, ATTRIBUTE_VOL_CTL
from hifiberrydsp.alsa.alsasync import AlsaSync
from hifiberrydsp import datatools

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
COMMAND_RESTORE_DATA = 0xf7
COMMAND_GET_META = 0xf8
COMMAND_META_RESPONSE = 0xf9
COMMAND_PROGMEM = 0xfa
COMMAND_PROGMEM_RESPONSE = 0xfb

HEADER_SIZE = 14

DEFAULT_PORT = 8086

MAX_READ_SIZE = 1024 * 2

ZEROCONF_TYPE = "_sigmatcp._tcp.local."


def parameterfile():
    if (getpass.getuser() == 0):
        return "/etc/dspparameters.dat"
    else:
        return os.path.expanduser("~/.dsptoolkit/dspparameters.dat")


def dspprogramfile():
    if (getpass.getuser() == 0):
        return "/etc/dspprogram.xml"
    else:
        return os.path.expanduser("~/.dsptoolkit/dspprogram.xml")


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


class SigmaTCPHandler(BaseRequestHandler):

    checksum = None
    spi = SpiHandler()
    dsp = adau145x.Adau145x
    dspprogramfile = dspprogramfile()
    parameterfile = parameterfile()
    alsasync = None
    updating = False

    def __init__(self, request, client_address, server):
        logging.debug("__init__")
        BaseRequestHandler.__init__(self, request, client_address, server)

    def setup(self):
        logging.debug('setup')

    def finish(self):
        logging.debug('finish')

    def handle(self):
        logging.debug('handle')
        finished = False
        data = None
        read_more = False

        while not(finished):
            # Read dara
            try:
                buffer = None
                result = None

                if data is None:
                    data = self.request.recv(65536)
                    if len(data) == 0:
                        finished = True
                        continue

                if read_more:
                    logging.debug("waiting for more data")
                    d2 = self.request.recv(65536)
                    if (len(d2) == 0):
                        time.sleep(0.1)
                    data = data + d2
                    read_more = False

                # Not an expected header?
                if len(data) > 0 and len(data) < 14:
                    read_more = True
                    continue

                logging.debug("received request type %s", data[0])

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

                elif data[0] == COMMAND_CHECKSUM:
                    result = self._response_packet(
                        COMMAND_CHECKSUM_RESPONSE, 0, 16) + \
                        self.program_checksum(cached=False)

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

    @staticmethod
    def get_and_check_xml():

        logging.info("reading profile %s",
                     SigmaTCPHandler.dspprogramfile)
        try:
            checksum_xml = bytearray()
            with open(SigmaTCPHandler.dspprogramfile) as fd:
                doc = xmltodict.parse(fd.read())
                for metadata in doc["ROM"]["beometa"]["metadata"]:
                    t = metadata["@type"]

                    if (t == ATTRIBUTE_CHECKSUM):
                        cs = metadata["#text"]
                        logging.debug("checksum from XML: %s", cs)
                        if cs is not None:
                            for i in range(0, len(cs), 2):
                                octet = int(cs[i:i + 2], 16)
                                checksum_xml.append(octet)

        except IOError:
            logging.error("can't read file %s",
                          SigmaTCPHandler.dspprogramfile)

        checksum_mem = SigmaTCPHandler.program_checksum()
        logging.info("checksum memory: %s, xmlfile: %s",
                     checksum_mem,
                     checksum_xml)

        if (checksum_xml is not None) and (checksum_xml != 0):
            if (checksum_xml != checksum_mem):
                logging.error("checksums do not match, aborting")
                return None
        else:
            logging.info("DSP profile doesn't have a checksum, "
                         "might be different from the program running now")

        data = open(SigmaTCPHandler.dspprogramfile, "rb").read()

        return data

    @staticmethod
    def get_meta(attribute):
        xml = SigmaTCPHandler.get_and_check_xml()
        try:
            doc = xmltodict.parse(xml)
            for metadata in doc["ROM"]["beometa"]["metadata"]:
                t = metadata["@type"]
                if (t == attribute):
                    return metadata["#text"]
        except Exception as e:
            logging.info("can't parse XML metadata (%s)", e)

        return None

    @staticmethod
    def handle_read(data):
        addr = int.from_bytes(data[10:12], byteorder='big')
        length = int.from_bytes(data[6:10], byteorder='big')

        spi_response = SigmaTCPHandler.spi.read(addr, length)
        logging.debug("read {} bytes from {}".format(length, addr))

        res = SigmaTCPHandler._response_packet(COMMAND_READRESPONSE,
                                               addr,
                                               len(spi_response)) + spi_response
        return res

    @staticmethod
    def handle_write(data):

        addr = int.from_bytes(data[12:14], byteorder='big')
        length = int.from_bytes(data[8:12], byteorder='big')
        if (length == 0):
            # Client might not implement length correctly and leave
            # it empty
            length = length(data) - 14

        _safeload = data[1]  # TODO: use this

        if addr == SigmaTCPHandler.dsp.KILLCORE_REGISTER and not(SigmaTCPHandler.updating):
            logging.debug(
                "write to KILLCORE seen, guessing something is updating the DSP")
            SigmaTCPHandler.prepare_update()

        logging.debug("writing {} bytes to {}".format(length, addr))
        memdata = data[14:]
        res = SigmaTCPHandler.spi.write(addr, memdata)

        if addr == SigmaTCPHandler.dsp.HIBERNATE_REGISTER and \
                SigmaTCPHandler.updating and memdata == b'\00\00':
            logging.debug(
                "set HIBERNATE to 0 seen, guessing update is done")
            SigmaTCPHandler.finish_update()

        return res

    @staticmethod
    def write_eeprom_content(xmldata):

        logging.info("writing XML file: %s", xmldata)

        try:
            doc = xmltodict.parse(xmldata)

            SigmaTCPHandler.prepare_update()
            for action in doc["ROM"]["page"]["action"]:
                instr = action["@instr"]

                if instr == "writeXbytes":
                    addr = int(action["@addr"])
                    paramname = action["@ParamName"]
                    data = []
                    for d in action["#text"].split(" "):
                        value = int(d, 16)
                        data.append(value)

                    logging.debug("writeXbytes %s %s", addr, len(data))
                    SigmaTCPHandler.spi.write(addr, data)

#                    if ("Page" in paramname):
#                        logging.debug("Page write, delaying 100ms")
#                        time.sleep(0.1)

                    # Sleep after erase operations
                    if ("g_Erase" in paramname):
                        logging.debug(
                            "found erase command, waiting 10 seconds to finish")
                        time.sleep(10)

                if instr == "delay":
                    logging.debug("delay")
                    time.sleep(1)

            SigmaTCPHandler.finish_update()

            # Write current DSP profile
            with open(SigmaTCPHandler.dspprogramfile, "w+b") as dspprogram:
                if (isinstance(xmldata, str)):
                    xmldata = xmldata.encode("utf-8")
                dspprogram.write(xmldata)

        except Exception as e:
            e.print_stack_trace()
            logging.error("exception during EEPROM write: %s", e)
            return b'\00'

        return b'\01'

    @staticmethod
    def write_eeprom_file(filename):
        try:
            with open(filename) as fd:
                data = fd.read()
                return SigmaTCPHandler.write_eeprom_content(data)
        except IOError as e:
            logging.debug("IOError: %s", e)
            return b'\00'

    @staticmethod
    def save_data_memory():
        logging.info("store: getting checksum")
        checksum = SigmaTCPHandler.program_checksum()
        memory = SigmaTCPHandler.get_memory_block(SigmaTCPHandler.dsp.DATA_ADDR,
                                                  SigmaTCPHandler.dsp.DATA_LENGTH)
        logging.info("store: writing memory dump to file")
        SigmaTCPHandler.store_parameters(checksum, memory)

    @staticmethod
    def restore_data_memory():

        logging.info("restore: checking checksum")
        checksum = SigmaTCPHandler.program_checksum(cached=False)
        memory = SigmaTCPHandler.restore_parameters(checksum)

        if memory is None:
            return

        logging.info("restore: writing to memory")

        dsp = SigmaTCPHandler.dsp

        if (len(memory) > dsp.DATA_LENGTH * dsp.WORD_LENGTH):
            logging.error("Got %s bytes to restore, but memory is only %s",
                          len(memory),
                          dsp.DATA_LENGTH * dsp.WORD_LENGTH)

        # Make sure DSP isn't running for this operation
        SigmaTCPHandler._kill_dsp()
        SigmaTCPHandler.spi.write(dsp.DATA_ADDR, memory)
        # Restart the core
        SigmaTCPHandler._start_dsp()

    @staticmethod
    def get_memory_block(addr, length):
        block_size = 2048

        dsp = SigmaTCPHandler.dsp

        logging.debug("reading %s bytes from memory",
                      length * dsp.WORD_LENGTH)

        # Must kill the core to read program memory, but it doesn't
        # hurt doing it also for other memory types :(
        SigmaTCPHandler._kill_dsp()

        memory = bytearray()

        while len(memory) < length * dsp.WORD_LENGTH:
            logging.debug("reading memory code block from addr %s", addr)
            data = SigmaTCPHandler.spi.read(addr, block_size)
            # logging.debug("%s", data)
            memory += data
            addr = addr + int(block_size / dsp.WORD_LENGTH)

        # Restart the core
        SigmaTCPHandler._start_dsp()

        return memory[0:length * dsp.WORD_LENGTH]

    @staticmethod
    def get_program_memory():
        '''
        Calculate a checksum of the program memory of the DSP
        '''
        dsp = SigmaTCPHandler.dsp
        memory = SigmaTCPHandler.get_memory_block(dsp.PROGRAM_ADDR,
                                                  dsp.PROGRAM_LENGTH)

        end_index = memory.find(dsp.PROGRAM_END_SIGNATURE)

        if end_index < 0:
            logging.error("couldn't find program end signature, "
                          "something is wrong with the DSP program memory")
            return None
        else:
            end_index = end_index + len(dsp.PROGRAM_END_SIGNATURE)

        logging.debug("Program lengths = %s words",
                      end_index / dsp.WORD_LENGTH)

        # logging.debug("%s", memory[0:end_index])
        return memory[0:end_index]

    @staticmethod
    def program_checksum(cached=True):
        if cached and SigmaTCPHandler.checksum is not None:
            logging.debug("using cached program checksum, "
                          "might not always be correct")
            return SigmaTCPHandler.checksum

        data = SigmaTCPHandler.get_program_memory()
        m = hashlib.md5()
        m.update(data)

        logging.debug("length: %s, digest: %s", len(data), m.digest())

        logging.info("caching program memory checksum")
        SigmaTCPHandler.checksum = m.digest()
        return SigmaTCPHandler.checksum

    @staticmethod
    def _list_str(int_list):
        formatted_list = [str(item) for item in int_list]
        return "[" + ','.join(formatted_list) + "]"

    @staticmethod
    def _response_packet(command, addr, data_length):
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

    @staticmethod
    def _kill_dsp():
        logging.debug("killing DSP core")
        dsp = SigmaTCPHandler.dsp
        spi = SigmaTCPHandler.spi

        spi.write(dsp.HIBERNATE_REGISTER,
                  int_data(1, dsp.REGISTER_WORD_LENGTH))
        time.sleep(0.0001)
        spi.write(dsp.KILLCORE_REGISTER,
                  int_data(0, dsp.REGISTER_WORD_LENGTH))
        time.sleep(0.0001)
        spi.write(dsp.KILLCORE_REGISTER,
                  int_data(1, dsp.REGISTER_WORD_LENGTH))

    @staticmethod
    def _start_dsp():
        logging.debug("starting DSP core")
        dsp = SigmaTCPHandler.dsp
        spi = SigmaTCPHandler.spi

        spi.write(dsp.KILLCORE_REGISTER,
                  int_data(0, dsp.REGISTER_WORD_LENGTH))
        time.sleep(0.0001)
        spi.write(dsp.STARTCORE_REGISTER,
                  int_data(0, dsp.REGISTER_WORD_LENGTH))
        time.sleep(0.0001)
        spi.write(dsp.STARTCORE_REGISTER,
                  int_data(1, dsp.REGISTER_WORD_LENGTH))
        time.sleep(0.0001)
        spi.write(dsp.HIBERNATE_REGISTER,
                  int_data(0, dsp.REGISTER_WORD_LENGTH))

    @staticmethod
    def store_parameters(checksum, memory):
        with open(SigmaTCPHandler.parameterfile, "wb") as datafile:
            datafile.write(checksum)
            datafile.write(memory)

    @staticmethod
    def restore_parameters(checksum):
        with open(SigmaTCPHandler.parameterfile, "rb") as datafile:
            file_checksum = datafile.read(16)
            logging.debug("Checking checksum %s/%s",
                          checksum, file_checksum)
            if checksum != file_checksum:
                logging.error("checksums do not match, aborting")
                return

    @staticmethod
    def prepare_update():
        '''
        Call this method if the DSP program might change soon
        '''
        logging.info("preparing for memory update")
        SigmaTCP.checksum = None
        SigmaTCPHandler.update_alsasync(clear=True)
        SigmaTCPHandler.updating = True

    @staticmethod
    def finish_update():
        '''
        Call this method after the DSP program has been refreshed
        '''
        logging.info("finished memory update")
        ProgramRefresher().start()

    @staticmethod
    def update_alsasync(clear=False):
        if SigmaTCPHandler.alsasync is None:
            return

        if clear:
            SigmaTCPHandler.alsasync.set_volume_register(None)
            return

        volreg = SigmaTCPHandler.get_meta(ATTRIBUTE_VOL_CTL)
        if volreg is None or len(volreg) == 0:
            SigmaTCPHandler.alsasync.set_volume_register(None)

        reg = datatools.parse_int(volreg)
        SigmaTCPHandler.alsasync.set_volume_register(reg)


class ProgramRefresher(Thread):

    def run(self):
        logging.debug(
            "running asynchrounous checksum refresh after potential update")
        time.sleep(0)
        # calculate cecksum
        SigmaTCPHandler.program_checksum(cached=False)
        # update volume register for ALSA control
        SigmaTCPHandler.update_alsasync()
        SigmaTCPHandler.updating = False


class SigmaTCPServer(ThreadingMixIn, TCPServer):

    def __init__(self,
                 server_address=("0.0.0.0", DEFAULT_PORT),
                 RequestHandlerClass=SigmaTCPHandler):
        self.allow_reuse_address = True

        TCPServer.__init__(self, server_address, RequestHandlerClass)

    def server_activate(self):
        TCPServer.server_activate(self)

    def server_close(self):
        TCPServer.server_close(self)


class SigmaTCPServerMain():

    def __init__(self, alsa_mixer_name="DSPVolume"):
        self.restore = False

        self.server = SigmaTCPServer()
        if "--alsa" in sys.argv:
            logging.info("initializiong ALSA mixer control")
            alsasync = AlsaSync()
            alsasync.set_alsa_control(alsa_mixer_name)
            SigmaTCPHandler.alsasync = alsasync
            alsasync.start()
            # TODO: start sync
        else:
            logging.info("not using ALSA volume control")
            self.alsa_mixer_name = None

        if "--restore" in sys.argv:
            self.restore = False

    def announce_zeroconf(self):
        desc = {'name': 'SigmaTCP', 'vendor': 'HiFiBerry'}
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        self.zeroconf_info = ServiceInfo(ZEROCONF_TYPE,
                                         "{}.{}".format(
                                             hostname, ZEROCONF_TYPE),
                                         socket.inet_aton(ip),
                                         DEFAULT_PORT, 0, 0, desc)
        self.zeroconf = Zeroconf()
        self.zeroconf.register_service(self.zeroconf_info)

    def shutdown_zeroconf(self):
        if self.zeroconf is not None and self.zeroconf_info is not None:
            self.zeroconf.unregister_service(self.zeroconf_info)

        self.zeroconf_info = None
        self.zeroconf.close()
        self.zeroconf = None

    def run(self):
        if (self.restore):
            try:
                logging.info("restoring saved data memory")
                SigmaTCPHandler.restore_data_memory()
                SigmaTCPHandler.finish_update()
            except IOError:
                logging.info("no saved data found")

        logging.info("Announcing via zeroconf")
        self.announce_zeroconf()

        logging.info("Starting TCP server")
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            self.server.server_close()

        if SigmaTCPHandler.alsasync is not None:
            SigmaTCPHandler.alsasync.finish()

        logging.info("Removing from zeroconf")
        self.shutdown_zeroconf()

        logging.info("saving DSP data memory")
        SigmaTCPHandler.save_data_memory()
