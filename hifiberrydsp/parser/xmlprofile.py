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

from collections import OrderedDict

from hifiberrydsp.hardware.adau145x import Adau145x
from hifiberrydsp.datatools import parse_int_length

ATTRIBUTE_CHECKSUM = "checksum"
ATTRIBUTE_VOL_CTL = "volumeControlRegister"
ATTRIBUTE_VOL_LIMIT = "volumeLimitRegister"
ATTRIBUTE_VOL_LIMIT_PI = "volumeLimitPiRegister"
ATTRIBUTE_VOL_LIMIT_SPDIF = "volumeLimitSPDIFRegister"
ATTRIBUTE_VOL_LIMIT_AUX = "volumeLimitAuxRegister"
ATTRIBUTE_INPUT_SELECT = "inputSelectRegister"
ATTRIBUTE_MUTE_PI = "mutePiRegister"
ATTRIBUTE_MUTE_SPDIF = "muteSPDIFRegister"
ATTRIBUTE_MUTE_AUX = "muteAuxRegister"
ATTRIBUTE_BALANCE = "balanceRegister"
ATTRIBUTE_LOUDNESS = "loudnessRegister"
ATTRIBUTE_LOUDNESS_LEVELS = "loudnessLevelRegisters"
ATTRIBUTE_VOL_RANGE = "volumeControlRangeDb"
ATTRIBUTE_IIR_FILTER_LEFT = "IIR_L"
ATTRIBUTE_IIR_FILTER_RIGHT = "IIR_R"
ATTRIBUTE_TONECONTROL_FILTER_LEFT = "toneControlLeftRegisters"
ATTRIBUTE_TONECONTROL_FILTER_RIGHT = "toneControlRightRegisters"
ATTRIBUTE_CUSTOM_FILTER_LEFT = "customFilterRegisterBankLeft"
ATTRIBUTE_CUSTOM_FILTER_RIGHT = "customFilterRegisterBankRight"
ATTRIBUTE_FIR_FILTER_LEFT = "FIR_L"
ATTRIBUTE_FIR_FILTER_RIGHT = "FIR_R"
ATTRIBUTE_MUTE_REG = "muteRegister"
ATTRIBUTE_INVERT_MUTE = "invertMuteRegister"
ATTRIBUTE_SPDIF_SOURCE = "spdifSource"
ATTRIBUTE_SAMPLERATE = "samplerate"
ATTRIBUTE_SAMPLERATE_CAP = "sampleRate"
ATTRIBUTE_CHANNEL_SELECT = "channelSelectRegister"
ATTRIBUTE_AUTOMUTE = "automute"
ATTRIBUTE_AUTOMUTE_LEVEL = "automuteLevel"
ATTRIBUTE_UNMUTE_DELAY = "unmuteDelay"
ATTRIBUTE_SPDIF_ENABLE = "enableSPDIFRegister"
ATTRIBUTE_SPDIF_ACTIVE = "readSPDIFOnRegister"

# A list of all metadata attributes that refer to registers
REGISTER_ATTRIBUTES = [ATTRIBUTE_CHANNEL_SELECT,
                       ATTRIBUTE_BALANCE,
                       ATTRIBUTE_FIR_FILTER_LEFT,
                       ATTRIBUTE_FIR_FILTER_RIGHT,
                       ATTRIBUTE_IIR_FILTER_LEFT,
                       ATTRIBUTE_IIR_FILTER_RIGHT,
                       ATTRIBUTE_MUTE_REG,
                       ATTRIBUTE_VOL_CTL,
                       ATTRIBUTE_VOL_LIMIT,
                       ATTRIBUTE_INVERT_MUTE,
                       ATTRIBUTE_SPDIF_SOURCE,
                       ATTRIBUTE_AUTOMUTE,
                       ATTRIBUTE_AUTOMUTE_LEVEL,
                       ATTRIBUTE_VOL_LIMIT_PI,
                       ATTRIBUTE_VOL_LIMIT_SPDIF,
                       ATTRIBUTE_VOL_LIMIT_AUX,
                       ATTRIBUTE_MUTE_PI,
                       ATTRIBUTE_MUTE_SPDIF,
                       ATTRIBUTE_MUTE_AUX,
                       ATTRIBUTE_UNMUTE_DELAY,
                       ATTRIBUTE_SPDIF_ENABLE,
                       ATTRIBUTE_LOUDNESS]

