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

import math
import logging
import time
import hashlib

from hifiberrydsp.hardware.spi import SpiHandler

# ADAU1701 address range
LSB_SIGMA = float(1) / math.pow(2, 23)


class Adau145x():

    DECIMAL_LEN = 4
    GPIO_LEN = 2

    WORD_LENGTH = 4
    REGISTER_WORD_LENGTH = 2

    PROGRAM_ADDR = 0xc000
    PROGRAM_LENGTH = 0x2000

    DATA_ADDR = 0x0000
    DATA_LENGTH = 0xb000

    MIN_REGISTER = 0xf000
    MAX_REGISTER = 0xffff

    MIN_MEMORY = 0x0000
    MAX_MEMORY = 0xdfff

    RESET_REGISTER = 0xf890
    HIBERNATE_REGISTER = 0xf400

    STARTCORE_REGISTER = 0xf402
    KILLCORE_REGISTER = 0xf403

    PROGRAM_END_SIGNATURE = b'\x02\xC2\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

    START_ADDRESS = {
        "DM0": 0x0000,
        "DM1": 0x6000,
        "PM": 0xc000,
        "REG": 0xf000,
    }
    
    # Cache for program checksum
    _checksum_cache = None

    @staticmethod
    def decimal_repr(f):
        '''
        converts a float to an 32bit fixed point value used in 
        ADAU154x SigmaDSP processors
        '''
        if (f > 256 - LSB_SIGMA) or (f < -256):
            raise Exception("value {} not in range [-16,16]".format(f))

        # dual complement
        if (f < 0):
            f = 256 + f

        # multiply by 2^24, then convert to integer
        f = f * (1 << 24)
        return int(f)

    @staticmethod
    def decimal_val(p):
        '''
        converts an 32bit fixed point value used in SigmaDSP 
        processors to a float value
        '''
        if isinstance(p, bytearray):
            val = 0
            for octet in p:
                val *= 256
                val += octet

            p = val
            
        f = float(p) / pow(2, 24)

        if f >= 128:
            f = -256 + f
        return f

    @staticmethod
    def cell_len(addr):
        '''
        Return the length of a memory cell. For program and data RAM is is 4 byte, but registers
        are only 2 byte long
        '''
        if addr < 0xf000:
            return 4
        else:
            return 2

    @staticmethod
    def is_valid_memory_address(addr):
        '''
        Check if an address is a valid memory address
        
        Args:
            addr: Address to check
            
        Returns:
            bool: True if the address is a valid memory address
        '''
        return Adau145x.MIN_MEMORY <= addr <= Adau145x.MAX_MEMORY

    @staticmethod
    def is_valid_register_address(addr):
        '''
        Check if an address is a valid register address
        
        Args:
            addr: Address to check
            
        Returns:
            bool: True if the address is a valid register address
        '''
        return Adau145x.MIN_REGISTER <= addr <= Adau145x.MAX_REGISTER
    
    @staticmethod
    def int_data(value, length):
        '''
        Convert an integer to a byte array for the DSP
        
        Args:
            value: Integer value to convert
            length: Number of bytes
            
        Returns:
            list: Byte array representing the integer
        '''
        octets = bytearray()
        for i in range(length, 0, -1):
            octets.append((value >> (i - 1) * 8) & 0xff)

        return octets
        
    @staticmethod
    def detect_dsp():
        '''
        Detect if a DSP is connected and responding
        
        Returns:
            bool: True if DSP detected, False otherwise
        '''
        spi = SpiHandler()
        spi.write(0xf890, [0])
        time.sleep(1)
        spi.write(0xf890, [1])
        time.sleep(1)
        reg1 = int.from_bytes(spi.read(0xf000, 2), byteorder='big') # PLL feedback divider must be != 0
        reg2 = int.from_bytes(spi.read(0xf890, 2), byteorder='big') # Soft reset is expected to be 1 
        if (reg1!=0) and (reg2==1):
            return True
        else:
            return False
    
    @staticmethod
    def kill_dsp():
        '''
        Kill the DSP core (stop processing)
        '''
        logging.debug("killing DSP core")
        spi = SpiHandler()
        
        spi.write(Adau145x.HIBERNATE_REGISTER, 
                  Adau145x.int_data(1, Adau145x.REGISTER_WORD_LENGTH))
        time.sleep(0.0001)
        spi.write(Adau145x.KILLCORE_REGISTER, 
                  Adau145x.int_data(0, Adau145x.REGISTER_WORD_LENGTH))
        time.sleep(0.0001)
        spi.write(Adau145x.KILLCORE_REGISTER, 
                  Adau145x.int_data(1, Adau145x.REGISTER_WORD_LENGTH))

    @staticmethod
    def start_dsp():
        '''
        Start the DSP core (begin processing)
        '''
        logging.debug("starting DSP core")
        spi = SpiHandler()

        spi.write(Adau145x.KILLCORE_REGISTER, 
                  Adau145x.int_data(0, Adau145x.REGISTER_WORD_LENGTH))
        time.sleep(0.0001)
        spi.write(Adau145x.STARTCORE_REGISTER, 
                  Adau145x.int_data(0, Adau145x.REGISTER_WORD_LENGTH))
        time.sleep(0.0001)
        spi.write(Adau145x.STARTCORE_REGISTER, 
                  Adau145x.int_data(1, Adau145x.REGISTER_WORD_LENGTH))
        time.sleep(0.0001)
        spi.write(Adau145x.HIBERNATE_REGISTER, 
                  Adau145x.int_data(0, Adau145x.REGISTER_WORD_LENGTH))
    
    @staticmethod
    def read_memory(addr, length):
        '''
        Read memory from the DSP
        
        Args:
            addr: Start address
            length: Number of bytes to read
            
        Returns:
            bytearray: Memory data
        '''
        spi = SpiHandler()
        return spi.read(addr, length)
        
    @staticmethod
    def write_memory(addr, data):
        '''
        Write memory to the DSP
        
        Args:
            addr: Start address
            data: Data bytes to write
            
        Returns:
            int: Result code (0 = success)
        '''
        spi = SpiHandler()
        return spi.write(addr, data)
    
    @staticmethod
    def get_memory_block(addr, length):
        '''
        Read a block of memory from the DSP
        
        Args:
            addr: Start address
            length: Length in words
            
        Returns:
            bytearray: Memory content
        '''
        block_size = 2048
        spi = SpiHandler()

        logging.debug("reading %s bytes from memory", 
                      length * Adau145x.WORD_LENGTH)

        # Must kill the core to read program memory, but it doesn't
        # hurt doing it also for other memory types
        Adau145x.kill_dsp()

        memory = bytearray()

        while len(memory) < length * Adau145x.WORD_LENGTH:
            logging.debug("reading memory code block from addr %s", addr)
            data = spi.read(addr, block_size)
            memory += data
            addr = addr + int(block_size / Adau145x.WORD_LENGTH)

        # Restart the core
        Adau145x.start_dsp()

        return memory[0:length * Adau145x.WORD_LENGTH]
    
    @staticmethod
    def get_program_memory():
        '''
        Read the program memory from the DSP including program end detection
        
        Returns:
            bytearray: Program memory content up to the end marker
        '''
        Adau145x.kill_dsp()
        time.sleep(0.0001)
        memory = Adau145x.get_memory_block(Adau145x.PROGRAM_ADDR,
                                          Adau145x.PROGRAM_LENGTH)
        Adau145x.start_dsp()
        logging.debug("Read program from address %s to %s", Adau145x.PROGRAM_ADDR, Adau145x.PROGRAM_ADDR + Adau145x.PROGRAM_LENGTH)

        end_index = memory.find(Adau145x.PROGRAM_END_SIGNATURE)
        logging.debug("Program end signature found at %s", end_index)

        if end_index < 0:
            memsum = 0
            for i in memory:
                memsum = memsum + i

            if (memsum > 0):
                logging.error("couldn't find program end signature," +
                              " using full program memory")
                end_index = Adau145x.PROGRAM_LENGTH - Adau145x.WORD_LENGTH
            else:
                logging.error("SPI returned only zeros - communication "
                              "error")
                return None
        else:
            end_index = end_index + len(Adau145x.PROGRAM_END_SIGNATURE)

        logging.debug("Program lengths = %s words",
                      end_index / Adau145x.WORD_LENGTH)

        return memory[0:end_index]
    
    @staticmethod
    def get_data_memory():
        '''
        Read the data memory from the DSP
        
        Returns:
            bytearray: Data memory content
        '''
        memory = Adau145x.get_memory_block(Adau145x.DATA_ADDR,
                                          Adau145x.DATA_LENGTH)
        logging.debug("Data lengths = %s words",
                      Adau145x.DATA_LENGTH / Adau145x.WORD_LENGTH)

        return memory[0:Adau145x.DATA_LENGTH]
        
    @staticmethod
    def calculate_program_checksum(program_data=None, cached=True):
        '''
        Calculate MD5 checksum of program memory
        
        Args:
            program_data: Optional program data. If None, reads from DSP
            cached: Whether to use cached checksum if available
            
        Returns:
            bytes: MD5 digest
        '''
        if cached and Adau145x._checksum_cache is not None:
            logging.debug("using cached program checksum")
            return Adau145x._checksum_cache

        if program_data is None:
            program_data = Adau145x.get_program_memory()
            
        if program_data is None:
            return None
            
        m = hashlib.md5()
        try:
            m.update(program_data)
        except:
            logging.error("Can't calculate checksum")
            return None

        logging.debug("length: %s, digest: %s", len(program_data), m.digest())
        
        # Cache the result
        Adau145x._checksum_cache = m.digest()
        
        return m.digest()
    
    @staticmethod
    def clear_checksum_cache():
        '''Clear the cached program checksum'''
        Adau145x._checksum_cache = None
        
    @staticmethod
    def write_biquad(start_addr, bq):
        '''
        Write biquad filter coefficients to DSP memory.
        
        Args:
            start_addr: Starting address for the biquad coefficients
            bq: Biquad filter object with a1, a2, b0, b1, b2 coefficients
        '''
        # Normalize the biquad coefficients
        bqn = bq.normalized()
        
        # Create array of parameters in the order they should be written
        bq_params = []
        bq_params.append(-bqn.a1)  # Negative a1
        bq_params.append(-bqn.a2)  # Negative a2
        bq_params.append(bqn.b0)   # b0
        bq_params.append(bqn.b1)   # b1
        bq_params.append(bqn.b2)   # b2
        
        # Write params to registers starting from highest address
        reg = start_addr + 4
        for param in bq_params:
            data = Adau145x.int_data(Adau145x.decimal_repr(param), Adau145x.DECIMAL_LEN)
            Adau145x.write_memory(reg, data)
            reg = reg - 1
        
        logging.debug(f"Wrote biquad to address {start_addr}: a1={-bqn.a1}, a2={-bqn.a2}, b0={bqn.b0}, b1={bqn.b1}, b2={bqn.b2}")
    
    @staticmethod
    def write_biquad_direct(start_addr, a0, a1, a2, b0, b1, b2):
        '''
        Write biquad filter coefficients directly to DSP memory without normalization.
        
        Args:
            start_addr: Starting address for the biquad coefficients
            a0: Denominator coefficient 0 (typically 1.0)
            a1: Denominator coefficient 1
            a2: Denominator coefficient 2
            b0: Numerator coefficient 0
            b1: Numerator coefficient 1
            b2: Numerator coefficient 2
        '''
        from hifiberrydsp.filtering.biquad import Biquad
        
        # Create a Biquad object with the provided coefficients
        # We use the constructor that accepts a0, a1, a2, b0, b1, b2
        bq = Biquad.from_parameters(a0, a1, a2, b0, b1, b2)
        
        # Use the existing write_biquad method
        Adau145x.write_biquad(start_addr, bq)
    
    @staticmethod
    def guess_samplerate():
        '''
        Guess the DSP sample rate by checking the clock generator registers.
        
        Returns:
            int or None: Sample rate in Hz (48000, 96000, 192000) or None if detection fails
        '''
        try:
            # read START_PULSE (0xf401) to find DSP sample rate (assume 294.912MHz core frequency)
            start_pulse = Adau145x.read_memory(0xf401,2)[1]
            logging.debug(f"START_PULSE value: {start_pulse}")
            if start_pulse == 2:
                return 48000
            elif start_pulse == 3:
                return 96000
            elif start_pulse == 4:
                return 192000
            else:
                logging.warning(f"Unexpected START_PULSE value: {start_pulse}, expected 2, 3 or 4")
                return None
                
        except Exception as e:
            logging.warning(f"Error guessing sample rate: {str(e)}")
            return None

    @staticmethod
    def write_eeprom_content(xmldata):
        """
        Write EEPROM content based on XML data.
        
        Args:
            xmldata (str or bytes): XML data containing DSP configuration
            
        Returns:
            bool: True for success, False for failure
        """
        import xmltodict
        import os
        import time
        from hifiberrydsp.parser.xmlprofile import get_default_dspprofile_path
        
        logging.info("Writing EEPROM content from XML")
        dspprogramfile = get_default_dspprofile_path()
        
        try:
            doc = xmltodict.parse(xmldata)

            # Kill DSP and clear checksum cache before updating
            Adau145x.clear_checksum_cache()
            Adau145x.kill_dsp()
            
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
                    Adau145x.write_memory(addr, data)

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

            # Restart the DSP core
            Adau145x.start_dsp()

            # Write current DSP profile to file
            with open(dspprogramfile, "w+b") as dspprogram:
                if isinstance(xmldata, str):
                    xmldata = xmldata.encode("utf-8")
                dspprogram.write(xmldata)

        except Exception as e:
            logging.error("Exception during EEPROM write: %s", e)
            logging.exception(e)
            return False

        return True

