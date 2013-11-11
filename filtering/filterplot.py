'''
Created on 10.11.2013

@author: matuschd
'''

from matplotlib import pyplot
import dspxml
import math


def transpose_response(resp):
    f=[]
    mag=[]
    phase=[]
    for r in resp:
        f.append(r[0])
        mag.append(r[1])
        phase.append(r[2]/2/math.pi*360)
    return (f,mag,phase)

def plot_response(node):
    
    print node
    response=node.get_response()
    print response
    
    (f,mag,phase) = transpose_response(response)
        

    pyplot.subplot(2, 1, 1)
    pyplot.plot(f, mag, 'yo-')
    pyplot.title('Filter response')
    pyplot.ylabel('Magnitude')
    pyplot.xscale('log')
    pyplot.xlim(20,20000)
    pyplot.ylim(-50,10)

    pyplot.subplot(2, 1, 2)
    pyplot.plot(f, phase, 'r.-')
    pyplot.xlabel('frequency(Hz)')
    pyplot.ylabel('Phase (degree)')
    pyplot.xscale('log')
    pyplot.xlim(20,20000)
    pyplot.ylim(-180,180)

    pyplot.show()
    
    
# Demo code

def main():
    n = dspxml.network_from_xml_string('<network samplerate="48000">\
        <input name="input1"/>\
        <biquad name="bq1" input="input1" type="lowpass" frequency="1000" q="0.7" />\
        <biquad name="bq2" input="bq1" type="highpass" frequency="100" q="0.7" />\
        <output name="out1" input="bq2" />\
        </network>')
    print n
    print n.get_outputs()
    plot_response(n.get_outputs()[0])
        

if __name__ == "__main__":
    main()