MEMTYPE = {
    0: "DM0",
    1: "DM1",
    2: "PM",
}


def replace_in_memory_block(data, startaddr, replace_dict):
    """
    Replace memory cells in memory write commands in an XML profile
    This function won't be applied to EEPROM write commands!
    """
    cell_len = Adau145x.cell_len(startaddr)
    
    assert len(data) % cell_len == 0

    endaddr = startaddr + len(data) / cell_len

    for repl_addr in replace_dict.keys():
        if repl_addr >= startaddr and repl_addr <= endaddr:
            content = replace_dict[repl_addr]

            if len(content) != cell_len:
                logging.error("Cell %s: content len is %s but cell len is %s, ignoring",
                              repl_addr, len(content), cell_len)
                continue

            assert len(content) == cell_len

            address_offset = (repl_addr - startaddr) * cell_len
            logging.debug(
                "replacing memory at address {} by {}", repl_addr, content)

            data[address_offset:address_offset +
                 len(content)] = content


class XmlProfile():

    def __init__(self, filename=None):
        self.dsp = Adau145x()
        self.doc = None
        self.filename = filename
        self.eeprom = DummyEepromWriter(self.dsp)
        if filename is not None:
            try:
                self.read_from_file(filename)
            except IOError:
                self.doc = None
                pass

    def read_from_file(self, filename):
        logging.info("reading profile %s", filename)
        try:
            with open(filename) as fd:
                self.doc = xmltodict.parse(fd.read(), dict_constructor=OrderedDict)
        except IOError:
            logging.error("can't read file %s", filename)
            return

        self.update()

    def read_from_text(self, xmlcontent):
        logging.info("parsing xml")
        self.doc = xmltodict.parse(xmlcontent)
        self.update()

    def update(self):
        page_address = None

        for action in self.doc["ROM"]["page"]["action"]:
            instr = action["@instr"]

            if instr == "writeXbytes":
                paramname = action["@ParamName"]

                data = []
                for d in action["#text"].split(" "):
                    value = int(d, 16)
                    data.append(value)

                if paramname == "g_PageAddress":
                    page_address = int.from_bytes(
                        data, byteorder='big', signed=False)

                if paramname.startswith("Page_"):
                    self.eeprom.write_eeprom(page_address, data)

    def replace_eeprom_cells(self, replace_dict):

        # First calculate new EEPROM content
        new_eeprom = self.eeprom.replace_memory_data(replace_dict)

        page_address = None

        for action in self.doc["ROM"]["page"]["action"]:
            instr = action["@instr"]

            if instr == "writeXbytes":
                paramname = action["@ParamName"]

                data = []
                for d in action["#text"].split(" "):
                    value = int(d, 16)
                    data.append(value)

                if paramname == "g_PageAddress":
                    page_address = int.from_bytes(
                        data, byteorder='big', signed=False)

                if paramname.startswith("Page_"):
                    # Get the new EEPROM contents
                    end_addr = page_address + len(data)
                    new_data = new_eeprom[page_address:end_addr]
                    new_data_str = ''.join(
                        '%02X ' % octet for octet in new_data).strip()
                    action["#text"] = new_data_str

    def replace_ram_cells(self, replace_dict):

        # Set this to true after the EEPROM programming has been detected
        eeprom_write_done = False

        for action in self.doc["ROM"]["page"]["action"]:
            instr = action["@instr"]
            paramname = action["@ParamName"]

            if paramname.startswith("Page_"):
                eeprom_write_done = True

            if eeprom_write_done and instr == "writeXbytes":
                addr = int(action["@addr"])
                data = []
                for d in action["#text"].split(" "):
                    value = int(d, 16)
                    data.append(value)

                for _name, saddr in self.dsp.START_ADDRESS.items():
                    if addr == saddr:
                        replace_in_memory_block(data,
                                                addr,
                                                replace_dict)
                        new_data_str = ''.join(
                            '%02X ' % octet for octet in data).strip()
                        action["#text"] = new_data_str

    def get_meta(self, name):
        for metadata in self.doc["ROM"]["beometa"]["metadata"]:
            t = metadata["@type"]
            if (t == name):
                return metadata["#text"]

    def get_storable_registers(self):
        storables = []
        for metadata in self.doc["ROM"]["beometa"]["metadata"]:
            try:
                storable = metadata["@storable"]
                if storable is not None:
                    storable = storable.lower()

                if (storable in ["y", "yes", "1", "true"]):
                    storables.append(metadata["@type"])
            except KeyError:
                pass

        return storables

    def get_addr_length(self, attribute):
        addr = self.get_meta(attribute)
        return parse_int_length(addr)

    def update_metadata(self, metadata_dict):

        md = dict(metadata_dict)
        try:
            beometa = self.doc["ROM"]["beometa"]
        except KeyError:
            self.doc["ROM"]["beometa"] = OrderedDict()
            self.doc["ROM"]["beometa"]["metadata"] = OrderedDict()
            self.doc["ROM"].move_to_end('beometa', last=False)
            beometa = self.doc["ROM"]["beometa"]

        md_new = []

        # First replace existing metadata
        for metadata in beometa["metadata"]:
            attribute = metadata["@type"]
            if attribute in md:
                md_new.append(OrderedDict([('@type', attribute),
                                           ('@storable', "yes"),
                                           ('#text', metadata_dict[attribute])]))
                del md[attribute]
            else:
                md_new.append(metadata)

        # Insert remaining attributes
        for attribute in md:
            md_new.append(OrderedDict([('@type', attribute),
                                       ('#text', md[attribute])]))

        beometa["metadata"] = md_new

    def samplerate(self):
        try:
            return int(self.get_meta("samplerate"))
        except TypeError:
            return 48000

    def write_xml(self, filename):
        outfile = open(filename, "w")
        outfile.write(xmltodict.unparse(self.doc, pretty=True))

    def __str__(self):
        if self.doc is None:
            return ""
        else:
            return xmltodict.unparse(self.doc, pretty=True)


