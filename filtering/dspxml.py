'''
Created on 09.11.2013

@author: matuschd
'''

from filternetwork import Input, BiQuad, Output, Mixer, Volume, Network
from hardwarespec import HardwareSpec
from xml.dom import minidom
import os


def filter_from_node(xmlnode, samplerate):
    # ignore text nodes
    if xmlnode.nodeType != minidom.Node.ELEMENT_NODE:
        return None
    filtertype=xmlnode.tagName
    filterelement=None
    
    if filtertype=="input":
        filterelement=Input()
    elif filtertype=="biquad":
        filterelement=BiQuad()
    elif filtertype=="output":
        filterelement=Output()
    elif filtertype=="mixer":
        filterelement=Mixer()
    elif filtertype=="volume":
        filterelement=Volume()
    else:
        raise Exception("Unknown filter type "+filtertype)
        
    # set name, every node MUST have a name
    nameAttr=xmlnode.getAttributeNode('name')
    if nameAttr is None:
        raise Exception("Filter with type {} doesn't not have a name".format(filtertype))
    else:
        filterelement.name=nameAttr.nodeValue
        
    filterelement.set_samplerate(samplerate)
        
    # set other attributes
    for aName, aValue in xmlnode.attributes.items():
        # frequency
        if aName=="f" or aName=="frequency":
            filterelement.set_frequency(float(aValue))
        elif aName=="q":
            filterelement.set_q(float(aValue))
        elif aName=="type":
            filterelement.set_type(aValue)
        elif aName=="dbgain":
            gains = [float(x) for x in aValue.split(",")]
            if (len(gains)==1):
                filterelement.set_dbgain(gains[0])
            else:
                filterelement.set_dbgains(gains)
        elif aName=="firstorder":
            if (aValue.lower() in ["yes","true","1"]):
                filterelement.set_first_order(True)
        elif aName=="input":
            for inp in aValue.split(","):
                # store the input names in a separate array to connect them later
                try:
                    filterelement.imported_inputnames.append(inp)
                except AttributeError:
                    filterelement.imported_inputnames=[inp] 
            
    # we need to calculate the coefficients for biquads
    if isinstance(filterelement, BiQuad):
        filterelement.recalc_coefficients()
            
    
    return filterelement;


def network_from_minidom(networknode):
    if networknode.tagName != "network":
        raise Exception("Cannot create network from node {}".format(networknode.tagName))
    
    # get sample rate
    sr=float(networknode.getAttributeNode('samplerate').value)
    
    network=Network()
    network.samplerate=sr
    
    # create nodes
    for filterNode in networknode.childNodes:
        f = filter_from_node(filterNode,sr)
        if f != None:
            network.add_node(f)
            
    # create connections
    # objects have been created with an additional attribute "imported_inputnames" that will be used now
    for f in network.get_nodes():
        try:
            inputnames=f.imported_inputnames
        except AttributeError:
            continue
        
        if len(inputnames)==1:
            inputobject=network.get_node_by_name(inputnames[0])
            if inputobject is not None:
                f.set_input(inputobject)
            else:
                raise Exception("Cannot connect {} with {}".format(f.name,inputnames[0]))
            
        else:
            for i in inputnames:
                inputobject=network.get_node_by_name(i)
                if inputobject is not None:
                    f.add_input(inputobject)
                else:
                    raise Exception("Cannot connect {} with {}".format(f.name,inputnames[0]))
    
    return network
    
def hardware_from_minidom(hardwarenode):
    if hardwarenode.tagName != "hardware":
        raise Exception("Cannot create network from node {}".format(hardwarenode.tagName))
    
    hw = HardwareSpec()
    hw.program=hardwarenode.getAttributeNode('program').value
    hw.param_h=hardwarenode.getAttributeNode('param_h').value
    return hw
    
    

def configuration_from_xml_string(xml, basedir="."):
    xmldoc = minidom.parseString(xml)
    if xmldoc.documentElement.tagName != "dsp":
        raise Exception("Root node is not <dsp>")
    networknodes=xmldoc.documentElement.getElementsByTagName("network")
    if len(networknodes)==1:
        nw=network_from_minidom(networknodes[0])
    elif len(networknodes)==0:
        raise Exception("No network definition found")
    else:
        raise Exception("Multiple network definitions found")
    
    hardwarenodes=xmldoc.documentElement.getElementsByTagName("hardware")
    if len(hardwarenodes)==1:
        hw=hardware_from_minidom(hardwarenodes[0])
        hw.basedir=basedir
    else:
        hw=None
        
    return (nw, hw)
    
    
