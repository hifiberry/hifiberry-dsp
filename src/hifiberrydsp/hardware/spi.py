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
import logging
import hifiberrydsp

def init_spi():        
    if not hifiberrydsp._called_from_test:
        # only open the device when not running tests
        import spidev        
        spi = spidev.SpiDev()        
        spi.open(0, 0)
        spi.bits_per_word = 8
        spi.max_speed_hz = 1000000
        spi.mode = 0
        logging.debug("spi initialized %s", spi)
    else:
        spi = None
        logging.debug("spi not initialized since running tests")
    return spi


class SpiHandler():
    '''
    Implements access to the SPI bus. Can be used by multiple threads.

    We assume that the SPI library is thread-safe and do not use 
    additional locking here.

    Data is passed in bytearrays, not string or lists
    '''

    spi = init_spi()

    @staticmethod
    def read(addr, length, debug=False):
        spi_request = []
        a0 = addr & 0xff
        a1 = (addr >> 8) & 0xff

        spi_request.append(1)
        spi_request.append(a1)
        spi_request.append(a0)

        for _i in range(0, length):
            spi_request.append(0)

        spi_response = SpiHandler.spi.xfer(spi_request)  # SPI read
        if debug:
            logging.debug("spi read %s bytes from %s", len(spi_request), addr)
        return bytearray(spi_response[3:])

    @staticmethod
    def write(addr, data, debug=False):
        a0 = addr & 0xff
        a1 = (addr >> 8) & 0xff

        spi_request = []
        spi_request.append(0)
        spi_request.append(a1)
        spi_request.append(a0)
        for d in data:
            spi_request.append(d)

        if len(spi_request) < 4096:
            SpiHandler.spi.xfer(spi_request)
            if debug:
                logging.debug("spi write %s bytes",  len(spi_request) - 3)
        else:
            finished = False
            while not finished:
                if len(spi_request) < 4096:
                    SpiHandler.spi.xfer(spi_request)
                    if debug:
                        logging.debug("spi write %s bytes",
                                      len(spi_request) - 3)
                    finished = True
                else:
                    short_request = spi_request[:4003]
                    SpiHandler.spi.xfer(short_request)
                    if debug:
                        logging.debug("spi write %s bytes",
                                      len(short_request) - 3)

                    # skip forward 1000 cells
                    addr = addr + 1000  # each memory cell is 4 bytes long
                    a0 = addr & 0xff
                    a1 = (addr >> 8) & 0xff
                    new_request = []
                    new_request.append(0)
                    new_request.append(a1)
                    new_request.append(a0)
                    new_request.extend(spi_request[4003:])

                    spi_request = new_request

        return data
