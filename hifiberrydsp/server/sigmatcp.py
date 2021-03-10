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

from threading import Thread

from socketserver import BaseRequestHandler, TCPServer, ThreadingMixIn

# from zeroconf import ServiceInfo, Zeroconf
import xmltodict
import configparser
import requests

from hifiberrydsp.hardware import adau145x
from hifiberrydsp.hardware.spi import SpiHandler
from hifiberrydsp.datatools import int_data
from hifiberrydsp.parser.xmlprofile import \
    XmlProfile, ATTRIBUTE_VOL_CTL, ATTRIBUTE_SPDIF_ACTIVE
from hifiberrydsp.alsa.alsasync import AlsaSync
from hifiberrydsp.lg.soundsync import SoundSync
from hifiberrydsp import datatools

from hifiberrydsp.server.constants import \
    COMMAND_READ, COMMAND_READRESPONSE, COMMAND_WRITE, \
    COMMAND_EEPROM_FILE, COMMAND_CHECKSUM, COMMAND_CHECKSUM_RESPONSE, \
    COMMAND_WRITE_EEPROM_CONTENT, COMMAND_XML, COMMAND_XML_RESPONSE, \
    COMMAND_STORE_DATA, COMMAND_RESTORE_DATA, COMMAND_GET_META, \
    COMMAND_META_RESPONSE, COMMAND_PROGMEM, COMMAND_PROGMEM_RESPONSE, \
    COMMAND_DATAMEM, COMMAND_DATAMEM_RESPONSE, \
    COMMAND_GPIO, \
    HEADER_SIZE, \
    DEFAULT_PORT
# import hifiberrydsp

# URL to notify on DSP program updates
this = sys.modules[__name__]
this.notify_on_updates = None
this.command_after_startup = None
this.dsp=None


def parameterfile():
    if (os.geteuid() == 0):
        return "/var/lib/hifiberry/dspparameters.dat"
    else:
        return os.path.expanduser("~/.hifiberry/dspparameters.dat")


def dspprogramfile():
    if (os.geteuid() == 0):
        logging.info(
            "running as root, data will be stored in /var/lib/hifiberry")
        mydir = "/var/lib/hifiberry"
    else:
        mydir = "~/.hifiberry"
        logging.info(
            "not running as root, data will be stored in ~/.hifiberry")
    try:
        if not os.path.isdir(mydir):
            os.makedirs(mydir)
    except Exception as e:
        logging.error("can't creeate directory {} ({})", mydir, e)

    return os.path.expanduser(mydir + "/dspprogram.xml")


def startup_notify():
    if this.command_after_startup is None:
        return 
    
    # TCP server still needs to start
    time.sleep(2)
    
    logging.info("calling %s", this.command_after_startup)
    os.system(this.command_after_startup)
    
    

