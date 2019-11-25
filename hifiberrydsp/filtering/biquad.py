'''
Copyright (c) 2019 Modul 9/HiFiBerry
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
Formulas from "Cookbook formulae for audio EQ biquad filter coefficients"
by Robert Bristow-Johnson  <rbj@audioimagination.com>
'''

import math
import logging

from hifiberrydsp.datatools import parse_decibel, parse_frequency

# def parse_frequency(f_str):
#     if f_str.endswith("hz"):
#         f_str = f_str[0:-2]
#     return float(f_str)
#
#
# def parse_decibel(dbstr):
#     dbstr = dbstr.strip()
#     if dbstr.endswith("db"):
#         dbstr = dbstr[0:-2]
#     return float(dbstr)


class Biquad():

    def __init__(self, a0, a1, a2, b0, b1, b2, description,
                 filtertype=None, f0=None, q=None, db=None):
        self.a0 = a0
        self.a1 = a1
        self.a2 = a2
        self.b0 = b0
        self.b1 = b1
        self.b2 = b2
        self.description = description

        self.filtertype = filtertype
        self.f0 = f0
        self.q = q
        self.db = db

    def normalized(self):
        return Biquad(1,
                      self.a1 / self.a0,
                      self.a2 / self.a0,
                      self.b0 / self.a0,
                      self.b1 / self.a0,
                      self.b2 / self.a0,
                      self.description,
                      self.filtertype,
                      self.f0,
                      self.q,
                      self.db)

    def coefficients_a(self, a0=False):
        if a0:
            return [self.a0, self.a1, self.a2]
        else:
            return [self.a1, self.a2]

    def coefficients_b(self):
        return [self.b0, self.b1, self.b2]

    def coefficients_b_a(self, a0=False):
        if a0:
            return [self.b0, self.b1, self.b2, self.a0, self.a1, self.a2]
        else:
            return [self.b0, self.b1, self.b2, self.a1, self.a2]

    def __str__(self):
        return ("Biquad {} ({},{},{},{},{},{})".format(self.description,
                                                       self.a0, self.a1,
                                                       self.a2, self.b0,
                                                       self.b1, self.b2))

    @classmethod
    def low_pass(cls, f0, q, fs):
        w0 = Biquad.omega(f0, fs)
        alpha = Biquad.alpha(w0, q)
        b0 = (1 - math.cos(w0)) / 2
        b1 = 1 - math.cos(w0)
        b2 = (1 - math.cos(w0)) / 2
        a0 = 1 + alpha
        a1 = -2 * math.cos(w0)
        a2 = 1 - alpha
        return Biquad(a0, a1, a2, b0, b1, b2,
                      "Low pass {}Hz".format(f0),
                      "lp", f0, q)

    @classmethod
    def high_pass(cls, f0, q, fs):
        w0 = Biquad.omega(f0, fs)
        alpha = Biquad.alpha(w0, q)
        b0 = (1 + math.cos(w0)) / 2
        b1 = -(1 + math.cos(w0))
        b2 = (1 + math.cos(w0)) / 2
        a0 = 1 + alpha
        a1 = -2 * math.cos(w0)
        a2 = 1 - alpha
        return Biquad(a0, a1, a2, b0, b1, b2,
                      "High pass {}Hz".format(f0),
                      "hp", f0, q)

    @classmethod
    def band_pass_peak_q(cls, f0, q, fs):
        w0 = Biquad.omega(f0, fs)
        alpha = Biquad.alpha(w0, q)
        b0 = math.sin(w0) / 2
        b1 = 0
        b2 = -math.sin(w0) / 2
        a0 = 1 + alpha
        a1 = -2 * math.cos(w0)
        a2 = 1 - alpha
        return Biquad(a0, a1, a2, b0, b1, b2,
                      "Band pass peak {}Hz".format(f0),
                      "bandpasspeak", f0, q)

    @classmethod
    def band_pass(cls, f0, q, fs):
        w0 = Biquad.omega(f0, fs)
        alpha = Biquad.alpha(w0, q)
        b0 = alpha
        b1 = 0
        b2 = -alpha
        a0 = 1 + alpha
        a1 = -2 * math.cos(w0)
        a2 = 1 - alpha
        return Biquad(a0, a1, a2, b0, b1, b2,
                      "Band pass {}Hz".format(f0),
                      "bp", f0, q)

    @classmethod
    def notch(cls, f0, q, fs):
        w0 = Biquad.omega(f0, fs)
        alpha = Biquad.alpha(w0, q)
        b0 = 1
        b1 = -2 * math.cos(w0)
        b2 = 1
        a0 = 1 + alpha
        a1 = -2 * math.cos(w0)
        a2 = 1 - alpha
        return Biquad(a0, a1, a2, b0, b1, b2,
                      "Notch pass {}Hz".format(f0),
                      "notch", f0, q)

    @classmethod
    def all_pass(cls, f0, q, fs):
        w0 = Biquad.omega(f0, fs)
        alpha = Biquad.alpha(w0, q)
        b0 = 1 - alpha
        b1 = -2 * math.cos(w0)
        b2 = 1 + alpha
        a0 = 1 + alpha
        a1 = -2 * math.cos(w0)
        a2 = 1 - alpha
        return Biquad(a0, a1, a2, b0, b1, b2,
                      "All pass {}Hz".format(f0),
                      "allpass", f0, q)

    @classmethod
    def peaking_eq(self, f0, q, dbgain, fs):
        w0 = Biquad.omega(f0, fs)
        alpha = Biquad.alpha(w0, q)
        a = Biquad.a(dbgain)
        b0 = 1 + alpha * a
        b1 = -2 * math.cos(w0)
        b2 = 1 - alpha * a
        a0 = 1 + alpha / a
        a1 = -2 * math.cos(w0)
        a2 = 1 - alpha / a
        return Biquad(a0, a1, a2, b0, b1, b2,
                      "Peaking Eq {}Hz {}dB".format(f0, dbgain),
                      "eq", f0, q, dbgain)

    @classmethod
    def low_shelf(self, f0, q, dbgain, fs):
        w0 = Biquad.omega(f0, fs)
        alpha = Biquad.alpha(w0, q)
        a = Biquad.a(dbgain)
        b0 = a * ((a + 1) - (a - 1) * math.cos(w0) + 2 * math.sqrt(a) * alpha)
        b1 = 2 * a * ((a - 1) - (a + 1) * math.cos(w0))
        b2 = a * ((a + 1) - (a - 1) * math.cos(w0) - 2 * math.sqrt(a) * alpha)
        a0 = (a + 1) + (a - 1) * math.cos(w0) + 2 * math.sqrt(a) * alpha
        a1 = -2 * ((a - 1) + (a + 1) * math.cos(w0))
        a2 = (a + 1) + (a - 1) * math.cos(w0) - 2 * math.sqrt(a) * alpha
        return Biquad(a0, a1, a2, b0, b1, b2,
                      "Low shelf {}Hz {}dB".format(f0, dbgain),
                      "ls", f0, q, dbgain)

    @classmethod
    def high_shelf(cls, f0, q, dbgain, fs):
        w0 = Biquad.omega(f0, fs)
        alpha = Biquad.alpha(w0, q)
        a = Biquad.a(dbgain)
        b0 = a * ((a + 1) + (a - 1) * math.cos(w0) + 2 * math.sqrt(a) * alpha)
        b1 = -2 * a * ((a - 1) + (a + 1) * math.cos(w0))
        b2 = a * ((a + 1) + (a - 1) * math.cos(w0) - 2 * math.sqrt(a) * alpha)
        a0 = (a + 1) - (a - 1) * math.cos(w0) + 2 * math.sqrt(a) * alpha
        a1 = 2 * ((a - 1) - (a + 1) * math.cos(w0))
        a2 = (a + 1) - (a - 1) * math.cos(w0) - 2 * math.sqrt(a) * alpha
        return Biquad(a0, a1, a2, b0, b1, b2,
                      "High shelf {}Hz {}dB".format(f0, dbgain),
                      "hs", f0, q, dbgain)

    @classmethod
    def plain(self):
        return Biquad(1, 0, 0, 1, 0, 0, "Null filter", "null")

    '''
    from A pratical guide for digital audio IIR filters
    http://freeverb3.sourceforge.net/iir_filter.shtml
    '''

    @classmethod
    def low_pass_firstorder(cls, f0, q, fs):
        w = math.tan(math.pi * f0 / fs)
        n = 1 / (1 + w)
        b0 = w * n
        b1 = b0
        a1 = n * (w - 1)
        return Biquad(1, a1, 0, b0, b1, 0,
                      "Low pass 1st {}Hz".format(f0),
                      "lowpass1st", f0, q)

    @classmethod
    def high_pass_firstorder(cls, f0, q, fs):
        w = math.tan(math.pi * f0 / fs)
        n = 1 / (1 + w)
        b0 = n
        b1 = -b0
        a1 = n * (w - 1)
        return Biquad(1, a1, 0, b0, b1, 0,
                      "High pass 1st {}Hz".format(f0),
                      "highpass1st", f0, q)

    @classmethod
    def volume(cls, db):
        b0 = pow(10, db / 20)
        return Biquad(1, 0, 0, b0, 0, 0,
                      "Volume change {}db".format(db),
                      "volumechange", None, None, db)

    @classmethod
    def mute(cls):
        return Biquad(1, 0, 0, 0, 0, 0, "Null", "mute")

    @classmethod
    def pass_filter(cls):
        return Biquad.volume(0)

    @staticmethod
    def omega(f0, fs):
        return math.pi * f0 / fs * 2

    @staticmethod
    def alpha(omega, q):
        return math.sin(omega) / (2 * q)

    @staticmethod
    def a(dbgain):
        return pow(10, dbgain / 40)

    @classmethod
    def create_filter(cls, definition, fs):
        '''
        creates a filter from a textual representation
        '''
        definition = definition.lower().strip()
        if definition.startswith("lp:"):
            try:
                (_lp, f, q) = definition.split(":")
                q = float(q)
            except:
                (_lp, f) = definition.split(":")
                q = 0.707
            f = parse_frequency(f)
            return Biquad.low_pass(f, q, fs)
        elif definition.startswith("hp:"):
            try:
                (_hp, f, q) = definition.split(":")
                q = float(q)
            except:
                (_hp, f) = definition.split(":")
                q = 0.707
            f = parse_frequency(f)
            return Biquad.high_pass(f, q, fs)
        elif definition.startswith("ls:"):
            try:
                (_ls, f, dbgain, q) = definition.split(":")
            except:
                (_ls, f, dbgain) = definition.split(":")
                q = 0.707
            f = parse_frequency(f)
            dbgain = parse_decibel(dbgain)
            return Biquad.low_shelf(f, q, dbgain, fs)
        elif definition.startswith("hs:"):
            try:
                (_ls, f, dbgain, q) = definition.split(":")
            except:
                (_ls, f, dbgain) = definition.split(":")
                q = 0.707
            f = parse_frequency(f)
            dbgain = parse_decibel(dbgain)
            return Biquad.high_shelf(f, q, dbgain, fs)
        elif definition.startswith("eq:"):
            try:
                (_eq, f, q, dbgain) = definition.split(":")
                q = float(q)
                f = parse_frequency(f)
                dbgain = parse_decibel(dbgain)
                return Biquad.peaking_eq(f, q, dbgain, fs)
            except:
                logging.error("can't parse ea filter")
                return None
        elif definition.startswith("vol:"):
            try:
                (_vol, db) = definition.split(":")
                db = parse_decibel(db)
                return Biquad.volume(db)
            except:
                logging.error("can't parse vol filter")
                return None
        elif definition.startswith("coeff:"):
            try:
                coeffs = definition.split(":")
                coeffs = coeffs[1:]
                numc = []
                for c in coeffs:
                    numc.append(float(c))

                if len(numc) == 5:
                    return Biquad(1, numc[0], numc[1], numc[2],
                                  numc[3], numc[4],
                                  "biquad from coefficients")
                elif len(numc) == 6:
                    return Biquad(numc[0], numc[1], numc[2], numc[3],
                                  numc[4], numc[5],
                                  "biquad from coefficients")

                else:
                    logging.error("5 or 6 biquad coefficients expected")
            except Exception as e:
                logging.error("can't parse biquad filter (%s)", e)
                return None
        elif definition.startswith("pass"):
            return Biquad.pass_filter()
        elif definition == "mute" or definition == "null":
            return Biquad.mute()
        else:
            logging.error("can't parse %s filter", definition)
            return None


if __name__ == "__main__":
    bq1 = Biquad.low_pass(200, 1.41, 48000)
    print("Lowpass 200Hz: ", bq1)

    bq2 = Biquad.low_pass_firstorder(200, 1, 48000)
    print("Lowpass 200Hz: ", bq2)

    bq3 = Biquad.peaking_eq(1000, 2, -1, 48000)
    print("Peaking EQ 1000Hz, Q2, -1dB ", bq3)
