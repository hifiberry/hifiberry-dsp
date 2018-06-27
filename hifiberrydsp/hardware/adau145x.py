#!/usr/bin/env python
#
# Hardware routines for the ADAU1701
# addressing is always done in 16bit

EXEC_PRINT = "print"
EXEC_DEFAULT = EXEC_PRINT

import math

# ADAU1701 address range
LSB_SIGMA = float(1) / math.pow(2, 23)


class Adau145x():

    def __init__(self):
        self.DECIMAL_LEN = 4
        self.GPIO_LEN = 2

    def decimal_repr(self, f):
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

    def decimal_val(self, p):
        '''
        converts an 32bit fixed point value used in SigmaDSP 
        processors to a float value
        '''
        f = float(p) / pow(2, 24)
        if f >= 16:
            f = -32 + f
        return f

    def reset_register(self):
        return (0xf890, 2)

    def hibernate_register(self):
        return (0xf400, 2)

    def startcore_register(self):
        return (0xf402, 2)
