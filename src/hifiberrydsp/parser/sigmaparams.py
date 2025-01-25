'''
Copyright (c) 2018 Modul 9/HiFiBerry

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

import sys
import os.path

from hifiberrydsp.parser.xmlprofile import ATTRIBUTE_BALANCE, \
    ATTRIBUTE_FIR_FILTER_LEFT, ATTRIBUTE_FIR_FILTER_RIGHT, \
    ATTRIBUTE_CUSTOM_FILTER_LEFT, ATTRIBUTE_CUSTOM_FILTER_RIGHT, \
    ATTRIBUTE_TONECONTROL_FILTER_LEFT, ATTRIBUTE_TONECONTROL_FILTER_RIGHT, \
    ATTRIBUTE_VOL_CTL, ATTRIBUTE_VOL_LIMIT, \
    ATTRIBUTE_VOL_LIMIT_PI, ATTRIBUTE_VOL_LIMIT_SPDIF, \
    ATTRIBUTE_VOL_LIMIT_AUX, \
    ATTRIBUTE_MUTE_PI, ATTRIBUTE_MUTE_SPDIF, \
    ATTRIBUTE_MUTE_AUX, ATTRIBUTE_SPDIF_ENABLE, \
    ATTRIBUTE_MUTE_REG, \
    ATTRIBUTE_CHANNEL_SELECT, ATTRIBUTE_INVERT_MUTE, \
    ATTRIBUTE_SPDIF_SOURCE, ATTRIBUTE_AUTOMUTE, ATTRIBUTE_UNMUTE_DELAY, \
    ATTRIBUTE_AUTOMUTE_LEVEL, ATTRIBUTE_INPUT_SELECT,\
    ATTRIBUTE_LOUDNESS, ATTRIBUTE_LOUDNESS_LEVELS, \
    XmlProfile

PARAMETER_MAPPING = {
    "balance": ATTRIBUTE_BALANCE,
    "balancevalue": ATTRIBUTE_BALANCE,
    "loudness.target": ATTRIBUTE_LOUDNESS,
    "loudness.level_low": ATTRIBUTE_LOUDNESS_LEVELS,
    "volume.target": ATTRIBUTE_VOL_CTL,
    "volumelimit.target": ATTRIBUTE_VOL_LIMIT,
    "mastervol.target": ATTRIBUTE_VOL_CTL,
    "masterlimit.target": ATTRIBUTE_VOL_LIMIT,
    "channelselect": ATTRIBUTE_CHANNEL_SELECT,
    "mute": ATTRIBUTE_MUTE_REG,
    "invertmute": ATTRIBUTE_INVERT_MUTE,
    "spdifsource": ATTRIBUTE_SPDIF_SOURCE,
    "fir_l": ATTRIBUTE_FIR_FILTER_LEFT,
    "fir_r": ATTRIBUTE_FIR_FILTER_RIGHT,
    "iir_l": ATTRIBUTE_CUSTOM_FILTER_LEFT,
    "iir_r": ATTRIBUTE_CUSTOM_FILTER_RIGHT,
    "tonecontrol_l": ATTRIBUTE_TONECONTROL_FILTER_LEFT,
    "tonecontrol_r": ATTRIBUTE_TONECONTROL_FILTER_RIGHT,
    "automute": ATTRIBUTE_AUTOMUTE,
    "automutelevel": ATTRIBUTE_AUTOMUTE_LEVEL,
    "unmutedelay": ATTRIBUTE_UNMUTE_DELAY,
    "volumelimitpi.target": ATTRIBUTE_VOL_LIMIT_PI,
    "volumelimitspdif.target": ATTRIBUTE_VOL_LIMIT_SPDIF,
    "volumelimitaux.target": ATTRIBUTE_VOL_LIMIT_AUX,
    "mutepi": ATTRIBUTE_MUTE_PI,
    "mutespdif": ATTRIBUTE_MUTE_SPDIF,
    "muteaux": ATTRIBUTE_MUTE_AUX,
    "enablespdif": ATTRIBUTE_SPDIF_ENABLE,
    "toslinkenable": ATTRIBUTE_SPDIF_ENABLE,
    "inputselect": ATTRIBUTE_INPUT_SELECT,
}


for lr in ["L", "R"]:
    for channel in range(1, 5):
        name = "iir_{}{}".format(lr.lower(), channel)
        attribute = "IIR_%LR%%CHANNEL%".replace(
            "%LR%", lr).replace("%CHANNEL%", str(channel))
        PARAMETER_MAPPING[name] = attribute
        
        
for ch in ["A","B","C","D", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9" ]:
        name = "eq_{}".format(ch.lower())
        attribute = "IIR_%CHANNEL%".replace("%CHANNEL%", ch)
        PARAMETER_MAPPING[name] = attribute
        
        name = "iir_{}".format(ch.lower())
        attribute = "IIR_%CHANNEL%".replace("%CHANNEL%", ch)
        PARAMETER_MAPPING[name] = attribute
        
        name = "delay_{}".format(ch.lower())
        attribute = "delay%CHANNEL%Register".replace("%CHANNEL%", ch)
        PARAMETER_MAPPING[name] = attribute

        name = "vol_{}".format(ch.lower())
        attribute = "levels%CHANNEL%Register".replace("%CHANNEL%", ch)
        PARAMETER_MAPPING[name] = attribute


class SigmastudioParamsFile():
    """
    This class handles metadata in DSP profile files.
    It can parse .params files exported by SigmaStudio and automatically create metadata records
    in a XML DSP profile based on standard naming.
    """

    def __init__(self, filename):
        """
        Opens a .params file and parse it
        """
        self.parameter_start_address = {}
        self.parameter_end_address = {}

        cellname = None
        address = None
        plen = 0
        pdata = False

        with open(filename) as params:
            for line in params:
                try:
                    name, value = line.split("=")
                    name = name.strip().lower()
                    value = value.strip().lower()

                    if name == "cell name":
                        cellname = value

                    if name == "parameter name":
                        paramname = value

                    if name == "parameter address":
                        address = int(value)

                except ValueError:

                    if line.lower().startswith("parameter data :"):
                        pdata = True

                    if line.strip() == "" and cellname is not None:
                        self.process_cell(cellname, paramname, address, plen)
                        cellname = None
                        paramname = None
                        address = None
                        pdata = False
                        plen = 0

                    else:
                        if pdata:
                            if line.startswith("0x"):
                                plen += 1

    def process_cell(self, cellname, paramname, address, length):
        """
        Parses a single cell in the .params file. This usually maps to a 
        DSP building block in SigmaStudio.
        
        Based on the PARAMETER_MAPPING, it will create the required 
        metadata records
        """

        name = cellname.split(".")[-1]
        
        for cell in PARAMETER_MAPPING:
            if "." in cell:
                cell_key, param_key = cell.split(".")
            else:
                cell_key = cell
                param_key = None

            if cell_key == name:
                if param_key is None or paramname.endswith(param_key):

                    attrib = PARAMETER_MAPPING[cell]

                    if attrib in self.parameter_start_address:
                        self.parameter_end_address[attrib] = address
                    else:
                        self.parameter_start_address[attrib] = address

                    if length > 1:
                        self.parameter_end_address[attrib] = address + \
                            length - 1

    def param_list(self):
        """
        Get a list of all parameters that have been loadef from the .params file.
        """
        result = {}
        for param in self.parameter_start_address:
            address = self.parameter_start_address[param]
            if param in self.parameter_end_address:
                end_address = self.parameter_end_address[param]
                length = end_address - address + 1
                address = "{}/{}".format(address, length)
            else:
                address = str(address)

            result[param] = address

        return result

    def merge_params_into_xml(self, xmlfile):
        """
        Add the metadata into a XML DSP project file.
        """
        xml = XmlProfile(xmlfile)
        param_list = self.param_list()
        xml.update_metadata(param_list)
        xml.write_xml(xmlfile)
        return param_list


def basefilename(filename):
    base = os.path.basename(filename)
    return os.path.splitext(base)[0]


def extension(filename):
    base = os.path.basename(filename)
    return os.path.splitext(base)[1]


def merge_params_main(xmlfile=None, paramsfile=None):

    if paramsfile == None:
        # called from command line
        try:
            xmlfile = sys.argv[1]
            paramsfile = sys.argv[2]
        except:
            print("call with {} xmlprofile paramsfile".format(sys.argv[0]))
            sys.exit(1)

    if extension(xmlfile) != ".xml":
        print("DSP profile file does not have the extension xml, aborting")
        sys.exit(1)

    if extension(paramsfile) != ".params":
        print("Parameters file does not have the extension params, aborting")
        sys.exit(1)

    if basefilename(xmlfile) != basefilename(paramsfile):
        print('''Warning: the two files do not share the same base name. If you're merging an incorrect
parameter file into an XML profile, this might damage your system!
        ''')

    try:
        pf = SigmastudioParamsFile(paramsfile)
    except IOError as e:
        print("can't read {} ({})".format(paramsfile, e))
        sys.exit(1)

    try:
        params = pf.merge_params_into_xml(xmlfile)
    except IOError as e:
        print("can't read or write {} ({})".format(xmlfile, e))
        sys.exit(1)

    print("added parameters to XML profile:")
    for param in sorted(params):
        print(" ", param)