class SigmaTCPHandler(BaseRequestHandler):

    checksum = None
    spi = SpiHandler()
    dsp = adau145x.Adau145x
    dspprogramfile = dspprogramfile()
    parameterfile = parameterfile()
    alsasync = None
    lgsoundsync = None
    updating = False
    xml = None
    checksum_error = False

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
                            "Expect %s bytes from header information (read), but have only %s",
                            command_length, len(data))
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
                            "Expect %s bytes from header information (write), but have only %s",
                            command_length, len(data))
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

                    except IOError as e:
                        logging.debug("IOerror when reading XML file: %s", e)
                        data = None
                    except Exception as e:
                        logging.debug("Unexpected error when reading XML file: %s", e)
                        logging.exception(e)
                        data = None

                    if data is not None:
                        xml_bytes = data.encode()
                        result = self._response_packet(
                            COMMAND_XML_RESPONSE, 0, len(data)) + xml_bytes
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

                elif data[0] == COMMAND_GPIO:
                    logging.error("GPIO command not yet implemented")

                elif data[0] == COMMAND_DATAMEM:
                    try:
                        data = self.get_data_memory()
                    except IOError:
                        data = []  # empty response

                    # format program memory dump
                    dump = ""
                    for i in range(0, len(data), 4):
                        dump += "{:02X}{:02X}{:02X}{:02X}\n".format(
                            data[i], data[i + 1], data[i + 2], data[i + 3])

                    result = self._response_packet(
                        COMMAND_DATAMEM_RESPONSE, 0, len(dump)) + \
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
    def read_xml_profile():
        SigmaTCPHandler.xml = XmlProfile(SigmaTCPHandler.dspprogramfile)
        cs = SigmaTCPHandler.xml.get_meta("checksum")
        logging.debug("checksum from XML: %s", cs)
        SigmaTCPHandler.checksum_xml = None
        if cs is not None:
            SigmaTCPHandler.checksum_xml = bytearray()
            for i in range(0, len(cs), 2):
                octet = int(cs[i:i + 2], 16)
                SigmaTCPHandler.checksum_xml.append(octet)

        checksum_mem = SigmaTCPHandler.program_checksum()
        checksum_xml = SigmaTCPHandler.checksum_xml
        logging.info("checksum memory: %s, xmlfile: %s",
                     checksum_mem,
                     checksum_xml)

        if (checksum_xml is not None) and (checksum_xml != 0):
            if (checksum_xml != checksum_mem):
                logging.error("checksums do not match, aborting")
                SigmaTCPHandler.checksum_error = True
                return
        else:
            logging.info("DSP profile doesn't have a checksum, "
                         "might be different from the program running now")

        SigmaTCPHandler.checksum_error = False

    @staticmethod
    def get_checked_xml():
        if not(SigmaTCPHandler.checksum_error):
            if SigmaTCPHandler.xml is None:
                SigmaTCPHandler.read_xml_profile()

            return SigmaTCPHandler.xml
        else:
            logging.debug("XML checksum error, ignoring XML file")
            return None

    @staticmethod
    def get_and_check_xml():
        return str(SigmaTCPHandler.get_checked_xml())

    @staticmethod
    def get_meta(attribute):
        if attribute=="detected_dsp":
            return this.dsp
        
        try:
            xml = SigmaTCPHandler.get_checked_xml()
        except:
            return None

        if xml is None:
            return None
        else:
            try:
                return xml.get_meta(attribute)
            except:
                logging.error("can't get attribute %s from XML", attribute)
                return None

    @staticmethod
    def handle_read(data):
        addr = int.from_bytes(data[10:12], byteorder='big')
        length = int.from_bytes(data[6:10], byteorder='big')
        
        logging.debug("Handle read %s/%s",addr,length)

        spi_response = SigmaTCPHandler.spi.read(addr, length)
        logging.debug("read {} bytes from {}".format(length, addr))

        res = SigmaTCPHandler._response_packet(COMMAND_READRESPONSE,
                                               addr,
                                               len(spi_response)) + spi_response
        return res

    @staticmethod
    def handle_write(data):

        if len(data) < 14:
            logging.error("Got incorrect write request, length < 14 bytes")
            return None

        addr = int.from_bytes(data[12:14], byteorder='big')
        length = int.from_bytes(data[8:12], byteorder='big')
        if (length == 0):
            # Client might not implement length correctly and leave
            # it empty
            length = len(data) - 14

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

                    # Sleep after erase operations
                    if ("g_Erase" in paramname):
                        logging.debug(
                            "found erase command, waiting 10 seconds to finish")
                        time.sleep(10)

                    # Delay after a page write
                    if ("Page_" in paramname):
                        logging.debug(
                            "found page write command, waiting 0.5 seconds to finish")
                        time.sleep(0.5)

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
            logging.error("exception during EEPROM write: %s", e)
            logging.exception(e)
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
            memsum = 0
            for i in memory:
                memsum = memsum + i

            if (memsum > 0):
                logging.error("couldn't find program end signature," +
                              " using full program memory")
                end_index = dsp.PROGRAM_LENGTH - dsp.WORD_LENGTH
            else:
                logging.error("SPI returned only zeros - communication"
                              "error")
                return None
        else:
            end_index = end_index + len(dsp.PROGRAM_END_SIGNATURE)

        logging.debug("Program lengths = %s words",
                      end_index / dsp.WORD_LENGTH)

        # logging.debug("%s", memory[0:end_index])
        return memory[0:end_index]

    @staticmethod
    def get_data_memory():
        '''
        Calculate a checksum of the program memory of the DSP
        '''
        dsp = SigmaTCPHandler.dsp
        memory = SigmaTCPHandler.get_memory_block(dsp.DATA_ADDR,
                                                  dsp.DATA_LENGTH)
        logging.debug("Data lengths = %s words",
                      dsp.DATA_LENGTH / dsp.WORD_LENGTH)

        # logging.debug("%s", memory[0:end_index])
        return memory[0:dsp.DATA_LENGTH]

    @staticmethod
    def program_checksum(cached=True):
        if cached and SigmaTCPHandler.checksum is not None:
            logging.debug("using cached program checksum, "
                          "might not always be correct")
            return SigmaTCPHandler.checksum

        data = SigmaTCPHandler.get_program_memory()
        m = hashlib.md5()
        try:
            m.update(data)
        except:
            logging.error("Can't calculate checksum from %s", data)
            return None

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
        SigmaTCPHandler.checksum = None
        SigmaTCPHandler.update_alsasync(clear=True)
        SigmaTCPHandler.update_lgsoundsync(clear=True)
        SigmaTCPHandler.updating = True

    @staticmethod
    def finish_update():
        '''
        Call this method after the DSP program has been refreshed
        '''
        logging.info("finished memory update")
        SigmaTCPHandler.xml = None
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

    @staticmethod
    def update_lgsoundsync(clear=False):
        if SigmaTCPHandler.lgsoundsync is None:
            logging.debug("LG Sound Sync instance is None")
            return

        if clear:
            SigmaTCPHandler.lgsoundsync.set_registers(None, None)
            return

        logging.debug("checking profile for SPDIF state and volume control support")
        volreg = SigmaTCPHandler.get_meta(ATTRIBUTE_VOL_CTL)
        spdifreg = SigmaTCPHandler.get_meta(ATTRIBUTE_SPDIF_ACTIVE)
        if volreg is None or len(volreg) == 0 or \
            spdifreg is None or len(spdifreg) == 0:
            SigmaTCPHandler.lgsoundsync.set_registers(None, None)
            logging.debug("disabled LG Sound Sync")

        logging.info("enabling LG Sound Sync")
        volr = datatools.parse_int(volreg)
        spdifr = datatools.parse_int(spdifreg)
        SigmaTCPHandler.lgsoundsync.set_registers(volr, spdifr)


