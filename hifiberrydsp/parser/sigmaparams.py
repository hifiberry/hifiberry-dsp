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


from hifiberrydsp.parser.xmlprofile import ATTRIBUTE_BALANCE, \
    ATTRIBUTE_FIR_FILTER_LEFT, ATTRIBUTE_FIR_FILTER_RIGHT, \
    ATTRIBUTE_IIR_FILTER_LEFT, ATTRIBUTE_IIR_FILTER_RIGHT, \
    ATTRIBUTE_VOL_CTL, ATTRIBUTE_VOL_LIMIT, \
    ATTRIBUTE_IIR_TEMPLATE, ATTRIBUTE_MUTE_REG, \
    ATTRIBUTE_CHANNEL_SELECT, \
    XmlProfile


PARAMETER_MAPPING = {
    "balance": ATTRIBUTE_BALANCE,
    "volume.target": ATTRIBUTE_VOL_CTL,
    "volumelimit.target": ATTRIBUTE_VOL_LIMIT,
    "channelselect": ATTRIBUTE_CHANNEL_SELECT,
    "mute": ATTRIBUTE_MUTE_REG,
    "fir_l": ATTRIBUTE_FIR_FILTER_LEFT,
    "fir_r": ATTRIBUTE_FIR_FILTER_RIGHT,
    "iir_l": ATTRIBUTE_IIR_FILTER_LEFT,
    "iir_r": ATTRIBUTE_IIR_FILTER_RIGHT,
}

for lr in ["L", "R"]:
    for channel in range(1, 5):
        name = "iir_{}{}".format(lr.lower(), channel)
        attribute = ATTRIBUTE_IIR_TEMPLATE.replace(
            "%LR%", lr).replace("%CHANNEL%", str(channel))
        PARAMETER_MAPPING[name] = attribute


class SigmastudioParamsFile():

    def __init__(self, filename):
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
        xml = XmlProfile(xmlfile)
        xml.update_metadata(self.param_list())
        xml.write_xml(xmlfile)


def main():
    print("*")
    pf = SigmastudioParamsFile(
        "/Users/matuschd/devel/python/hifiberry-dsp/sample_files/xml/4way-iir.params")
    print(pf.param_list())
    pf.merge_params_into_xml(
        "/Users/matuschd/devel/python/hifiberry-dsp/sample_files/xml/4way-iir.xml")


main()
