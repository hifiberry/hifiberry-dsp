'''
Created on 09.11.2013

Some basic math for magnitude and phase calculations

@author: matuschd
'''
import math

def magnitude_to_db(mag):
    return 20*math.log10(mag)

def db_to_gain(db):
    return pow(10,db/20)


'''
sum to signals with given db value
e.g. db_sum(-3,-3)=0
'''
def db_sum(db1,db2):
    # convert to volt, add and then convert back to db
    v1=db_to_gain(db1)
    v2=db_to_gain(db2)
    return magnitude_to_db(v1+v2)