def configuration_from_xml_file(filename):
    f = open(filename, 'r')
    return configuration_from_xml_string(f.read(),os.path.dirname(filename))


# Demo code

def main():
    (network, hardware) = configuration_from_xml_string('''
        <dsp>
        <network samplerate="48000">
        
         <input name="input1"/>

         <biquad name="bq11" input="input1" type="lowpass1" frequency="200" q="0.7"/>
         <biquad name="bq12" input="bq11"/>
         <biquad name="bq13" input="bq12"/>
         <biquad name="bq14" input="bq13"/>
         <biquad name="bq15" input="bq14"/>
         <biquad name="bq16" input="bq15"/>
         <biquad name="bq17" input="bq16"/>
         <biquad name="bq18" input="bq17"/>
         <biquad name="bq19" input="bq18"/>
         <biquad name="bq110" input="bq19"/>
         <biquad name="bq111" input="bq110"/>
         <biquad name="bq112" input="bq111"/>
         <biquad name="bq113" input="bq112"/>
         <biquad name="bq114" input="bq113"/>
         <biquad name="bq115" input="bq114"/>
         <biquad name="bq116" input="bq115"/>
         <output name="out1" input="bq116" />
         
         <biquad name="bq21" input="input1" type="highpass1" frequency="200" q="0.7" />
         <biquad name="bq22" input="bq21" type="lowpass1" frequency="800" q="0.7" />
         <biquad name="bq23" input="bq22"/>
         <biquad name="bq24" input="bq23"/>
         <biquad name="bq25" input="bq24"/>
         <biquad name="bq26" input="bq25"/>
         <biquad name="bq27" input="bq26"/>
         <biquad name="bq28" input="bq27"/>
         <biquad name="bq29" input="bq28"/>
         <biquad name="bq210" input="bq29"/>
         <biquad name="bq211" input="bq210"/>
         <biquad name="bq212" input="bq211"/>
         <biquad name="bq213" input="bq212"/>
         <biquad name="bq214" input="bq213"/>
         <biquad name="bq215" input="bq214"/>
         <biquad name="bq216" input="bq215"/>
         <output name="out2" input="bq216" />

         <biquad name="bq31" input="input1" type="highpass1" frequency="800" q="0.7" />
         <biquad name="bq32" input="bq31" type="lowpass1" frequency="3000" q="0.7" />
         <biquad name="bq33" input="bq32"/>
         <biquad name="bq34" input="bq33"/>
         <biquad name="bq35" input="bq34"/>
         <biquad name="bq36" input="bq35"/>
         <biquad name="bq37" input="bq36"/>
         <biquad name="bq38" input="bq37"/>
         <biquad name="bq39" input="bq38"/>
         <biquad name="bq310" input="bq39"/>
         <biquad name="bq311" input="bq310"/>
         <biquad name="bq312" input="bq311"/>
         <biquad name="bq313" input="bq312"/>
         <biquad name="bq314" input="bq313"/>
         <biquad name="bq315" input="bq314"/>
         <biquad name="bq316" input="bq315"/>
         <output name="out3" input="bq316" />
 
         <biquad name="bq41" input="input1" type="highpass1" frequency="3000" q="0.7"  />
         <biquad name="bq42" input="bq41"/>
         <biquad name="bq43" input="bq42"/>
         <biquad name="bq44" input="bq43"/>
         <biquad name="bq45" input="bq44"/>
         <biquad name="bq46" input="bq45"/>
         <biquad name="bq47" input="bq46"/>
         <biquad name="bq48" input="bq47"/>
         <biquad name="bq49" input="bq48"/>
         <biquad name="bq410" input="bq49"/>
         <biquad name="bq411" input="bq410"/>
         <biquad name="bq412" input="bq411"/>
         <biquad name="bq413" input="bq412"/>
         <biquad name="bq414" input="bq413"/>
         <biquad name="bq415" input="bq414"/>
         <biquad name="bq416" input="bq415"/>
         <output name="out4" input="bq416" />

        </network>
        <hardware type="ADAU1701" program="" param_h="../../demofiles/generic-4way/generic-4way_IC_1_PARAM.h">
        </hardware>
        </dsp>''')
    
    network.print_response()
    hardware.read_param_h()
    print hardware.network_to_sigmadsp_config(network)
    
        

if __name__ == "__main__":
    main()
        