'''
Created on 11.11.2013

@author: matuschd
'''
import re
import os.path
from filternetwork import *

LSB_SIGMA=float(1)/math.pow(2,23)

def float_to_28bit_fixed(f):
    '''
    converts a float to an 28bit fixed point value used in SigmaDSP processors
    '''
    if (f>16-LSB_SIGMA) or (f<-16):
        raise Exception("value {} not in range [-16,16]".format(f))
    
    # dual complement
    if (f<0):
        f=32+f
    
    # multiply by 2^23, then convert to integer
    f=f*(1<<23)
    return int(f)
    
'''
a generic class that holds some hardware information
'''
class HardwareSpec(object):
    
    def __init__(self):
        self.type="unknown"
        self.program=""
        self.param_h=""
        self.address={}
        self.basedir="."
        return
    
    def read_param_h(self):
        f = open(self.param_h, 'r')
        
        # Regexps:
        #define MOD_BQ116_ALG0_STAGE0_B0_ADDR 89  -> BQ116, B0 = 89
        biquad_re = re.compile('#define MOD_([A-Z0-9]*)_ALG0_STAGE0_([AB][012])_ADDR\s*([0-9]*)')
        
        for line in f:
            match=biquad_re.match(line)
            if match:
                name=match.group(1)+"__"+match.group(2)
                self.address[name.lower()]=int(match.group(3)) 
                
    def network_to_sigmadsp_config(self, network, ignoremissing=True):
        '''
        read all parameters from a network and create a hardware configuration
        '''
        res={}
        for n in network.get_nodes():
            if isinstance(n,BiQuad):
                for v in ["a1","a2","b0","b1","b2"]:
                    # unfortunately, SigmaStudio has an incorrect naming for the A parameters
                    try:
                        if (v=="a1"):
                            addr=self.address[n.name+"__a0"]
                        elif (v=="a2"):
                            addr=self.address[n.name+"__a1"]
                        else:
                            addr=self.address[n.name+"__"+v]
                    except KeyError:
                        if not ignoremissing:
                            raise Exception("Address for {}.{} not found in parameter definition".format(n.name,v))
                    value=n.get_coefficient(v)
                    res[str(addr)]=float_to_28bit_fixed(value)
        return res;
    
    def get_programfile(self):
        return os.path.join(self.basedir,self.program)
    

#
# Demo code
#
def main():
    print "0       {:07x}".format(float_to_28bit_fixed(0))
    print "16-1LSB {:07x}".format(float_to_28bit_fixed(16-LSB_SIGMA))
    print "8       {:07x}".format(float_to_28bit_fixed(8))
    print "-16     {:07x}".format(float_to_28bit_fixed(-16))
    print "0.25    {:07x}".format(float_to_28bit_fixed(0.25))
    print "-0.25   {:07x}".format(float_to_28bit_fixed(-0.25))
    
    hw = HardwareSpec()
    hw.param_h="../../demofiles/generic-4way/generic-4way_IC_1_PARAM.h"
    hw.read_param_h()
    print hw.address
    
    return

if __name__ == '__main__':
    main()