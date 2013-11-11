'''
Created on 09.11.2013

@author: matuschd
'''

from array import array
from filtermath import *
import biquad


BIQUAD_GENERAL=0
BIQUAD_LOWPASS=1
BIQUAD_HIGHPASS=2
BIQUAD_BANDPASS_PEAK_Q=3
BIQUAD_BANDPASS=4
BIQUAD_NOTCH=5
BIQUAD_ALLPASS=6
BIQUAD_PEAKING_EQ=7
BIQUAD_LOW_SHELF=8
BIQUAD_HIGH_SHELF=9
BIQUAD_LOWPASS_FIRSTORDER=10
BIQUAD_HIGHPASS_FIRSTORDER=11

BIQUAD_TYPES = {'general':              BIQUAD_GENERAL, 
                'lowpass':              BIQUAD_LOWPASS,
                'highpass':             BIQUAD_HIGHPASS,
                'lowpass1':             BIQUAD_LOWPASS_FIRSTORDER,
                'highpass1':            BIQUAD_HIGHPASS_FIRSTORDER,
                'bandpass_peak_q':      BIQUAD_BANDPASS_PEAK_Q,
                'bandpass':             BIQUAD_BANDPASS,
                'notch':                BIQUAD_NOTCH,
                'allpass':              BIQUAD_ALLPASS,
                'peaking_eq':           BIQUAD_PEAKING_EQ,
                'low_shelf':            BIQUAD_LOW_SHELF,
                'high_shelf':           BIQUAD_HIGH_SHELF
                }

DEFAULT_FREQUENCIES = [10,15,20,30,40,50,75,
                       100,150,200,300,400,500,750,
                       1000,1500,2000,3000,4000,5000,7500,
                       10000,15000,20000]


class Network(object):
    
    def __init__(self):
        self.samplerate=48000
        self.nodes=[]
        return
    
    def get_nodes(self):
        return self.nodes
    
    def set_nodes(self, nodes):
        self.nodes=nodes
        
    def get_node_by_name(self,nodename):
        for n in self.nodes:
            if (n.get_name() == nodename):
                return n
        return None
    
    def add_node(self, node):
        self.nodes.append(node)
        
    def __str__(self):
        res=""
        for n in self.nodes:
            res=res+str(n)+"\n"
        return res
    
    def print_response(self):
        for n in self.nodes:
            if isinstance(n, Output):
                print n.name
                print "  Freq       Mag   Phase"
                for (f,mag,phase) in n.get_response():
                    print u"{:6.0f} {:7.2f}db {:7.2f}\u00B0".format(f,mag,phase/2/math.pi*360)
                    
    def get_outputs(self):
        res=[]
        for n in self.nodes:
            if isinstance(n, Output):
                res.append(n)
        return res        


class Filter(object):
    ''' 
    The basic filter class that is the parent for all filters.
    '''

    def __init__(self):
        self.fs=48000
        self.name="?"
        return
    
    def set_samplerate(self,fs):
        self.fs=fs
    
    def get_response(self):
        return None
    
    def set_name(self,name):
        self.name=name
        
    def get_name(self):
        return self.name

    def set_input(self,input_filter):
        self.input_filter = input_filter
    
    def __str__(self):
        return "Generic filter"


class Input(Filter):
    
    def __init__(self):
        super(Input,self).__init__()
        return
    
    def get_response(self):
        resp=[]
        for f in DEFAULT_FREQUENCIES:
            val=array('d',[f,0,0])
            resp.append(val)
        return resp

    def __str__(self):
        return self.name+" (Input)"
    
class Output(Filter):
    
    def __init__(self):
        super(Output,self).__init__()
        return
    
        
    def get_response(self):
        return self.input_filter.get_response()

    def __str__(self):
        return self.name+" (Output)"
    
    
    
    
