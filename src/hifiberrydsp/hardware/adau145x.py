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
    START_PULSE_REGISTER = 0xf401    # Register to read DSP sample rate configuration

    STARTCORE_REGISTER = 0xf402
    KILLCORE_REGISTER = 0xf403

    PROGRAM_END_SIGNATURE = b'\x02\xC2\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

    PROGRAM_LEN_UPPER = 0xf463 
    PROGRAM_LEN_LOWER = 0xf464 

    PROGRAM_MAX_LEN_UPPER = 0xf465
    PROGRAM_MAX_LEN_LOWER = 0xf466 

    # PLL Control Registers
    PLL_CTRL0 = 0xf000          # PLL feedback divider
    PLL_CTRL1 = 0xf001          # PLL prescale divider
    PLL_CLK_SRC = 0xf002        # PLL clock source
    PLL_ENABLE = 0xf003         # PLL enable
    PLL_LOCK = 0xf004           # PLL lock (read-only)
    MCLK_OUT = 0xf005           # CLKOUT control
    PLL_WATCHDOG = 0xf006       # Analog PLL watchdog control

    # Clock Generator Registers
    CLK_GEN1_M = 0xf020         # Denominator (M) for Clock Generator 1
    CLK_GEN1_N = 0xf021         # Numerator (N) for Clock Generator 1
    CLK_GEN2_M = 0xf022         # Denominator (M) for Clock Generator 2
    CLK_GEN2_N = 0xf023         # Numerator (N) for Clock Generator 2
    CLK_GEN3_M = 0xf024         # Denominator (M) for Clock Generator 3
    CLK_GEN3_N = 0xf025         # Numerator (N) for Clock Generator 3
    CLK_GEN3_SRC = 0xf026       # Input Reference for Clock Generator 3 

    START_ADDRESS = {
        "DM0": 0x0000,
        "DM1": 0x6000,
        "PM": 0xc000,
        "REG": 0xf000,
    }

    # SigmaStudio software safeload. The staging window sits at the start of
    # DM1: five data words, the address they belong at, then the number of
    # words. Writing the count asks the core to perform the copy, and the
    # core zeroes the count again once it has, which makes the handshake
    # observable. The copy happens between two audio frames, so a
    # multi-word parameter such as a biquad is never half applied.
    SAFELOAD_DATA_ADDR = 0x6000
    SAFELOAD_TARGET_ADDR = 0x6005
    SAFELOAD_COUNT_ADDR = 0x6006
    SAFELOAD_MAX_WORDS = 5
    SAFELOAD_WINDOW_WORDS = 7
    # A request is consumed within one audio frame (~21us at 48kHz), so
    # 10ms is already some 480 frames of margin. It is kept short because
    # the wait is also how long a probe's words sit in the memory of a
    # program that turns out not to implement safeload.
    SAFELOAD_TIMEOUT = 0.01
    SAFELOAD_POLL_INTERVAL = 0.001

    # None = not probed yet, True/False = what the last probe found
    _safeload_supported = None
    
    # Cache for program checksums - structure: {mode: {algorithm: digest}}
    _checksum_cache = {
        "signature": {"md5": None, "sha1": None},
        "length": {"md5": None, "sha1": None}
    }
    
    # Cache for program memory to avoid multiple reads
    _memory_cache = {
        "signature": None,
        "length": None
    }

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

        # The three writes are one operation: hold the bus so no other
        # thread meets the core half stopped.
        with SpiHandler.lock:
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

        with SpiHandler.lock:
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
        # Debug logging for memory writes if enabled
        # Check if debug mode is enabled in SigmaTCPHandler
        try:
            from hifiberrydsp.server.sigmatcp import SigmaTCPHandler
            if hasattr(SigmaTCPHandler, 'debug_memory_writes') and SigmaTCPHandler.debug_memory_writes:
                length = len(data)
                logging.debug(f"Memory write to address 0x{addr:04X} ({addr}), length: {length} bytes")
                if length <= 32:  # Log full data for small writes
                    hex_data = ' '.join(f"{b:02X}" for b in data)
                    logging.debug(f"Write data: {hex_data}")
                else:  # Log first 16 bytes for large writes
                    hex_data = ' '.join(f"{b:02X}" for b in data[:16])
                    logging.debug(f"Write data (first 16 bytes): {hex_data}...")
        except ImportError:
            # SigmaTCPHandler not available, skip debug logging
            pass
        
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
    def get_program_len(max=False):
        '''
        Read the program length from the DSP registers
        
        Args:
            max (bool): If True, read maximum program length instead of current length
        
        Returns:
            int: Program length in bytes
        '''
        spi = SpiHandler()
        
        if max:
            # Read maximum program length registers
            upper = spi.read(Adau145x.PROGRAM_MAX_LEN_UPPER, 2)
            lower = spi.read(Adau145x.PROGRAM_MAX_LEN_LOWER, 2)
            register_type = "maximum program length"
        else:
            # Read current program length registers
            upper = spi.read(Adau145x.PROGRAM_LEN_UPPER, 2)
            lower = spi.read(Adau145x.PROGRAM_LEN_LOWER, 2)
            register_type = "program length"
            
        if upper is None or lower is None:
            logging.error(f"Failed to read {register_type} registers")
            return None
            
        upper_val = int.from_bytes(upper, byteorder='big')
        lower_val = int.from_bytes(lower, byteorder='big')
        program_length = (upper_val << 16) | lower_val
        logging.debug(f"{register_type.capitalize()} read from DSP: {program_length} bytes")
        return program_length
    
    @staticmethod
    def get_program_memory(end="signature"):
        '''
        Read the program memory from the DSP with different end detection modes
        
        Args:
            end (str): End detection mode:
                - "signature": Find program end signature (default behavior)
                - "full": Dump full program memory space
                - "len": Use program length registers to determine end
        
        Returns:
            bytearray: Program memory content
        '''
        if end not in ["signature", "full", "len"]:
            raise ValueError(f"Invalid end mode '{end}'. Must be 'signature', 'full', or 'len'")
        
        Adau145x.kill_dsp()
        time.sleep(0.0001)
        
        try:
            if end == "full":
                # Dump full program memory space
                memory = Adau145x.get_memory_block(Adau145x.PROGRAM_ADDR,
                                                  Adau145x.PROGRAM_LENGTH)
                logging.debug("Read full program memory from address %s to %s (%s bytes)", 
                             Adau145x.PROGRAM_ADDR, 
                             Adau145x.PROGRAM_ADDR + Adau145x.PROGRAM_LENGTH * Adau145x.WORD_LENGTH,
                             len(memory))
                return memory
                
            elif end == "len":
                # Use program length registers to determine end
                program_len = Adau145x.get_program_len()
                if program_len is None:
                    logging.error("Failed to read program length for memory dump")
                    return None
                    
                # Convert from words to bytes
                program_len_bytes = program_len * Adau145x.WORD_LENGTH
                
                # Read only the used program memory
                memory_length_words = min(program_len, Adau145x.PROGRAM_LENGTH)
                memory = Adau145x.get_memory_block(Adau145x.PROGRAM_ADDR,
                                                  memory_length_words)
                
                logging.debug("Read program memory using length registers: %s words (%s bytes)",
                             program_len, program_len_bytes)
                return memory[0:program_len_bytes]
                
            else:  # end == "signature" (default)
                # Original behavior: find program end signature
                memory = Adau145x.get_memory_block(Adau145x.PROGRAM_ADDR,
                                                  Adau145x.PROGRAM_LENGTH)
                logging.debug("Read program from address %s to %s", 
                             Adau145x.PROGRAM_ADDR, 
                             Adau145x.PROGRAM_ADDR + Adau145x.PROGRAM_LENGTH * Adau145x.WORD_LENGTH)

                end_index = memory.find(Adau145x.PROGRAM_END_SIGNATURE)
                logging.debug("Program end signature found at %s", end_index)

                if end_index < 0:
                    memsum = 0
                    for i in memory:
                        memsum = memsum + i

                    if (memsum > 0):
                        logging.error("couldn't find program end signature," +
                                      " using full program memory")
                        end_index = len(memory) - Adau145x.WORD_LENGTH
                    else:
                        logging.error("SPI returned only zeros - communication "
                                      "error")
                        return None
                else:
                    end_index = end_index + len(Adau145x.PROGRAM_END_SIGNATURE)

                logging.debug("Program lengths = %s words",
                              end_index / Adau145x.WORD_LENGTH)

                return memory[0:end_index]
                
        finally:
            # Always restart the DSP core
            Adau145x.start_dsp()
    
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
    def get_program_memory_subset(mode="signature", cached=True):
        '''
        Get a subset of program memory based on either signature or length detection
        with efficient caching to avoid multiple memory reads
        
        Args:
            mode (str): Detection mode - "signature" or "length"
            cached (bool): Whether to use cached memory if available
            
        Returns:
            bytearray: Program memory subset or None if failed
        '''
        if mode not in ["signature", "length"]:
            raise ValueError(f"Invalid mode '{mode}'. Must be 'signature' or 'length'")
        
        # Check cache first
        if cached and Adau145x._memory_cache[mode] is not None:
            logging.debug(f"Using cached program memory ({mode} mode)")
            return Adau145x._memory_cache[mode]
        
        logging.debug(f"Reading program memory ({mode} mode)")
        
        if mode == "signature":
            # Use signature-based detection
            memory = Adau145x.get_program_memory(end="signature")
        else:  # mode == "length"
            # Use length-based detection
            memory = Adau145x.get_program_memory(end="len")
        
        # Cache the result
        if memory is not None:
            Adau145x._memory_cache[mode] = memory
            logging.debug(f"Cached program memory ({mode} mode): {len(memory)} bytes")
        
        return memory
    
    @staticmethod
    def calculate_program_checksums(mode="signature", algorithms=None, cached=True):
        '''
        Calculate multiple checksums of program memory efficiently
        
        Args:
            mode (str): Detection mode - "signature" or "length"
            algorithms (list): List of algorithms ["md5", "sha1"]. If None, calculates both
            cached (bool): Whether to use cached checksums if available
            
        Returns:
            dict: Dictionary with algorithm names as keys and hex digests as values
        '''
        if mode not in ["signature", "length"]:
            raise ValueError(f"Invalid mode '{mode}'. Must be 'signature' or 'length'")
        
        if algorithms is None:
            algorithms = ["md5", "sha1"]
        
        # Validate algorithms
        valid_algorithms = {"md5", "sha1"}
        for alg in algorithms:
            if alg not in valid_algorithms:
                raise ValueError(f"Invalid algorithm '{alg}'. Must be one of {valid_algorithms}")
        
        result = {}
        
        # Check cache for each requested algorithm
        all_cached = True
        for alg in algorithms:
            if cached and Adau145x._checksum_cache[mode][alg] is not None:
                result[alg] = Adau145x._checksum_cache[mode][alg]
                logging.debug(f"Using cached {alg} checksum ({mode} mode)")
            else:
                all_cached = False
        
        # If all requested checksums are cached, return them
        if all_cached:
            return result
        
        # Get program memory (cached if possible)
        program_data = Adau145x.get_program_memory_subset(mode=mode, cached=cached)
        if program_data is None:
            logging.error(f"Failed to get program memory for checksum calculation ({mode} mode)")
            return {}
        
        # Calculate missing checksums
        import hashlib
        for alg in algorithms:
            if alg not in result:  # Only calculate if not cached
                try:
                    if alg == "md5":
                        hasher = hashlib.md5()
                    elif alg == "sha1":
                        hasher = hashlib.sha1()
                    
                    hasher.update(program_data)
                    digest_hex = hasher.hexdigest().upper()
                    
                    # Cache and store result
                    Adau145x._checksum_cache[mode][alg] = digest_hex
                    result[alg] = digest_hex
                    
                    logging.debug(f"Calculated {alg} checksum ({mode} mode): {digest_hex}")
                    
                except Exception as e:
                    logging.error(f"Failed to calculate {alg} checksum ({mode} mode): {str(e)}")
        
        return result
    
    @staticmethod
    def clear_checksum_cache():
        '''Clear all cached checksums and memory'''
        Adau145x._checksum_cache = {
            "signature": {"md5": None, "sha1": None},
            "length": {"md5": None, "sha1": None}
        }
        Adau145x._memory_cache = {
            "signature": None,
            "length": None
        }
        Adau145x.reset_safeload_detection()
        logging.debug("Cleared all checksum and memory caches")
        
    @staticmethod
    def calculate_program_checksum(program_data=None, cached=True):
        '''
        Calculate MD5 checksum of program memory (backward compatibility method)
        
        Args:
            program_data: Optional program data. If None, reads from DSP using signature mode
            cached: Whether to use cached checksum if available
            
        Returns:
            bytes: MD5 digest
        '''
        if program_data is not None:
            # If program_data is provided, calculate directly (legacy behavior)
            import hashlib
            m = hashlib.md5()
            try:
                m.update(program_data)
                return m.digest()
            except (TypeError, ValueError):
                logging.error("Can't calculate checksum from provided data")
                return None
        else:
            # Use new efficient method for signature-based MD5
            checksums = Adau145x.calculate_program_checksums(mode="signature", algorithms=["md5"], cached=cached)
            if "md5" in checksums:
                # Convert hex string back to bytes for backward compatibility
                try:
                    return bytes.fromhex(checksums["md5"])
                except (ValueError, TypeError):
                    logging.error("Failed to convert hex checksum to bytes")
                    return None
            else:
                return None
    
    @staticmethod
    def write_biquad(start_addr, bq):
        '''
        Write biquad filter coefficients to DSP memory.

        The five words go through safeload where the loaded program supports
        it, so the core swaps the whole filter in between two audio frames
        instead of running a frame on a half-written slot. A program without
        safeload falls back to writing the cells one at a time, highest
        address first, which is what this did before.

        Args:
            start_addr: Starting address for the biquad coefficients
            bq: Biquad filter object with a1, a2, b0, b1, b2 coefficients
        '''
        # Normalize the biquad coefficients
        bqn = bq.normalized()

        # The slot holds, ascending from start_addr: b2, b1, b0, -a2, -a1
        coefficients = [bqn.b2, bqn.b1, bqn.b0, -bqn.a2, -bqn.a1]
        words = [Adau145x.decimal_repr(c) for c in coefficients]

        if not Adau145x._write_biquad_safeload(start_addr, words):
            with SpiHandler.lock:
                for offset in reversed(range(len(words))):
                    Adau145x.write_memory(
                        start_addr + offset,
                        Adau145x.int_data(words[offset], Adau145x.DECIMAL_LEN))

        logging.debug(f"Wrote biquad to address {start_addr}: a1={-bqn.a1}, a2={-bqn.a2}, b0={bqn.b0}, b1={bqn.b1}, b2={bqn.b2}")

    @staticmethod
    def reset_safeload_detection():
        '''
        Forget whether the loaded program answers safeload requests.

        Safeload is an option of the SigmaStudio project, not a property of
        the chip, so the answer can change with the program. Call this
        whenever a different program is loaded.

        Takes the bus lock, because the probe holds it while it reads and
        writes this: a reset landing mid-probe would otherwise be undone by
        the answer for the program that has just been replaced.
        '''
        with SpiHandler.lock:
            Adau145x._safeload_supported = None

    @staticmethod
    def core_is_running():
        '''
        Ask the chip whether the core is running.

        Asking beats remembering: the core is also stopped by a TCP client
        writing these registers directly, and a flag that missed that would
        send a probe against a dead core and file the timeout as the
        program's answer. Both registers read back what was written,
        verified on a Beocreate 4-Channel Amplifier.
        '''
        for register in (Adau145x.HIBERNATE_REGISTER, Adau145x.KILLCORE_REGISTER):
            value = Adau145x.read_memory(register, Adau145x.REGISTER_WORD_LENGTH)
            if int.from_bytes(value, byteorder="big") != 0:
                return False
        return True

    @staticmethod
    def _write_biquad_safeload(addr, words):
        '''
        Try to apply filter coefficients through safeload.

        The first write after a program is loaded doubles as the capability
        probe, and the probe has to prove the transfer rather than trust the
        handshake. On a program without safeload the staging window is
        ordinary data belonging to the running program, and the cell being
        polled may read zero for reasons of its own. So the words are read
        back from the slot before safeload is believed.

        Two answers are refused rather than recorded, because neither says
        anything about the program: one from a slot that already held the
        words, where the readback would succeed either way, and one from a
        core that is or goes down during the probe.

        Returns:
            bool: True if the coefficients reached the slot
        '''
        with SpiHandler.lock:
            if Adau145x._safeload_supported is False:
                return False

            if Adau145x._safeload_supported:
                return Adau145x.safeload_write(addr, words)

            wanted = Adau145x._wire_words(words)

            if not Adau145x.core_is_running():
                return False

            if Adau145x._read_words(addr, len(words)) == wanted:
                # the readback could not tell a transfer from what is
                # already there, so this write cannot settle the question
                return False

            window = Adau145x.read_memory(
                Adau145x.SAFELOAD_DATA_ADDR,
                Adau145x.SAFELOAD_WINDOW_WORDS * Adau145x.WORD_LENGTH)
            applied = False
            try:
                applied = (Adau145x.safeload_write(addr, words)
                           and Adau145x._read_words(addr, len(words)) == wanted)
            finally:
                if not applied:
                    Adau145x.write_memory(Adau145x.SAFELOAD_DATA_ADDR, window)

            if not applied and not Adau145x.core_is_running():
                # the core went down while we were asking
                return False

            Adau145x._safeload_supported = applied
            if applied:
                logging.info("DSP program supports safeload, "
                             "applying filters atomically")
            else:
                logging.info("DSP program does not answer safeload "
                             "requests, writing coefficients directly")
            return applied

    @staticmethod
    def _wire_words(words):
        '''
        The values as they will exist in DSP memory. decimal_repr() can
        return 2**32, which int_data() puts on the wire as four zero bytes,
        so a comparison against the Python value would not match.
        '''
        return [int.from_bytes(Adau145x.int_data(word, Adau145x.WORD_LENGTH),
                               byteorder="big")
                for word in words]

    @staticmethod
    def _read_words(addr, count):
        '''
        Read count consecutive 32-bit cells as integers.
        '''
        data = Adau145x.read_memory(addr, count * Adau145x.WORD_LENGTH)
        return [int.from_bytes(data[i * Adau145x.WORD_LENGTH:
                                    (i + 1) * Adau145x.WORD_LENGTH],
                               byteorder="big")
                for i in range(count)]

    @staticmethod
    def safeload_write(addr, words):
        '''
        Write up to SAFELOAD_MAX_WORDS words to consecutive cells starting at
        addr using SigmaStudio software safeload, so the DSP applies them all
        at a frame boundary.

        The bus is held for the whole handshake: the staging window is a
        single shared resource, and a second request posted before the core
        has consumed the first would replace it.

        Args:
            addr: target address of the first word
            words: 1..SAFELOAD_MAX_WORDS integers in the DSP's own format

        Returns:
            bool: True if the DSP consumed the request, False if it did not
                  answer in time - a program without safeload support, or a
                  stopped core
        '''
        if not 1 <= len(words) <= Adau145x.SAFELOAD_MAX_WORDS:
            raise ValueError(
                "safeload takes 1 to {} words, got {}".format(
                    Adau145x.SAFELOAD_MAX_WORDS, len(words)))

        # int_data() truncates silently, so a value that does not fit a cell
        # would otherwise be posted as four plausible bytes. 2**32 is allowed:
        # decimal_repr() returns it for a coefficient just below zero.
        for word in words:
            if not 0 <= word <= 1 << (Adau145x.WORD_LENGTH * 8):
                raise ValueError(
                    "safeload word {} does not fit a {}-byte cell".format(
                        word, Adau145x.WORD_LENGTH))

        padded = list(words) + [0] * (Adau145x.SAFELOAD_MAX_WORDS - len(words))
        payload = bytearray()
        for word in padded + [addr, len(words)]:
            payload += Adau145x.int_data(word, Adau145x.WORD_LENGTH)

        with SpiHandler.lock:
            Adau145x.write_memory(Adau145x.SAFELOAD_DATA_ADDR, payload)

            # monotonic, not wall clock: these boards have no RTC, and an NTP
            # step backwards during the poll would hold the bus for the size
            # of the step
            deadline = time.monotonic() + Adau145x.SAFELOAD_TIMEOUT
            while True:
                pending = Adau145x.read_memory(Adau145x.SAFELOAD_COUNT_ADDR,
                                               Adau145x.WORD_LENGTH)
                if int.from_bytes(pending, byteorder="big") == 0:
                    return True
                if time.monotonic() >= deadline:
                    logging.debug(
                        "safeload request for address %s was not consumed "
                        "within %ss", addr, Adau145x.SAFELOAD_TIMEOUT)
                    return False
                time.sleep(Adau145x.SAFELOAD_POLL_INTERVAL)
    
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
        bq = Biquad(a0, a1, a2, b0, b1, b2)

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
            # read START_PULSE register to find DSP sample rate (assume 294.912MHz core frequency)
            start_pulse = Adau145x.read_memory(Adau145x.START_PULSE_REGISTER, 2)[1]
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

                    # Delay after Programn, DM0 data, DM1 data, HIBERNATE
                    if ("Programn" in paramname) or ("DM0" in paramname) or ("DM1" in paramname) or ("HIBERNATE" in paramname):
                        logging.debug(
                            "found program write command, waiting 1 seconds to finish")
                        time.sleep(1)

                    # Delay after a page write
                    if ("Page_" in paramname):
                        logging.debug(
                            "found page write command, waiting 1 second to finish")
                        time.sleep(1)

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

