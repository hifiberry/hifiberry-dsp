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

from hifiberrydsp.hardware.adau145x import Adau145x

ATTRIBUTE_CHECKSUM = "checksum"
ATTRIBUTE_VOL_CTL = "volumeControlRegister"
ATTRIBUTE_VOL_LIMIT = "volumeLimitRegister"
ATTRIBUTE_BALANCE = "balanceRegister"
ATTRIBUTE_VOL_RANGE = "volumeControlRangeDb"
ATTRIBUTE_IIR_FILTER_LEFT = "IIRLeft"
ATTRIBUTE_IIR_FILTER_RIGHT = "IIRRight"
ATTRIBUTE_FIR_FILTER_LEFT = "FIRLeft"
ATTRIBUTE_FIR_FILTER_RIGHT = "FIRRight"
ATTRIBUTE_IIR_XOVER = "IIR%LR%%CHANNEL%"
ATTRIBUTE_MUTE_REG = "muteRegister"
ATTRIBUTE_SAMPLERATE = "samplerate"

MEMTYPE = {
    0: "DM0",
    1: "DM1",
    2: "PM",
}


def replace_in_memory_block(data, startaddr, replace_dict):
    assert len(data) % 4 == 0

    endaddr = startaddr + len(data) / 4

    for repl_addr in replace_dict.keys():
        if repl_addr >= startaddr and repl_addr <= endaddr:
            content = replace_dict[repl_addr]

            assert len(content) == 4

            address_offset = (repl_addr - startaddr) * 4
            logging.debug(
                "Replacing memory at address {} by {}", repl_addr, content)

            data[address_offset:address_offset +
                 len(content)] = content


class XmlProfile():

    def __init__(self, filename=None):
        self.dsp = Adau145x()
        self.doc = None
        self.filename = filename
        self.eeprom = DummyEepromWriter(self.dsp)
        if filename is not None:
            self.read_from_file(filename)

    def read_from_file(self, filename):
        logging.debug("reading profile %s", filename)
        try:
            with open(filename) as fd:
                self.doc = xmltodict.parse(fd.read())
        except IOError:
            logging.error("can't read file %s", filename)

        page_address = None

        for action in self.doc["ROM"]["page"]["action"]:
            instr = action["@instr"]

            if instr == "writeXbytes":
                addr = int(action["@addr"])
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
                        print("Found memory block ", saddr)
                        replace_in_memory_block(data, addr, replace_dict)
                        new_data_str = ''.join(
                            '%02X ' % octet for octet in data).strip()
                        action["#text"] = new_data_str

    def write_xml(self, filename):
        outfile = open(filename, "w")
        outfile.write(xmltodict.unparse(self.doc, pretty=True))


class DummyEepromWriter():

    def __init__(self, dsp):
        self.memory = dict()
        self.end_addr = 0
        self.bytes = None
        self.dsp = dsp

    def write_eeprom(self, addr, values):
        for v in values:
            self.memory[addr] = v
            addr += 1

        if addr > self.end_addr:
            self.end_addr = addr

        self.byte = None

    def as_bytes(self):
        if self.bytes is not None:
            return self.bytes

        res = bytearray()
        for i in range(0, self.end_addr):
            res.append(self.memory[i])
        self.bytes = res
        return res

    def get_header(self):
        return self.as_bytes()[0:16]

    def first_block_addr(self):
        return int.from_bytes(self.get_header()[1:4],
                              byteorder='big',
                              signed=False)

    def calc_checksum(self, eeprom_content):
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
                          mem_type, base_address, data_length, start_address, end_address)

            addr = addr + 8
            data = self.as_bytes()[addr:addr + 4 * data_length]

            # Replace data
            replace_in_memory_block(data, start_address, replace_dict)

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

        print(checksum, cs_calc, cs_new)

        # Append checksum
        new_data.extend(cs_new.to_bytes(8, byteorder='big'))

        # Padding with zeros
        new_data.extend(bytearray(len(self.as_bytes()) - addr))

        print(len(self.as_bytes()), len(new_data))

        return new_data


# x = XmlProfile(
#     "/Users/matuschd/devel/python/hifiberry-dsp/sample_files/xml/fullrange-iir.xml")
#
# x.write_xml("/tmp/x.xml")
# x.replace_eeprom_cells({16: [0xff, 0xff, 0xff, 0xff]})
# x.replace_ram_cells({16: [0xff, 0xff, 0xff, 0xff]})
# x.write_xml("/tmp/y.xml")
