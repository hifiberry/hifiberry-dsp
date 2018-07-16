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

    RESET_REGISTER = 0xf890
    HIBERNATE_REGISTER = 0xf400

    STARTCORE_REGISTER = 0xf402
    KILLCORE_REGISTER = 0xf403

    PROGRAM_END_SIGNATURE = b'\x02\xC2\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

    START_ADDRESS = {
        "DM0": 0x0000,
        "DM1": 0x6000,
        "PM": 0xc000,
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
            f = 512 + f

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

        if f >= 16:
            f = -32 + f
        return f

    def program_end_signature(self):
        return
