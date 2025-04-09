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
from hifiberrydsp.filtering.biquad import Biquad


class REWParser():

    def __init__(self):
        pass

    @staticmethod
    def readfilters(filename, fs=48000):
        filters = []

        with open(filename) as file:
            for line in file.readlines():
                if line.startswith("Filter"):
                    parts = line.split()
                    if len(parts) >= 12 and parts[2] == "ON" and \
                            parts[3] == "PK" and \
                            parts[4] == "Fc" and parts[6] == "Hz" and \
                            parts[7] == "Gain" and parts[9] == "dB" and \
                            parts[10] == "Q":

                        fc = float(parts[5])
                        gain = float(parts[8])
                        q = float(parts[11])
                        logging.info("Filter EQ fc=%s, q=%s, gain=%s, fs=%s",
                                     fc, q, gain, fs)
                        filters.append(
                            Biquad.peaking_eq(fc, q, gain, fs))
                    elif len(parts) >= 6 and parts[2] == "ON" and \
                            parts[3] == "LP" and \
                            parts[4] == "Fc" and parts[6] == "Hz":

                        fc = float(parts[5])
                        logging.info("Filter LP fc=%s", fc)
                        filters.append(
                            Biquad.low_pass(fc, 0.707, fs))
                    elif len(parts) >= 9 and parts[2] == "ON" and \
                            parts[3] == "LPQ" and \
                            parts[4] == "Fc" and parts[6] == "Hz" and \
                            parts[7] == "Q":
                        fc = float(parts[5])
                        q = float(parts[8])
                        logging.info("Filter LPQ fc=%s, q=%s", fc, q)
                        filters.append(
                            Biquad.low_pass(fc, q, fs))
                    elif len(parts) >= 10 and parts[2] == "ON" and \
                            parts[3] == "LS" and \
                            parts[4] == "Fc" and parts[6] == "Hz" and \
                            parts[7] == "Gain" and parts[9] == "dB":
                        fc = float(parts[5])
                        db = float(parts[8])
                        q = 0.707
                        logging.info("Filter LS fc=%s, db=%s", fc, db)
                        filters.append(
                            Biquad.low_shelf(fc, q, db, fs))
                    elif len(parts) >= 6 and parts[2] == "ON" and \
                            parts[3] == "HP" and \
                            parts[4] == "Fc" and parts[6] == "Hz":

                        fc = float(parts[5])
                        logging.info("Filter HP fc=%s", fc)
                        filters.append(
                            Biquad.high_pass(fc, 0.707, fs))
                    elif len(parts) >= 9 and parts[2] == "ON" and \
                            parts[3] == "HPQ" and \
                            parts[4] == "Fc" and parts[6] == "Hz" and \
                            parts[7] == "Q":
                        fc = float(parts[5])
                        q = float(parts[8])
                        logging.info("Filter HPQ fc=%s, q=%s", fc, q)
                        filters.append(
                            Biquad.high_pass(fc, q, fs))
                    elif len(parts) >= 10 and parts[2] == "ON" and \
                            parts[3] == "HS" and \
                            parts[4] == "Fc" and parts[6] == "Hz" and \
                            parts[7] == "Gain" and parts[9] == "dB":
                        fc = float(parts[5])
                        db = float(parts[8])
                        q = 0.707
                        logging.info("Filter HS fc=%s, db=%s", fc, db)
                        filters.append(
                            Biquad.high_shelf(fc, q, db, fs))
                    elif len(parts) >= 7 and parts[2] == "ON" and \
                            parts[3] == "NO" and \
                            parts[4] == "Fc" and parts[6] == "Hz":
                        fc = float(parts[5])
                        q = 0.707
                        logging.info("Filter NO fc=%s q=%s", fc, q)
                        filters.append(
                            Biquad.notch(fc, q, fs))

                    else:
                        if len(parts) >= 4 and parts[2] != "OFF" and parts[3] != "None":
                            print("Filter type " + parts[3] +
                                  " not yet supported")

            return filters
