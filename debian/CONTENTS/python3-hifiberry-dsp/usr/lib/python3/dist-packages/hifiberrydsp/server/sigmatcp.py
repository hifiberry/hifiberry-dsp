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
import argparse

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
    XmlProfile, ATTRIBUTE_VOL_CTL, ATTRIBUTE_SPDIF_ACTIVE, \
    get_default_dspprofile_path
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
from hifiberrydsp.api.restapi import run_api  # Import the REST API server
from hifiberrydsp.api.settings_store import SettingsStore
from hifiberrydsp.filtering.biquad import Biquad
import binascii
import shutil
# import hifiberrydsp

# Constants
DSP_PROFILES_DIRECTORY = "/usr/share/hifiberry/dspprofiles"

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


def find_and_restore_dsp_profile():
    """
    Find and restore the correct DSP profile from the profiles directory
    if the current profile is missing or has incorrect checksum
    """
    try:
        current_profile_path = dspprogramfile()
        
        # Check if current profile exists and has correct checksum
        profile_valid = False
        current_checksum = None
        
        if os.path.exists(current_profile_path):
            try:
                # Get DSP program checksums (try both SHA-1 and MD5)
                dsp_checksums = adau145x.Adau145x.calculate_program_checksums(mode="length", algorithms=["sha1", "md5"], cached=False)
                if not dsp_checksums:
                    # Fallback to signature-based if length-based fails
                    dsp_checksums = adau145x.Adau145x.calculate_program_checksums(mode="signature", algorithms=["sha1", "md5"], cached=False)
                
                if dsp_checksums:
                    dsp_checksum_sha1 = dsp_checksums.get("sha1")
                    dsp_checksum_md5 = dsp_checksums.get("md5")
                    
                    # Try to load current profile and check its checksums
                    try:
                        xml_profile = XmlProfile(current_profile_path)
                        
                        # Check SHA-1 checksum first (preferred)
                        profile_checksum_sha1 = xml_profile.get_meta("checksum_sha1")
                        if profile_checksum_sha1 and dsp_checksum_sha1:
                            if profile_checksum_sha1.upper() == dsp_checksum_sha1.upper():
                                profile_valid = True
                                logging.debug(f"Current DSP profile is valid with SHA-1 checksum {dsp_checksum_sha1}")
                        
                        # Fall back to MD5 checksum if SHA-1 not available or doesn't match
                        if not profile_valid:
                            profile_checksum_md5 = xml_profile.get_meta("checksum")
                            if profile_checksum_md5 and dsp_checksum_md5:
                                if profile_checksum_md5.upper() == dsp_checksum_md5.upper():
                                    profile_valid = True
                                    logging.debug(f"Current DSP profile is valid with MD5 checksum {dsp_checksum_md5}")
                                else:
                                    logging.info(f"DSP profile checksum mismatch: profile MD5={profile_checksum_md5}, DSP MD5={dsp_checksum_md5}")
                        
                        if not profile_valid:
                            checksums_info = []
                            if profile_checksum_sha1:
                                checksums_info.append(f"profile SHA-1={profile_checksum_sha1}")
                            if profile_checksum_md5:
                                checksums_info.append(f"profile MD5={profile_checksum_md5}")
                            if dsp_checksum_sha1:
                                checksums_info.append(f"DSP SHA-1={dsp_checksum_sha1}")
                            if dsp_checksum_md5:
                                checksums_info.append(f"DSP MD5={dsp_checksum_md5}")
                            logging.info(f"DSP profile checksum mismatch: {', '.join(checksums_info)}")
                            
                    except Exception as e:
                        logging.info(f"Error loading current DSP profile: {str(e)}")
                else:
                    logging.warning("Could not get DSP program checksums")
                    
            except Exception as e:
                logging.warning(f"Error validating current DSP profile: {str(e)}")
        else:
            logging.info(f"DSP profile file not found: {current_profile_path}")
        
        if profile_valid:
            return True
            
        # Profile is invalid or missing, search for correct one
        if not os.path.exists(DSP_PROFILES_DIRECTORY):
            logging.warning(f"DSP profiles directory not found: {DSP_PROFILES_DIRECTORY}")
            return False
            
        # Get target checksum from DSP (try both SHA-1 and MD5)
        dsp_checksums = adau145x.Adau145x.calculate_program_checksums(mode="length", algorithms=["sha1", "md5"], cached=False)
        if not dsp_checksums:
            # Fallback to signature-based if length-based fails
            dsp_checksums = adau145x.Adau145x.calculate_program_checksums(mode="signature", algorithms=["sha1", "md5"], cached=False)
        
        if not dsp_checksums:
            logging.warning("Could not get DSP program checksum for profile search")
            return False
            
        # Prefer SHA-1 over MD5 for matching
        target_checksum_sha1 = dsp_checksums.get("sha1")
        target_checksum_md5 = dsp_checksums.get("md5")
        
        if target_checksum_sha1:
            logging.info(f"Searching for DSP profile with SHA-1 checksum: {target_checksum_sha1}")
        elif target_checksum_md5:
            logging.info(f"Searching for DSP profile with MD5 checksum: {target_checksum_md5}")
        else:
            logging.warning("No valid checksums available for profile search")
            return False
        
        # Search for matching profile in profiles directory
        found_profile = None
        try:
            for filename in os.listdir(DSP_PROFILES_DIRECTORY):
                if filename.endswith('.xml'):
                    profile_path = os.path.join(DSP_PROFILES_DIRECTORY, filename)
                    try:
                        xml_profile = XmlProfile(profile_path)
                        
                        # Check SHA-1 checksum first (preferred)
                        profile_checksum_sha1 = xml_profile.get_meta("checksum_sha1")
                        if profile_checksum_sha1 and target_checksum_sha1:
                            if profile_checksum_sha1.upper() == target_checksum_sha1.upper():
                                found_profile = profile_path
                                logging.info(f"Found matching DSP profile (SHA-1): {filename}")
                                break
                        
                        # Fall back to MD5 checksum if SHA-1 not available or doesn't match
                        profile_checksum_md5 = xml_profile.get_meta("checksum")
                        if profile_checksum_md5 and target_checksum_md5:
                            if profile_checksum_md5.upper() == target_checksum_md5.upper():
                                found_profile = profile_path
                                logging.info(f"Found matching DSP profile (MD5): {filename}")
                                break
                            
                    except Exception as e:
                        logging.debug(f"Error checking profile {filename}: {str(e)}")
                        continue
        except Exception as e:
            logging.error(f"Error searching profiles directory: {str(e)}")
            return False
        
        if found_profile:
            try:
                # Ensure target directory exists
                target_dir = os.path.dirname(current_profile_path)
                os.makedirs(target_dir, exist_ok=True)
                
                # Copy the profile
                shutil.copy2(found_profile, current_profile_path)
                logging.info(f"Copied DSP profile from {found_profile} to {current_profile_path}")
                
                return True
            except Exception as e:
                logging.error(f"Error copying DSP profile: {str(e)}")
                return False
        else:
            checksums_msg = []
            if target_checksum_sha1:
                checksums_msg.append(f"SHA-1: {target_checksum_sha1}")
            if target_checksum_md5:
                checksums_msg.append(f"MD5: {target_checksum_md5}")
            logging.warning(f"No matching DSP profile found in {DSP_PROFILES_DIRECTORY} for checksums: {', '.join(checksums_msg)}")
            return False
        
    except Exception as e:
        logging.error(f"Error in find_and_restore_dsp_profile: {str(e)}")
        return False
    

