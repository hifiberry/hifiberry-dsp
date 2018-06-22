#!/usr/bin/env python
#
# Hardware routines for the ADAU1701
# addressing is always done in 16bit

EXEC_PRINT = "print"
EXEC_DEFAULT = EXEC_PRINT

import math

# ADAU1701 address range
LSB_SIGMA = float(1) / math.pow(2, 23)


def float_to_32bit_fixed(f):
    '''
    converts a float to an 28bit fixed point value used in SigmaDSP processors
    '''
    if (f > 256 - LSB_SIGMA) or (f < -256):
        raise Exception("value {} not in range [-16,16]".format(f))

    # dual complement
    if (f < 0):
        f = 512 + f

    # multiply by 2^24, then convert to integer
    f = f * (1 << 24)
    return int(f)


def dsp32bit_fixed_to_float(p):
    '''
    converts an 28bit fixed point value used in SigmaDSP processors to a float value
    '''
    f = float(p) / pow(2, 24)
    if f >= 16:
        f = -32 + f
    return f


def hex_repr(val):
    res = []
    for i in range(3, -1, -1):
        octet = val >> (i * 8) & 0xff
        res.append("0x{:02X}".format(octet))
    return res


def write_register(reg, length, values, connection=None):
    if connection is None:
        h = hex_repr(values)
        print("beocreate-client 127.0.0.1 write_reg {} {} {}".format(reg,
                                                                     length, ' '.join(h)))
    else:
        print("Not yet implemented")


def write_register_decimal(reg, value, connection=None):
    fixed = float_to_32bit_fixed(value)
    write_register(reg, 4, fixed, connection)


def write_biquad_to_dsp(bq_params, start_reg, connection=None):
    if (len(bq_params)) != 5:
        raise RuntimeError("BiquadFilter needs a parameters (a1,a2,b0,b1,b2)")

    # a1 and a2 needs to be multiplied by -1 as the DSP only used addition
    # internally
    bq_params[0] = -bq_params[0]
    bq_params[1] = -bq_params[1]

    reg = start_reg + 4
    for param in bq_params:
        write_register_decimal(reg, param, connection)
        reg = reg - 1


#
# Demo code
#


def demo():
    print("0       {:07x}".format(float_to_32bit_fixed(0)))
    print("16-1LSB {:07x}".format(float_to_32bit_fixed(16 - LSB_SIGMA)))
    print("8       {:07x}".format(float_to_32bit_fixed(8)))
    print("-16     {:07x}".format(float_to_32bit_fixed(-16)))
    print("0.25    {:07x}".format(float_to_32bit_fixed(0.25)))
    print("-0.25   {:07x}".format(float_to_32bit_fixed(-0.25)))

    # Sample BQ filter
    i = 0x21
    filter = [-1.9, 0.9, 0.9, -1.9, 0.9]
    for f in filter:
        p = float_to_32bit_fixed(f)
        h = hex_repr(p)
        print("beocreate-client 127.0.0.1 write_reg {} 4 {} # ({}/{})".format(i, ' '.join(h), p, f))
        i -= 1


if __name__ == "__main__":
    demo()