class DummyEepromWriter():
    """
    This class simulates an EEPROM. 
    It accepts SigmaStudio write commands and stored the content in memory.
    This allows to modify these data and patch EEPROM write command by replacing some memory cells.
    """

    def __init__(self, dsp):
        self.memory = dict()
        self.end_addr = 0
        self.bytes = None
        self.dsp = dsp

    def write_eeprom(self, addr, values):
        """
        Writes a list of values to EEPROM memory. Also keeps track of the highest address ever seen
        """
        for v in values:
            self.memory[addr] = v
            addr += 1

        if addr > self.end_addr:
            self.end_addr = addr

        self.byte = None

    def as_bytes(self):
        """
        Return the full EEPROM content as a bytearray
        """
        if self.bytes is not None:
            return self.bytes

        res = bytearray()
        for i in range(0, self.end_addr):
            res.append(self.memory[i])
        self.bytes = res
        return res

    def get_header(self):
        """
        Get the EEPROM header bytes (16 byte). 
        For the format, check the documentation in the ADAU1452 data sheet
        """
        return self.as_bytes()[0:16]

    def first_block_addr(self):
        """
        Extract the address of the first block from the header
        """
        return int.from_bytes(self.get_header()[1:4],
                              byteorder='big',
                              signed=False)

    def calc_checksum(self, eeprom_content):
        """
        Calculate a checksum of the full EEPROM content that needs to
        be stored at the end of the EEPROM data.
        Without a correct checksum, a DSP will not accept the EEPROM
        data
        """
        checksum = 0
        end = len(eeprom_content)

        assert end % 4 == 0

        addr = 0
        while (addr < end):
            word = int.from_bytes(
                eeprom_content[addr:addr + 4], byteorder='big', signed=False)
            checksum += word
            addr += 4

        return checksum
    
    
    def has_pattern_at_addr(self, address, pattern):
        """
        Check if memory cells starting at a given address match a specific pattern
        """

        if address + len(pattern) > self.end_addr:
            return False
        
        for offset in range(0,len(pattern)):
            pval = pattern[offset]
            mem = self.memory[address+offset]
            if pval != mem:
                return False
            else:
                logging.error("found word %s", offset)
            
        return True
  
    def find_pattern(self, pattern, start_addr = 0):
        """ 
        Loop through memory and check if a specific pattern of 4-byte words can be found
        """
        for addr in range(start_addr,self.end_addr):
            if self.has_pattern_at_addr(addr, pattern):
                return addr
        
 
    def find_register_position(self, register_address, start_addr = 0):
        """
        Find a register setting in the EEPROM code. This is some guesswork and it might 
        also replace data that are NOT register settings as registers aren't clearly
        stored in EEPROM, but will be set from the DSP program. Therefore this routine
        searches for "write register" patterns in the EEPROM code. 
        """
        
        r_low = register_address & 0xff
        r_high = register_address >> 8
        
        start_pattern = [0x00, 0x00, r_high, r_low, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00]
        end_pattern = [0x00, 0x00, 0x00]
        end_pattern_offset = 12

        while start_addr < self.end_addr:
        
            position = self.find_pattern(start_pattern, start_addr)
            if position is None:
                return None
            
            if not(self.has_pattern_at_addr(position + end_pattern_offset, end_pattern)):
                logging.debug("end pattern not found, trying again")
                start_addr = position + 1
                position = None
            else:
                break 

        return position
        

    def replace_memory_data(self, replace_dict):
        
        # The modified data
        new_data = bytearray()
        addr = self.first_block_addr()

        # Copy header
        new_data.extend(self.as_bytes()[0:addr])

        finished = False

        while not finished:
            header = self.as_bytes()[addr:addr + 8]
            if (header[0] & 0x80) != 0:
                finished = True

            mem_type = MEMTYPE[header[1] & 0x03]

            base_address = int.from_bytes(
                header[2:4], byteorder='big', signed=False)
            data_length = int.from_bytes(
                header[4:6], byteorder='big', signed=False)

            start_address = self.dsp.START_ADDRESS[mem_type] + base_address
            # The physical address range of this block
            end_address = start_address + data_length

            logging.debug("Parsing EEPROM {} {}/{} (phys: {}-{})",
                          mem_type, base_address,
                          data_length, start_address, end_address)

            addr = addr + 8
            data = self.as_bytes()[addr:addr + 4 * data_length]

            # Replace data
            replace_in_memory_block(data,
                                    start_address,
                                    replace_dict)

            new_data.extend(header)
            new_data.extend(data)

            addr = addr + 4 * data_length

        length = addr

        checksum = int.from_bytes(
            self.as_bytes()[length:length + 8], byteorder='big', signed=False)
        cs_calc = self.calc_checksum(self.as_bytes()[0:addr])

        cs_new = self.calc_checksum(new_data)

        if (checksum != 0) and (checksum != cs_calc):
            logging.error("Checksum of EEPROM content is incorrect, aborting")
            return

        addr += 8

        # Append checksum
        new_data.extend(cs_new.to_bytes(8, byteorder='big'))

        # Padding with zeros
        new_data.extend(bytearray(len(self.as_bytes()) - addr))

        return new_data


def demo():
    x = XmlProfile("sample_files/xml/fullrange-iir.xml")
    x.write_xml("/tmp/x.xml")
    x.replace_eeprom_cells({16: [0xff, 0xff, 0xff, 0xff]})
    x.replace_ram_cells({16: [0xff, 0xff, 0xff, 0xff]})
    x.write_xml("/tmp/y.xml")
