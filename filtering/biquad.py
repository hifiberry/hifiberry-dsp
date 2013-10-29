'''
Created on 09.11.2013

@author: matuschd

Formulas from "Cookbook formulae for audio EQ biquad filter coefficients"
by Robert Bristow-Johnson  <rbj@audioimagination.com>
'''

import math

def _omega(f0,fs):
    return math.pi*f0/fs*2

def _alpha(omega,q):
    return math.sin(omega)/(2*q)

def _a(dbgain):
    return pow(10,dbgain/40)     

def _normalize(params,a0):
    res=[]
    for p in params:
        res.append(p/a0)
    return res


def low_pass(f0,q,fs):
    w0=_omega(f0,fs)
    alpha=_alpha(w0,q)
    b0 =  (1 - math.cos(w0))/2            
    b1 =   1 - math.cos(w0)            
    b2 =  (1 - math.cos(w0))/2            
    a0 =   1 + alpha            
    a1 =  -2* math.cos(w0)            
    a2 =   1 - alpha
    return _normalize([a1,a2,b0,b1,b2],a0)


def high_pass(f0,q,fs):
    w0=_omega(f0,fs)
    alpha=_alpha(w0,q)
    b0 =  (1 + math.cos(w0))/2            
    b1 = -(1 + math.cos(w0))            
    b2 =  (1 + math.cos(w0))/2            
    a0 =   1 + alpha            
    a1 =  -2*math.cos(w0)            
    a2 =   1 - alpha    
    return _normalize([a1,a2,b0,b1,b2],a0)

def band_pass_peak_q(f0,q,fs):
    w0=_omega(f0,fs)
    alpha=_alpha(w0,q)
    b0 =   math.sin(w0)/2           
    b1 =   0            
    b2 =  -math.sin(w0)/2           
    a0 =   1 + alpha            
    a1 =  -2*math.cos(w0)            
    a2 =   1 - alpha
    return _normalize([a1,a2,b0,b1,b2],a0)

def band_pass(f0,q,fs):
    w0=_omega(f0,fs)
    alpha=_alpha(w0,q)
    b0 =   alpha            
    b1 =   0            
    b2 =  -alpha            
    a0 =   1 + alpha            
    a1 =  -2*math.cos(w0)            
    a2 =   1 - alpha
    return _normalize([a1,a2,b0,b1,b2],a0)


def notch(f0,q,fs):
    w0=_omega(f0,fs)
    alpha=_alpha(w0,q)
    b0 =   1            
    b1 =  -2*math.cos(w0)            
    b2 =   1            
    a0 =   1 + alpha            
    a1 =  -2*math.cos(w0)            
    a2 =   1 - alpha
    return _normalize([a1,a2,b0,b1,b2],a0)


def all_pass(f0,q,fs):
    w0=_omega(f0,fs)
    alpha=_alpha(w0,q)
    b0 =   1 - alpha            
    b1 =  -2*math.cos(w0)            
    b2 =   1 + alpha            
    a0 =   1 + alpha            
    a1 =  -2*math.cos(w0)            
    a2 =   1 - alpha
    return _normalize([a1,a2,b0,b1,b2],a0)

def peaking_eq(f0,q,dbgain,fs):
    w0=_omega(f0,fs)
    alpha=_alpha(w0,q)
    a=_a(dbgain)
    b0 =   1 + alpha*a            
    b1 =  -2*math.cos(w0)            
    b2 =   1 - alpha*a            
    a0 =   1 + alpha/a            
    a1 =  -2*math.cos(w0)            
    a2 =   1 - alpha/a
    return _normalize([a1,a2,b0,b1,b2],a0)


def low_shelf(f0,q,dbgain,fs):
    w0=_omega(f0,fs)
    alpha=_alpha(w0,q)
    a=_a(dbgain)
    b0 =    a*( (a+1) - (a-1)*math.cos(w0) + 2*math.sqrt(a)*alpha )            
    b1 =  2*a*( (a-1) - (a+1)*math.cos(w0)                   )            
    b2 =    a*( (a+1) - (a-1)*math.cos(w0) - 2*math.sqrt(a)*alpha )            
    a0 =        (a+1) + (a-1)*math.cos(w0) + 2*math.sqrt(a)*alpha            
    a1 =   -2*( (a-1) + (a+1)*math.cos(w0)                   )            
    a2 =        (a+1) + (a-1)*math.cos(w0) - 2*math.sqrt(a)*alpha
    return _normalize([a1,a2,b0,b1,b2],a0)
    

def high_shelf(f0,q,dbgain,fs):    
    w0=_omega(f0,fs)
    alpha=_alpha(w0,q)
    a=_a(dbgain)
    b0 =    a*( (a+1) + (a-1)*math.cos(w0) + 2*math.sqrt(a)*alpha )            
    b1 = -2*a*( (a-1) + (a+1)*math.cos(w0)                   )            
    b2 =    a*( (a+1) + (a-1)*math.cos(w0) - 2*math.sqrt(a)*alpha )            
    a0 =        (a+1) - (a-1)*math.cos(w0) + 2*math.sqrt(a)*alpha            
    a1 =    2*( (a-1) - (a+1)*math.cos(w0)                   )            
    a2 =        (a+1) - (a-1)*math.cos(w0) - 2*math.sqrt(a)*alpha
    return _normalize([a1,a2,b0,b1,b2],a0)
    
    
''' 
from A pratical guide for digital audio IIR filters
http://freeverb3.sourceforge.net/iir_filter.shtml
'''
def low_pass_firstorder(f0,q,fs):
    w = math.tan(math.pi*f0/fs)
    n = 1/(1+w)
    b0 = w*n
    b1 = b0
    a1 = n*(w-1)
    return [a1,0,b0,b1,0]

def high_pass_firstorder(f0,q,fs):
    w = math.tan(math.pi*f0/fs)
    n = 1/(1+w)
    b0 = n
    b1 = -b0
    a1 = n*(w-1)    
    return [a1,0,b0,b1,0]

