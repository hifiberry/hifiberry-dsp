'''
Created on 09.11.2013

@author: matuschd
'''

from filternetwork import Input, BiQuad, Output, Network
from xml.dom import minidom


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
            filterelement.set_dbgain(float(aValue))
        elif aName=="input":
            # store the input names in a separate array to connect them later
            try:
                filterelement.imported_inputnames.append(aValue)
            except AttributeError:
                filterelement.imported_inputnames=[aValue] 
            
    # we need to calculate the coefficients for biquads
    if isinstance(filterelement, BiQuad):
        filterelement.recalc_coefficients()
            
    
    return filterelement;


def network_from_minidom(dom):
    if dom.documentElement.tagName != "network":
        return None
    
    # get sample rate
    sr=float(dom.documentElement.getAttributeNode('samplerate').value)
    
    
    network=Network()
    network.samplerate=sr
    
    
    # create nodes
    for filterNode in dom.documentElement.childNodes:
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
            raise Exception("Multiple inputs on a filter not supported yet")
    
    return network
    
         

def network_from_xml_string(xml):
    xmldoc = minidom.parseString(xml)
    return network_from_minidom(xmldoc)


# Demo code

def main():
    n = network_from_xml_string('<network samplerate="48000">\
        <input name="input1"/>\
        <biquad name="bq1" input="input1" type="allpass" frequency="200" q="1" />\
        <biquad name="bq2" input="bq1" type="lowpass" frequency="1000" q="0.7" />\
        <biquad name="bq3" input="bq2" type="highpass" frequency="100" q="0.7" />\
        <biquad name="bq4" input="bq3" type="notch" frequency="400" q=".1" />\
        <biquad name="bq5" input="bq4" type="peaking_eq" frequency="700" q="4" dbgain="3" />\
        <output name="out1" input="bq5" />\
        </network>')
    n.print_response()
        

if __name__ == "__main__":
    main()
        