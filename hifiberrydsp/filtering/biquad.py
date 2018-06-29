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

Formulas from "Cookbook formulae for audio EQ biquad filter coefficients"
by Robert Bristow-Johnson  <rbj@audioimagination.com>
'''

import math


class Biquad():

    def __init__(self, a0, a1, a2, b0, b1, b2, description):
        self.a0 = a0
        self.a1 = a1
        self.a2 = a2
        self.b0 = b0
        self.b1 = b1
        self.b2 = b2
        self.description = description

    def normalized(self):
        return Biquad(1,
                      self.a1 / self.a0,
                      self.a2 / self.a0,
                      self.b0 / self.a0,
                      self.b1 / self.a0,
                      self.b2 / self.a0,
                      self.description)

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
                      "Low pass {}Hz".format(f0))

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
                      "High pass {}Hz".format(f0))

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
                      "Band pass peak {}Hz".format(f0))

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
                      "Band pass {}Hz".format(f0))

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
                      "Notch pass {}Hz".format(f0))

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
                      "All pass {}Hz".format(f0))

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
                      "Peaking Eq {}Hz {}dB".format(f0, dbgain))

    @classmethod
    def low_shelf(self, f0, q, dbgain, fs):
        w0 = Biquad.omega(f0, fs)
        alpha = Biquad.alpha(w0, q)
        a = self._a(dbgain)
        b0 = a * ((a + 1) - (a - 1) * math.cos(w0) + 2 * math.sqrt(a) * alpha)
        b1 = 2 * a * ((a - 1) - (a + 1) * math.cos(w0))
        b2 = a * ((a + 1) - (a - 1) * math.cos(w0) - 2 * math.sqrt(a) * alpha)
        a0 = (a + 1) + (a - 1) * math.cos(w0) + 2 * math.sqrt(a) * alpha
        a1 = -2 * ((a - 1) + (a + 1) * math.cos(w0))
        a2 = (a + 1) + (a - 1) * math.cos(w0) - 2 * math.sqrt(a) * alpha
        return Biquad(a0, a1, a2, b0, b1, b2,
                      "Low shelf {}Hz {}dB".format(f0, dbgain))

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
                      "High shelf {}Hz {}dB".format(f0, dbgain))

    @classmethod
    def plain(self):
        return Biquad(1, 0, 0, 1, 0, 0, "Null filter")
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
                      "Low pass 1st {}Hz".format(f0))

    @classmethod
    def high_pass_firstorder(cls, f0, q, fs):
        w = math.tan(math.pi * f0 / fs)
        n = 1 / (1 + w)
        b0 = n
        b1 = -b0
        a1 = n * (w - 1)
        return Biquad(1, a1, 0, b0, b1, 0,
                      "High pass 1st {}Hz".format(f0))

    @staticmethod
    def omega(f0, fs):
        return math.pi * f0 / fs * 2

    @staticmethod
    def alpha(omega, q):
        return math.sin(omega) / (2 * q)

    @staticmethod
    def a(dbgain):
        return pow(10, dbgain / 40)


if __name__ == "__main__":
    bq1 = Biquad.low_pass(200, 1.41, 48000)
    print("Lowpass 200Hz: ", bq1)

    bq2 = Biquad.low_pass_firstorder(200, 1, 48000)
    print("Lowpass 200Hz: ", bq2)

    bq3 = Biquad.peaking_eq(1000, 2, -1, 48000)
    print("Peaking EQ 1000Hz, Q2, -1dB ", bq3)
