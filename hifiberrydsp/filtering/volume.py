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


def decibel2amplification(db):
    return pow(10, db / 20)


def amplification2decibel(amplification):
    if (amplification > 0):
        return math.log10(amplification) * 20
    else:
        return float('-inf')


def log_coefficients(dbrange):

    if dbrange <= 50:
        a = 0.0031623
        b = 5.757
    elif dbrange <= 60:
        a = 0.001
        b = 6.908
    elif dbrange <= 70:
        a = 0.00031623
        b = 8.059
    elif dbrange <= 80:
        a = 0.0001
        b = 9.210
    elif dbrange <= 90:
        a = 0.000031623
        b = 10.36
    else:
        a = 0.00001
        b = 11.51

    return (a, b)


def percent2amplification(percent, dbrange=60):
    if percent <= 0:
        return 0

    (a, b) = log_coefficients(dbrange)
    return a * math.exp(b * float(percent) / 100)


def amplification2percent(amplification, dbrange=60):

    if amplification <= 0:
        return 0

    if amplification >= 1:
        return 100

    (a, b) = log_coefficients(dbrange)
    return round((math.log(amplification / a) / b) * 100)


if __name__ == '__main__':
    for i in range(0, 101, 10):
        a = percent2amplification(i)
        db = amplification2percent(a)
        print("{} {} {}".format(i, a, db))

    for i in range(0, -100, -2):
        a = decibel2amplification(i)
        db = amplification2decibel(a)
        print("{} {} {}".format(i, a, db))
