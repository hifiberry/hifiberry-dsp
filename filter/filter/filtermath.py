'''
Created on 09.11.2013

Some basic math for magnitude and phase calculations

@author: matuschd
'''
import math

def magnitude_to_db(mag):
    return 20*math.log10(mag)