class SigmaTCPHandler(BaseRequestHandler):

    checksum = None
    dsp = adau145x.Adau145x
    dspprogramfile = get_default_dspprofile_path()
    parameterfile = parameterfile()
    alsasync = None
    lgsoundsync = None
    updating = False
    xml = None
    checksum_error = False
    autoload_filters = True  # Default to True, can be disabled via command line
    debug_memory_writes = False  # Debug logging for memory writes

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
        logging.info("reading XML file %s", SigmaTCPHandler.dspprogramfile)
        SigmaTCPHandler.xml = XmlProfile(SigmaTCPHandler.dspprogramfile)
        
        # Check SHA-1 checksum first (preferred)
        cs_sha1 = SigmaTCPHandler.xml.get_meta("checksum_sha1")
        cs_md5 = SigmaTCPHandler.xml.get_meta("checksum")
        
        logging.debug("SHA-1 checksum from XML: %s", cs_sha1)
        logging.debug("MD5 checksum from XML: %s", cs_md5)
        
        # Get memory checksums
        try:
            # Try length-based checksums first
            memory_checksums = adau145x.Adau145x.calculate_program_checksums(mode="length", algorithms=["sha1", "md5"], cached=True)
            if not memory_checksums:
                # Fallback to signature-based checksums
                memory_checksums = adau145x.Adau145x.calculate_program_checksums(mode="signature", algorithms=["sha1", "md5"], cached=True)
            
            memory_checksum_sha1 = memory_checksums.get("sha1")
            memory_checksum_md5 = memory_checksums.get("md5")
            
            logging.debug("SHA-1 checksum from memory: %s", memory_checksum_sha1)
            logging.debug("MD5 checksum from memory: %s", memory_checksum_md5)
            
        except Exception as e:
            logging.error(f"Error calculating memory checksums: {str(e)}")
            memory_checksum_sha1 = None
            memory_checksum_md5 = None
        
        # Check checksums with priority: SHA-1 first, then MD5
        checksum_match = False
        if cs_sha1 and memory_checksum_sha1:
            if cs_sha1.upper() == memory_checksum_sha1.upper():
                checksum_match = True
                logging.info("SHA-1 checksums match")
            else:
                logging.warning(f"SHA-1 checksum mismatch: XML={cs_sha1}, memory={memory_checksum_sha1}")
        
        # Fall back to MD5 if SHA-1 doesn't match or isn't available
        if not checksum_match and cs_md5 and memory_checksum_md5:
            # Convert memory checksum to bytes format for backward compatibility
            try:
                memory_checksum_md5_bytes = bytes.fromhex(memory_checksum_md5)
                SigmaTCPHandler.checksum_xml = bytearray()
                for i in range(0, len(cs_md5), 2):
                    octet = int(cs_md5[i:i + 2], 16)
                    SigmaTCPHandler.checksum_xml.append(octet)
                
                if SigmaTCPHandler.checksum_xml == memory_checksum_md5_bytes:
                    checksum_match = True
                    logging.info("MD5 checksums match")
                else:
                    logging.warning(f"MD5 checksum mismatch: XML={cs_md5}, memory={memory_checksum_md5}")
            except Exception as e:
                logging.error(f"Error comparing MD5 checksums: {str(e)}")
        
        # Handle checksum validation result
        if cs_sha1 or cs_md5:
            if not checksum_match:
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
        
        logging.debug("Handle read %s/%s", addr, length)

        spi_response = adau145x.Adau145x.read_memory(addr, length)
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
        
        # Extract memory data first
        memdata = data[14:]
        
        # Debug logging for memory writes if enabled
        if SigmaTCPHandler.debug_memory_writes:
            logging.info(f"DEBUG: Memory write to address 0x{addr:04X} ({addr}), length: {length} bytes")
            if length <= 20:  # Log data for small writes
                hex_data = ' '.join(f'{b:02X}' for b in memdata[:20])
                logging.info(f"DEBUG: Write data: {hex_data}")
            else:
                hex_data = ' '.join(f'{b:02X}' for b in memdata[:16])
                logging.info(f"DEBUG: Write data (first 16 bytes): {hex_data}...")
        
        res = adau145x.Adau145x.write_memory(addr, memdata)

        if addr == SigmaTCPHandler.dsp.HIBERNATE_REGISTER and \
                SigmaTCPHandler.updating and memdata == b'\00\00':
            logging.debug(
                "set HIBERNATE to 0 seen, guessing update is done")
            SigmaTCPHandler.finish_update()

        return res

    @staticmethod
    def write_eeprom_content(xmldata):
        logging.info("writing XML file through Adau145x implementation")
        result = adau145x.Adau145x.write_eeprom_content(xmldata)
        
        # After the EEPROM write is done, set internal state as needed
        if result:  # Success
            SigmaTCPHandler.finish_update()
            return b'\01'  # Convert True to binary 1
        else:
            return b'\00'  # Convert False to binary 0

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
        checksum = adau145x.Adau145x.calculate_program_checksum(cached=True)
        memory = adau145x.Adau145x.get_data_memory()
        logging.info("store: writing memory dump to file")
        SigmaTCPHandler.store_parameters(checksum, memory)

    @staticmethod
    def restore_data_memory():

        logging.info("restore: checking checksum")
        checksum = adau145x.Adau145x.calculate_program_checksum(cached=False)
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
        adau145x.Adau145x.kill_dsp()
        adau145x.Adau145x.write_memory(dsp.DATA_ADDR, memory)
        # Restart the core
        adau145x.Adau145x.start_dsp()

    @staticmethod
    def get_memory_block(addr, length):
        return adau145x.Adau145x.get_memory_block(addr, length)

    @staticmethod
    def get_program_memory():
        '''
        Get the program memory from the DSP
        '''
        return adau145x.Adau145x.get_program_memory()

    @staticmethod
    def get_data_memory():
        '''
        Get the data memory from the DSP
        '''
        return adau145x.Adau145x.get_data_memory()

    @staticmethod
    def program_checksum(cached=True):
        return adau145x.Adau145x.calculate_program_checksum(cached=cached)

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
        adau145x.Adau145x.kill_dsp()

    @staticmethod
    def _start_dsp():
        adau145x.Adau145x.start_dsp()

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
        adau145x.Adau145x.clear_checksum_cache()
        
        # Also clear REST API checksum cache
        try:
            from hifiberrydsp.api.restapi import clear_checksum_cache
            clear_checksum_cache()
        except ImportError:
            # REST API might not be available
            pass
            
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

    @staticmethod
    def load_and_apply_filters(type="sha1"):
        """
        Automatically load and apply stored filters for the current DSP profile checksum
        
        Args:
            type (str): Checksum type to use - "sha1" (length-based, default) or "md5" (signature-based)
        """
        try:
            # Validate checksum type parameter
            if type not in ["md5", "sha1"]:
                logging.error(f"Invalid checksum type '{type}'. Must be 'md5' or 'sha1'")
                return False
            
            # Get current DSP program checksum based on type
            if type == "md5":
                # MD5 with signature-based detection (legacy compatibility)
                checksum_bytes = adau145x.Adau145x.calculate_program_checksum(cached=True)
                if not checksum_bytes:
                    logging.warning("Could not get DSP program MD5 checksum for filter autoloading")
                    return False
                checksum_hex = binascii.hexlify(checksum_bytes).decode('utf-8').upper()
                logging.info(f"Autoloading filters for DSP profile MD5 checksum (signature-based): {checksum_hex}")
            else:  # type == "sha1"
                # SHA-1 with length-based detection (modern approach)
                checksums = adau145x.Adau145x.calculate_program_checksums(mode="length", algorithms=["sha1"], cached=True)
                if not checksums or "sha1" not in checksums:
                    logging.warning("Could not get DSP program SHA-1 checksum for filter autoloading")
                    return False
                checksum_hex = checksums["sha1"]
                logging.info(f"Autoloading filters for DSP profile SHA-1 checksum (length-based): {checksum_hex}")
            
            # Initialize settings store for direct access
            settings_store = SettingsStore()
            
            # Get stored filters and memory settings for this checksum
            filters = settings_store.load_filters(checksum_hex)
            memory_settings = settings_store.load_memory_settings(checksum_hex)
            
            total_settings = len(filters) + len(memory_settings)
            if total_settings == 0:
                logging.info(f"No stored settings found for checksum {checksum_hex}")
                return True
                
            logging.info(f"Found {len(filters)} filters and {len(memory_settings)} memory settings for current profile")
            
            # Get the XML profile to resolve metadata keys if needed
            xml_profile = SigmaTCPHandler.get_checked_xml()
            
            settings_applied = 0
            
            # First apply memory settings
            for memory_address, memory_data in memory_settings.items():
                try:
                    success = SigmaTCPHandler._apply_memory_setting_new(memory_address, memory_data)
                    if success:
                        settings_applied += 1
                        logging.debug(f"Applied memory setting at {memory_address}")
                    else:
                        logging.warning(f"Failed to apply memory setting at {memory_address}")
                except Exception as e:
                    logging.error(f"Error applying memory setting {memory_address}: {str(e)}")
                    continue
            
            # Then apply filter settings
            for filter_key, filter_data in filters.items():
                try:
                    # This is a regular filter
                    address = filter_data.get("address")
                    offset = filter_data.get("offset", 0)
                    is_bypassed = filter_data.get("bypassed", False)
                    filter_spec = filter_data.get("filter", {})
                    
                    if not address or not filter_spec:
                        logging.warning(f"Skipping invalid filter {filter_key}: missing address or filter data")
                        continue
                    
                    # Resolve address from metadata if it's a string key
                    base_address = None
                    if isinstance(address, str) and not address.startswith('0x') and not address.isdigit():
                        # Try to resolve from metadata
                        if xml_profile:
                            metadata_value = xml_profile.get_meta(address)
                            if metadata_value and '/' in str(metadata_value):
                                # Parse biquad format like "addr/offset"
                                parts = str(metadata_value).split('/')
                                try:
                                    base_address = int(parts[0])
                                except ValueError:
                                    logging.warning(f"Could not parse address from metadata key {address}: {metadata_value}")
                                    continue
                            else:
                                logging.warning(f"Could not resolve address from metadata key {address}")
                                continue
                        else:
                            logging.warning(f"No XML profile available to resolve metadata key {address}")
                            continue
                    else:
                        # Direct address
                        try:
                            base_address = int(address, 0)  # Supports hex and decimal
                        except ValueError:
                            logging.warning(f"Could not parse direct address {address}")
                            continue
                    
                    # Calculate actual address with offset
                    actual_address = base_address + (offset * 5)
                    
                    # Check if address is valid
                    if not adau145x.Adau145x.is_valid_memory_address(actual_address) or \
                       not adau145x.Adau145x.is_valid_memory_address(actual_address + 4):
                        logging.warning(f"Skipping filter {filter_key}: invalid memory address range {hex(actual_address)}")
                        continue
                    
                    # Apply the filter (original or bypass based on state)
                    if is_bypassed:
                        # Apply bypass filter
                        success = SigmaTCPHandler._apply_bypass_filter(actual_address)
                        filter_type = "bypassed"
                    else:
                        # Apply original filter
                        success = SigmaTCPHandler._apply_filter(actual_address, filter_spec)
                        filter_type = "active"
                    
                    if success:
                        settings_applied += 1
                        logging.debug(f"Applied {filter_type} filter {filter_key} at address {hex(actual_address)}")
                    else:
                        logging.warning(f"Failed to apply filter {filter_key} at address {hex(actual_address)}")
                        
                except Exception as e:
                    logging.error(f"Error applying filter {filter_key}: {str(e)}")
                    continue
            
            logging.info(f"Successfully applied {settings_applied} out of {total_settings} stored settings ({len(memory_settings)} memory + {len(filters)} filters)")
            return settings_applied > 0
            
        except Exception as e:
            logging.error(f"Error during filter autoloading: {str(e)}")
            return False
    
    @staticmethod
    def _apply_memory_setting(setting_key, setting_data):
        """
        Apply a memory setting from the filter store
        
        Args:
            setting_key (str): The setting key 
            setting_data (dict): The setting data containing address and values
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            filter_spec = setting_data.get("filter", {})
            if filter_spec.get("type") != "memory":
                return False
            
            # Extract memory setting information
            address_str = filter_spec.get("address")
            values = filter_spec.get("values", [])
            
            if not address_str or not values:
                logging.warning(f"Memory setting {setting_key} missing address or values")
                return False
            
            # Parse address (same logic as REST API)
            try:
                address = int(address_str, 0)  # Auto-detect hex/decimal
            except ValueError:
                logging.warning(f"Could not parse address {address_str} for memory setting {setting_key}")
                return False
            
            # Validate address range
            if not adau145x.Adau145x.is_valid_memory_address(address):
                logging.warning(f"Invalid address {hex(address)} for memory setting {setting_key}")
                return False
            
            # Apply each value
            success_count = 0
            for i, value in enumerate(values):
                current_addr = address + i
                
                if not adau145x.Adau145x.is_valid_memory_address(current_addr):
                    logging.warning(f"Invalid address {hex(current_addr)} in memory setting {setting_key}")
                    continue
                
                try:
                    # Convert value to int (same logic as REST API)
                    if isinstance(value, str) and value.startswith("0x"):
                        int_value = int(value, 16)  # Hexadecimal
                    elif isinstance(value, (float, int)):
                        if isinstance(value, float):
                            int_value = adau145x.Adau145x.decimal_repr(value)  # Convert float to fixed-point
                        else:
                            int_value = value
                    else:
                        logging.warning(f"Unsupported value type {type(value)} in memory setting {setting_key}")
                        continue
                    
                    # Write to DSP memory
                    byte_data = adau145x.Adau145x.int_data(int_value, 4)
                    adau145x.Adau145x.write_memory(current_addr, byte_data)
                    success_count += 1
                    
                except Exception as e:
                    logging.warning(f"Error writing value {value} to address {hex(current_addr)}: {str(e)}")
                    continue
            
            if success_count > 0:
                logging.debug(f"Applied memory setting {setting_key}: {success_count}/{len(values)} values written to address {hex(address)}")
                return True
            else:
                logging.warning(f"No values successfully written for memory setting {setting_key}")
                return False
                
        except Exception as e:
            logging.error(f"Error applying memory setting {setting_key}: {str(e)}")
            return False

    @staticmethod
    def _apply_memory_setting_new(memory_address, memory_data):
        """
        Apply a memory setting from the new settings store structure
        
        Args:
            memory_address (str): The memory address key
            memory_data (dict): The memory data containing address and values
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Extract memory setting information from new structure
            address_str = memory_data.get("address")
            values = memory_data.get("values", [])
            
            if not address_str or not values:
                logging.warning(f"Memory setting at {memory_address} missing address or values")
                return False
            
            # Parse address (same logic as REST API)
            try:
                address = int(address_str, 0)  # Auto-detect hex/decimal
            except ValueError:
                logging.warning(f"Could not parse address {address_str} for memory setting at {memory_address}")
                return False
            
            # Validate address range
            if not adau145x.Adau145x.is_valid_memory_address(address):
                logging.warning(f"Invalid address {hex(address)} for memory setting at {memory_address}")
                return False
            
            # Apply each value
            success_count = 0
            for i, value in enumerate(values):
                current_addr = address + i
                
                if not adau145x.Adau145x.is_valid_memory_address(current_addr):
                    logging.warning(f"Invalid address {hex(current_addr)} in memory setting at {memory_address}")
                    continue
                
                try:
                    # Convert value to int (same logic as REST API)
                    if isinstance(value, str) and value.startswith("0x"):
                        int_value = int(value, 16)  # Hexadecimal
                    elif isinstance(value, (float, int)):
                        if isinstance(value, float):
                            int_value = adau145x.Adau145x.decimal_repr(value)  # Convert float to fixed-point
                        else:
                            int_value = value
                    else:
                        logging.warning(f"Unsupported value type {type(value)} in memory setting at {memory_address}")
                        continue
                    
                    # Write to DSP memory
                    byte_data = adau145x.Adau145x.int_data(int_value, 4)
                    adau145x.Adau145x.write_memory(current_addr, byte_data)
                    success_count += 1
                    
                except Exception as e:
                    logging.warning(f"Error writing value {value} to address {hex(current_addr)}: {str(e)}")
                    continue
            
            if success_count > 0:
                logging.debug(f"Applied memory setting at {memory_address}: {success_count}/{len(values)} values written to address {hex(address)}")
                return True
            else:
                logging.warning(f"No values successfully written for memory setting at {memory_address}")
                return False
                
        except Exception as e:
            logging.error(f"Error applying memory setting at {memory_address}: {str(e)}")
            return False

    @staticmethod
    def _apply_filter(address, filter_spec):
        """
        Apply a single filter at the specified address
        
        Args:
            address (int): Memory address to write the filter to
            filter_spec (dict): Filter specification
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if this is direct coefficients or a filter specification
            if all(k in filter_spec for k in ['a0', 'a1', 'a2', 'b0', 'b1', 'b2']):
                # Direct coefficients
                a0 = float(filter_spec['a0'])
                a1 = float(filter_spec['a1']) 
                a2 = float(filter_spec['a2'])
                b0 = float(filter_spec['b0'])
                b1 = float(filter_spec['b1'])
                b2 = float(filter_spec['b2'])
                
                # Create and write biquad
                bq = Biquad(a0, a1, a2, b0, b1, b2, "Autoloaded filter")
                adau145x.Adau145x.write_biquad(address, bq)
                return True
                
            elif 'type' in filter_spec:
                # Filter specification - need to calculate coefficients
                # This requires importing Filter class and sample rate
                try:
                    from hifiberrydsp.api.filters import Filter
                    import json
                    
                    # Get sample rate from profile or guess it
                    sample_rate = 48000  # Default fallback
                    try:
                        xml_profile = SigmaTCPHandler.get_checked_xml()
                        if xml_profile:
                            sample_rate = xml_profile.samplerate() or 48000
                    except:
                        # Try to guess from DSP
                        try:
                            sample_rate = adau145x.Adau145x.guess_samplerate() or 48000
                        except:
                            pass
                    
                    # Create filter object
                    filter_json = json.dumps(filter_spec)
                    filter_obj = Filter.fromJSON(filter_json)
                    
                    # Calculate coefficients
                    coeffs = filter_obj.biquadCoefficients(sample_rate)
                    if not coeffs or len(coeffs) != 6:
                        logging.error("Invalid coefficients returned from filter")
                        return False
                    
                    # Extract coefficients (Filter returns b0,b1,b2,a0,a1,a2)
                    b0, b1, b2, a0, a1, a2 = coeffs
                    
                    # Create and write biquad
                    description = f"{filter_spec.get('type', 'Filter')} at {filter_spec.get('f', '')}Hz"
                    bq = Biquad(a0, a1, a2, b0, b1, b2, description)
                    adau145x.Adau145x.write_biquad(address, bq)
                    return True
                    
                except Exception as e:
                    logging.error(f"Error processing filter specification: {str(e)}")
                    return False
            else:
                logging.error("Invalid filter format: expected direct coefficients or filter specification")
                return False
                
        except Exception as e:
            logging.error(f"Error applying filter at address {hex(address)}: {str(e)}")
            return False
    
    @staticmethod
    def _apply_bypass_filter(address):
        """
        Apply a bypass filter at the specified address
        
        Args:
            address (int): Memory address to write the bypass filter to
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create bypass filter (unity coefficients)
            from hifiberrydsp.api.filters import Bypass
            bypass_filter = Bypass()
            coeffs = bypass_filter.biquadCoefficients(48000)  # Sample rate doesn't matter for bypass
            
            # Extract coefficients (Filter returns b0,b1,b2,a0,a1,a2)
            b0, b1, b2, a0, a1, a2 = coeffs
            
            # Create and write bypass biquad
            bq = Biquad(a0, a1, a2, b0, b1, b2, "Autoloaded bypass filter")
            adau145x.Adau145x.write_biquad(address, bq)
            return True
            
        except Exception as e:
            logging.error(f"Error applying bypass filter at address {hex(address)}: {str(e)}")
            return False


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
        
        # Autoload filters for the new profile if enabled
        if SigmaTCPHandler.autoload_filters:
            try:
                logging.info("Reloading stored filters after DSP program update")
                SigmaTCPHandler.load_and_apply_filters()
            except Exception as e:
                logging.error(f"Error reloading filters after update: {str(e)}")
        else:
            logging.debug("Filter autoloading disabled")
        
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

        params = self.parse_config()

        # Determine the host to bind to
        if params["bind_address"]:
            bind_host = params["bind_address"]
        elif params["localhost"]:
            bind_host = "localhost"
        else:
            bind_host = "0.0.0.0"

        logging.info(f"Starting SigmaTCP server on {bind_host}:{DEFAULT_PORT}")
        self.server = SigmaTCPServer(server_address=(bind_host, DEFAULT_PORT))

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

        # Set the autoload filters flag
        SigmaTCPHandler.autoload_filters = not params.get("no_autoload_filters", False)
        
        # Set the debug memory writes flag
        SigmaTCPHandler.debug_memory_writes = params.get("debug", False)
        if SigmaTCPHandler.debug_memory_writes:
            logging.info("Debug mode enabled: will log all DSP memory writes")

        self.params = params
        
    def parse_config(self):
        config = configparser.ConfigParser()
        config.optionxform = lambda option: option

        config.read("/etc/sigmatcp.conf")

        params = {}

        # Parse command-line arguments
        parser = argparse.ArgumentParser(description="SigmaTCP Server")
        parser.add_argument("--alsa", action="store_true", help="Enable ALSA volume control")
        parser.add_argument("--lgsoundsync", action="store_true", help="Enable LG Sound Sync")
        parser.add_argument("--enable-rest", action="store_true", help="Enable REST API server")
        parser.add_argument("--disable-tcp", action="store_true", help="Disable SigmaTCP server (only useful with --enable-rest)")
        parser.add_argument("--store", action="store_true", help="Store data memory to a file on exit")
        parser.add_argument("--restore", action="store_true", help="Restore saved data memory")
        parser.add_argument("--localhost", action="store_true", help="Bind to localhost only")
        parser.add_argument("--bind-address", type=str, default=None, help="Specify IP address to bind to")
        parser.add_argument("--no-autoload-filters", action="store_true", help="Disable automatic loading of stored filters on startup")
        parser.add_argument("--debug", action="store_true", help="Enable debug logging for all DSP memory writes")
        parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
        args = parser.parse_args()

        params["alsa"] = args.alsa
        params["lgsoundsync"] = args.lgsoundsync
        params["enable_rest"] = args.enable_rest
        params["disable_tcp"] = args.disable_tcp
        params["store"] = args.store
        params["restore"] = args.restore
        params["verbose"] = args.verbose
        params["localhost"] = args.localhost
        params["bind_address"] = args.bind_address
        params["no_autoload_filters"] = args.no_autoload_filters
        params["debug"] = args.debug

        try:
            this.command_after_startup = config.get("server", "command_after_startup")
        except:
            this.command_after_startup = None

        try:
            this.notify_on_updates = config.get("server", "notify_on_updates")
        except:
            this.notify_on_updates = None

        # Override any previous logging configuration
        logging.basicConfig(level=logging.DEBUG if params["verbose"] else logging.INFO, force=True)

        return params
            
    def run(self):
        
        # Check if a DSP is detected
        dsp_detected = adau145x.Adau145x.detect_dsp()
        if dsp_detected:
            logging.info("detected ADAU14xx DSP")
            this.dsp="ADAU14xx"
        else:
            logging.info("did not detect ADAU14xx DSP")
            this.dsp=""
        
        # Find and restore correct DSP profile if needed
        if dsp_detected:
            logging.info("Checking DSP profile integrity...")
            find_and_restore_dsp_profile()
            
        if (self.restore):
            try:
                logging.info("restoring saved data memory")
                SigmaTCPHandler.restore_data_memory()
                SigmaTCPHandler.finish_update()
            except IOError:
                logging.info("no saved data found")

        # Autoload filters for the current profile unless disabled
        if not self.params.get("no_autoload_filters", False):
            logging.info("Autoloading stored filters for current DSP profile")
            try:
                SigmaTCPHandler.load_and_apply_filters()
            except Exception as e:
                logging.error(f"Error during filter autoloading: {str(e)}")
        else:
            logging.info("Filter autoloading disabled by --no-autoload-filters option")

        logging.debug("done")
        
        logging.info(this.command_after_startup)
        notifier_thread = Thread(target = startup_notify)
        notifier_thread.start()
        
        if self.params.get("enable_rest"):
            # Use the same bind address for REST API
            if self.params.get("bind_address"):
                rest_host = self.params.get("bind_address")
            elif self.params.get("localhost"):
                rest_host = "localhost"
            else:
                rest_host = "0.0.0.0"
                
            logging.info(f"Starting REST API server on {rest_host}:13141")
            rest_thread = Thread(target=run_api, kwargs={"host": rest_host, "port": 13141})
            rest_thread.daemon = True
            rest_thread.start()

        try:
            if not(self.abort) and not(self.params.get("disable_tcp")):
                logging.info("starting TCP server")
                self.server.serve_forever()
            elif self.params.get("disable_tcp") and self.params.get("enable_rest"):
                logging.info("TCP server disabled, running REST API only")
                # Keep main thread alive for REST API
                while True:
                    time.sleep(1)
            else:
                logging.warning("Both TCP server and REST API are disabled. Nothing to do!")
        except KeyboardInterrupt:
            logging.info("aborting ")
            if not self.params.get("disable_tcp"):
                self.server.server_close()

        if SigmaTCPHandler.alsasync is not None:
            SigmaTCPHandler.alsasync.finish()

        if SigmaTCPHandler.lgsoundsync is not None:
            SigmaTCPHandler.lgsoundsync.finish()

        if self.params.get("store"):
            try:
                logging.info("saving DSP data memory")
                SigmaTCPHandler.save_data_memory()
            except Exception as e:
                logging.error("Error saving DSP data memory: %s", e)
