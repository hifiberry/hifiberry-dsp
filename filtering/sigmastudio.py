'''
Created on 10.11.2013

@author: matuschd
'''

from filternetwork import Network, Input, Output, BiQuad


def lines_to_network(lines):
    network=Network()
    for l in lines:
        parts=l.split()
        node=None
        print parts
        if len(parts)>=4:
            print "h"
            typename=parts[1]
            if typename.startswith("EQ1940SingleS"):
                print "g"
                # biquad filter
                node=BiQuad()
                node.name=typename
            elif typename.startswith("EQ1940Single"):
                node=BiQuad()
                node.name=typename
            elif typename.startswith("ICSigma100Out"):
                node=Output()
                node.name=typename
            elif typename.startswith("ICSigma100In"):
                # split input into separate input nodes
                inputs=parts[2:]
                i=0
                while len(inputs)>=2:
                    inp=Input()
                    inp.name=typename+"_"+str(i)
                    network.add_node(inp)
        if node is not None:
            network.add_node(node)
        return network
                           
                

# demo code
def main():
    networkdefinition=["0 ICSigma100In1 O_C0_A0_P1_out Link0 O_C0_A0_P2_out Link1 O_C0_A0_P3_out Link6",
                       "1 EQ1940Single1 I_C13_A0_P1_in Link0 O_C13_A0_P2_out Link2",
                       "2 EQ1940SingleS1 I_C18_A0_P1_in Link1 O_C18_A0_P2_out Link3",
                       "3 EQ1940Single3 I_C54_A0_P1_in Link6 O_C54_A0_P2_out Link7",
                       "4 EQ1940SingleS2 I_C24_A0_P1_in Link2 O_C24_A0_P2_out Link4",
                       "5 EQ1940Single2 I_C21_A0_P1_in Link3 O_C21_A0_P2_out Link5",
                       "6 ICSigma100Out3 I_C41_A0_P1_in Link7",
                       "7 ICSigma100Out1 I_C11_A0_P1_in Link4",
                       "8 ICSigma100Out2 I_C35_A0_P1_in Link5"]

    print lines_to_network(networkdefinition)

if __name__ == '__main__':
    main()