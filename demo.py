'''
Created on 22.06.2018

@author: matuschd
'''

import filtering.biquad as biquad
import hardware.adau145x as adau


def main():
    fs = 48000
    biquads = [
        biquad.high_pass(100, 0.5, fs),
        biquad.low_pass(5000, 0.5, fs),
        biquad.notch(800, 2, fs),
        biquad.peaking_eq(2000, 2, 3, fs)
    ]

    reg = 0x1D
    for bq in biquads:
        adau.write_biquad_to_dsp(bq, reg)
        reg += 5


if __name__ == '__main__':
    main()