class ProgramRefresher(Thread):

    def run(self):
        logging.debug(
            "running asynchrounous checksum refresh after potential update")
        time.sleep(0)
        # calculate cecksum
        SigmaTCPHandler.program_checksum(cached=False)
        # update volume register for ALSA control
        SigmaTCPHandler.update_alsasync()
        SigmaTCPHandler.update_lgsoundsync()
        SigmaTCPHandler.updating = False
        if this.notify_on_updates is not None:
            r = requests.post(this.notify_on_updates)
            logging.info("sent update notify to %s, HTTP status %s",
                          this.notify_on_updates, r.status_code)
            


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
        self.abort = False
        self.zeroconf = None

        self.server = SigmaTCPServer()
        
        params = self.parse_config()
        if params["alsa"]:
            logging.info("initializing ALSA mixer control %s", alsa_mixer_name)
            alsasync = AlsaSync()
            if alsasync.set_alsa_control(alsa_mixer_name):
                SigmaTCPHandler.alsasync = alsasync
                volreg = SigmaTCPHandler.get_meta(ATTRIBUTE_VOL_CTL)
                if volreg is not None and len(volreg) > 0:
                    reg = datatools.parse_int(volreg)
                    alsasync.set_volume_register(reg)
                alsasync.start()
            else:
                logging.error("can't create mixer control - aborting")
                self.abort=True
        else:
            logging.info("not using ALSA volume control")
            self.alsa_mixer_name = None

        if params["lgsoundsync"]:
            try:
                logging.info("initializing LG Sound Sync")
                SigmaTCPHandler.lgsoundsync = SoundSync()
                SigmaTCPHandler.lgsoundsync.start()
                SigmaTCPHandler.update_lgsoundsync()
            except Exception as e:
                logging.exception(e)
        else:
            logging.info("not enabling LG Sound Sync")
            
        if this.notify_on_updates is not None:
            logging.info("Sending notifies on program updates to %s",
                         this.notify_on_updates)

        if params["restore"]:
            self.restore = True

        
    def parse_config(self):
        config = configparser.ConfigParser()
        config.optionxform = lambda option: option
    
        config.read("/etc/sigmatcp.conf")

        params = {}
    
        try:
            params["alsa"] = config.getboolean("server","alsa")
        except:
            params["alsa"] = False
            
        if  "--alsa" in sys.argv:
            params["alsa"] = True

        try:            
            params["lgsoundsync"] = config.getboolean("server","lgsoundsync") 
        except:
            params["lgsoundsync"] = False
            
        if "--lgsoundsync" in sys.argv:
            params["lgsoundsync"] = True
            
        try:
            this.command_after_startup = config.get("server","command_after_startup")
        except:
            this.command_after_startup = None

        try:            
            this.notify_on_updates = config.get("server","notify_on_updates") 
        except:
            this.notify_on_updates = None
            


        if "--restore" in sys.argv:
            params["restore"] = True
        else:
            params["restore"] = False
            
        return params
            

