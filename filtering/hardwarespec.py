'''
Created on 11.11.2013

@author: matuschd
'''
import re
import os.path
from filternetwork import *
import filtermath

    
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
        f = open(os.path.join(self.basedir,self.param_h), 'r')
        
        # Regexps:
        #define MOD_BQ116_ALG0_STAGE0_B0_ADDR 89  -> BQ116, B0 = 89
        #define MOD_MX1_ALG0_STAGE0_MONOSWITCHNOSLEW_ADDR
        biquad_re = re.compile('#define MOD_([A-Z0-9]*)_ALG0_STAGE0_([AB][012])_ADDR\s*([0-9]*)')
        monomixer_re = re.compile("#define MOD_([A-Z0-9]*)_ALG0_STAGE([012]*)_MONOSWITCHNOSLEW_ADDR\s*([0-9]*)")
        
        #
        
        for line in f:
            # Check for biquad
            match=biquad_re.match(line)
            if match:
                name=match.group(1)+"__"+match.group(2)
                self.address[name.lower()]=int(match.group(3))
                continue
            
            # check for monoswitch, which is basically a mixer
            match=monomixer_re.match(line)
            if match:
                name=match.group(1)+"__"+match.group(2)
                self.address[name.lower()]=int(match.group(3))
                continue
                
                
    def network_to_sigmadsp_config(self, network, ignoremissing=False):
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
                    if v.startswith("a"):
                        # a1 and a2 needs to be inverted for the SigmaDSP BiQuad filter
                        paramvalue=-value
                    else:
                        paramvalue=value
                        
                    res[str(addr)]=paramvalue
            if isinstance(n,Mixer):
                gains=n.get_dbgains()
                for i in range(0,len(gains)):
                    try:
                        addr=self.address[n.name+"__"+str(i)]
                    except KeyError:
                        if not ignoremissing:
                            raise Exception("Address for {}.{} not found in parameter definition".format(n.name,v))
                    value=gains[i] # TODO: convert to multiplier
                    res[str(addr)]=filtermath.db_to_gain(value)
                # TODO
        return res;
    
    def get_programfile(self):
        return os.path.join(self.basedir,self.program)
    

#
# Demo code
#
def main():

    
    hw = HardwareSpec()
    hw.param_h="../../demofiles/generic-4way/generic-4way_IC_1_PARAM.h"
    hw.read_param_h()
    print hw.address
    
    return

if __name__ == '__main__':
    main()