class BiQuad(Filter):
    
    def __init__(self):
        super(BiQuad,self).__init__()
        self.filtertype=BIQUAD_GENERAL
        self.q=1
        self.dbgain=0
        self.f=1
        self.set_coefficients([0,0,1,0,0])
        self.first_order=False
        return
    
    def __filterstr_to_type__(self,s):
        return BIQUAD_TYPES[s.lower()]
        
    def set_coefficients(self,paramlist):
        '''
        paramlist = [a1, a2, b0, b1, b2]
        '''
        self.a1=paramlist[0]
        self.a2=paramlist[1]
        self.b0=paramlist[2]
        self.b1=paramlist[3]
        self.b2=paramlist[4]
        
    def set_type(self,filtertype):
        if isinstance(filtertype, basestring):
            filtertype=self.__filterstr_to_type__(filtertype)
        self.filtertype=filtertype;
        
    def set_frequency(self, f):
        self.f=f
        
    def set_q(self,q):
        self.q=q
        
    def set_dbgain(self,dbgain):
        self.dbgain=dbgain
        
    def recalc_coefficients(self):
        if self.filtertype == BIQUAD_LOWPASS:
            self.set_coefficients(biquad.low_pass(self.f,self.q, self.fs))
        elif self.filtertype == BIQUAD_HIGHPASS:
            self.set_coefficients(biquad.high_pass(self.f,self.q, self.fs))
        elif self.filtertype == BIQUAD_BANDPASS_PEAK_Q:
            self.set_coefficients(biquad.band_pass_peak_q(self.f,self.q, self.fs))
        elif self.filtertype == BIQUAD_BANDPASS:
            self.set_coefficients(biquad.band_pass(self.f,self.q, self.fs))
        elif self.filtertype == BIQUAD_NOTCH:
            self.set_coefficients(biquad.notch(self.f,self.q, self.fs))
        elif self.filtertype == BIQUAD_ALLPASS:
            self.set_coefficients(biquad.all_pass(self.f,self.q, self.fs))
        elif self.filtertype == BIQUAD_PEAKING_EQ:
            self.set_coefficients(biquad.peaking_eq(self.f,self.q, self.dbgain, self.fs))
        elif self.filtertype == BIQUAD_LOW_SHELF:
            self.set_coefficients(biquad.low_shelf(self.f,self.q, self.dbgain, self.fs))
        elif self.filtertype == BIQUAD_HIGH_SHELF:
            self.set_coefficients(biquad.low_shelf(self.f,self.q, self.dbgain, self.fs))
        elif self.filtertype == BIQUAD_LOWPASS_FIRSTORDER:
            self.set_coefficients(biquad.low_pass_firstorder(self.f,self.q, self.fs))
        elif self.filtertype == BIQUAD_HIGHPASS_FIRSTORDER:
            self.set_coefficients(biquad.high_pass_firstorder(self.f,self.q, self.fs))

        
        if self.first_order:
            self.a2=0
            self.b2=0
            
            
    def get_coefficient(self,name):
        return self.__dict__[name]
           
        
    def get_response(self):
        input_response=self.input_filter.get_response()
        res=[]
        for iresp in input_response:
            f=iresp[0]
            input_mag=iresp[1]
            input_phase=iresp[2]
            
            omega=math.pi*f/self.fs
            numerator_real=self.b0+self.b1*math.cos(omega)+self.b2*math.cos(2*omega)
            numerator_imag=-(self.b1*math.sin(omega)+self.b2*math.sin(2*omega))
            denominator_real=1+self.a1*math.cos(omega)+self.a2*math.cos(2*omega)
            denominator_imag=-(self.a1*math.sin(omega)+self.a2*math.sin(2*omega))
            magnitude=math.sqrt((numerator_real*numerator_real+numerator_imag*numerator_imag)/(denominator_real*denominator_real+denominator_imag*denominator_imag));
            phase=math.atan2(numerator_imag,numerator_real)-math.atan2(denominator_imag,denominator_real);
            
            # add phase and magnitude to previous stage
            phase=phase+input_phase
            magnitude=magnitude_to_db(magnitude)+input_mag
    
            
            resp=array('d',[f,magnitude,phase])
            res.append(resp)
        return res
    
    '''
    convert the filter to a first-order filter by setting a2 and b2 to 0
    '''
    def set_first_order(self,first_order=True):
        self.first_order=first_order
        self.recalc_coefficients()
    
    def __str__(self):
        # TODO add more details
        return "{} (BiQuad (a1={} a2={} b0={} b1={} b2={})".format(self.name,self.a1,self.a2,self.b0,self.b1,self.b2)

    
# Demo code

def main():
    i1 = Input()
    bq1 = BiQuad()
    bq1.set_input(i1)    
    [a1,a2,b0,b1,b2]=biquad.low_pass(2000,0.7,48000)
    bq1.set_coefficients([a1,a2,b0,b1,b2])
    
    bq2 = BiQuad()
    bq2.set_input(bq1)    
    [a1,a2,b0,b1,b2]=biquad.high_pass(500,0.7,48000)
    bq2.set_coefficients([a1,a2,b0,b1,b2])

    bq3 = BiQuad()
    bq3.set_input(bq2)    
    [a1,a2,b0,b1,b2]=biquad.peaking_eq(5000,0.7,20,48000)
    bq3.set_coefficients([a1,a2,b0,b1,b2])

    for v in bq2.get_response():
        print v
        

if __name__ == "__main__":
    main()
        