#     def announce_zeroconf(self):
#         desc = {'name': 'SigmaTCP',
#                 'vendor': 'HiFiBerry',
#                 'version': hifiberrydsp.__version__}
#         hostname = socket.gethostname()
#         try:
#             ip = socket.gethostbyname(hostname)
#         except Exception:
#             logging.error("can't get IP for hostname %s, "
#                           "not initialising Zeroconf",
#                           hostname)
#             return
# 
#         self.zeroconf_info = ServiceInfo(ZEROCONF_TYPE,
#                                          "{}.{}".format(
#                                              hostname, ZEROCONF_TYPE),
#                                          socket.inet_aton(ip),
#                                          DEFAULT_PORT, 0, 0, desc)
#         self.zeroconf = Zeroconf()
#         self.zeroconf.register_service(self.zeroconf_info)
# 
#     def shutdown_zeroconf(self):
#         if self.zeroconf is not None and self.zeroconf_info is not None:
#             self.zeroconf.unregister_service(self.zeroconf_info)
# 
#             self.zeroconf_info = None
#             self.zeroconf.close()
#             self.zeroconf = None

    def run(self):
        
        # Check if a DSP is detected
        dsp_detected = adau145x.Adau145x.detect_dsp()
        if dsp_detected:
            logging.info("detected ADAU14xx DSP")
            this.dsp="ADAU15xx"
        else:
            logging.info("did not detect ADAU14xx DSP")
            this.dsp=""
            
        
        if (self.restore):
            try:
                logging.info("restoring saved data memory")
                SigmaTCPHandler.restore_data_memory()
                SigmaTCPHandler.finish_update()
            except IOError:
                logging.info("no saved data found")

#         logging.info("announcing via zeroconf")
#         try:
#             self.announce_zeroconf()
#         except Exception as e:
#             logging.debug("exception while initialising Zeroconf")
#             logging.exception(e)

        logging.debug("done")
        
        logging.info(this.command_after_startup)
        notifier_thread = Thread(target = startup_notify)
        notifier_thread.start()
        
        try:
            if not(self.abort):
                logging.info("starting TCP server")
                self.server.serve_forever()
        except KeyboardInterrupt:
            logging.info("aborting ")
            self.server.server_close()

        if SigmaTCPHandler.alsasync is not None:
            SigmaTCPHandler.alsasync.finish()

        if SigmaTCPHandler.lgsoundsync is not None:
            SigmaTCPHandler.lgsoundsync.finish()

#        logging.info("removing from zeroconf")
#        self.shutdown_zeroconf()

        logging.info("saving DSP data memory")
        SigmaTCPHandler.save_data_memory()
