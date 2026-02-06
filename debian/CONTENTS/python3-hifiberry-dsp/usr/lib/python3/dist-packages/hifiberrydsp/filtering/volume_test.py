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
'''
import unittest

from .volume import percent2amplification, amplification2percent,decibel2amplification, amplification2decibel


class Test(unittest.TestCase):


    def testPercentAmplification(self):
        for dbrange in [60, 70, 80, 90, 120]:
            for percent in range(0,100):
                # print(percent2amplification(percent, dbrange))
                self.assertEqual(percent, amplification2percent(percent2amplification(percent, dbrange), dbrange), 
                                 "amplification/percent mismatch at {}% (range {}db)".format(percent, dbrange))

    def testDecibelAmplification(self):
        for decibel in range(-100,10):
            self.assertEqual(decibel, round(amplification2decibel(decibel2amplification(decibel))), 
                             "amplfication/decibel mismatch at {}db)".format(decibel))

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()