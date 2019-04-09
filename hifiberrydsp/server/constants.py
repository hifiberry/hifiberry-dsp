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
# Original SigmaDSP operations
COMMAND_READ = 0x0a
COMMAND_READRESPONSE = 0x0b
COMMAND_WRITE = 0x09

# additional functionalities
COMMAND_EEPROM_FILE = 0xf0
COMMAND_CHECKSUM = 0xf1
COMMAND_CHECKSUM_RESPONSE = 0xf2
COMMAND_WRITE_EEPROM_CONTENT = 0xf3
COMMAND_XML = 0xf4
COMMAND_XML_RESPONSE = 0xf5
COMMAND_STORE_DATA = 0xf6
COMMAND_RESTORE_DATA = 0xf7
COMMAND_GET_META = 0xf8
COMMAND_META_RESPONSE = 0xf9
COMMAND_PROGMEM = 0xfa
COMMAND_PROGMEM_RESPONSE = 0xfb
COMMAND_DATAMEM = 0xfc
COMMAND_DATAMEM_RESPONSE = 0xfd
COMMAND_GPIO = 0xfe
COMMAND_GPIO_RESPONSE = 0xff

GPIO_READ = 0
GPIO_WRITE = 1

GPIO_SELFBOOT = 0
GPIO_RESET = 0

HEADER_SIZE = 14

DEFAULT_PORT = 8086

MAX_READ_SIZE = 1024 * 2

ZEROCONF_TYPE = "_sigmatcp._tcp.local."


class SigmaTCPException(IOError):

    def __init__(self, message):
        super(SigmaTCPException, self).__init__(message)
