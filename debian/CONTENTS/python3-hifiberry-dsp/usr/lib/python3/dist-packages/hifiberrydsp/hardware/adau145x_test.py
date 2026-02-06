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
from hifiberrydsp.hardware.adau145x import Adau145x

class Test(unittest.TestCase):


    def testConversion(self):
        return
        for mul in [-2, -1, -.8, -.3, 0.1, 0.3, 0.331, 0.6, 0.9, 1, 1.2]:
            for d in [0.0001, 0.1234, 0.5, 0.51, 0.52, 0.53, 0.7, 1, 1.1, 1.2, 1.22, 2.9, 0]:
                val = mul * d
                print(val)
                print(Adau145x.decimal_repr(val))
                self.assertAlmostEqual(val,Adau145x.decimal_val(Adau145x.decimal_repr(val)), 5)
                
                
    def testValues(self):
        # Known good representations (calculated in SigmaStudio)
        known_good = {
            0x80000000: -128,
            0xFF000000: -1,
            0: 0,
            0x40000000: 64,
            0x1000000:  1,
            0x10000:    0.00390625,
        }
        
        for b in known_good:
            f=known_good[b]
            self.assertEqual(b,Adau145x.decimal_repr(f), "float -> int failed for {}/{}".format(b,f))
            self.assertEqual(f,Adau145x.decimal_val(b), "int -> float failed for {}/{}".format(b,f))


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testConversion']
    unittest.main()