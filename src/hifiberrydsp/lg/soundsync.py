'''
Copyright (c) 2018 Modul 9/HiFiBerry
              2020 Christoffer Sawicki

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

import time
import logging
import struct

from threading import Thread

from hifiberrydsp.filtering.volume import percent2amplification
from hifiberrydsp import datatools

try:
    from hifiberrydsp.hardware.adau145x import Adau145x
    from hifiberrydsp.hardware.spi import SpiHandler
    # depends on spidev and is not required to run tests
except:
    pass

class SoundSync(Thread):
    '''
    Implements reverse-engineered LG Sound Sync to set main volume control
    '''

    def __init__(self):
        self.dsp = Adau145x
        self.spi = SpiHandler

        self.finished = False
        self.detected = False

        self.volume_register = None
        self.spdif_active_register = None

        Thread.__init__(self)

    def set_registers(self, volume_register, spdif_active_register):
        logging.info("LG Sound Sync: Using volume register at %s and SPDIF active register at %s",
                     volume_register, spdif_active_register)
        self.volume_register = volume_register
        self.spdif_active_register = spdif_active_register

    def update_volume(self):
        if self.volume_register is None:
            return False

        if (self.spdif_active_register is not None) and (not self.is_spdif_active()):
            return False

        volume = self.try_read_volume()

        if volume is None:
            return False

        self.write_volume(volume)

        return True

    def is_spdif_active(self):
        if self.spdif_active_register is None:
            return True
        
        data = self.spi.read(self.spdif_active_register, 4)
        [spdif_active] = struct.unpack(">l", data)
        return spdif_active != 0

    def try_read_volume(self):
        spdif_status_register = 0xf617
        return self.parse_volume_from_status(self.spi.read(spdif_status_register, 5))

    # Volume    ~~~~~
    #      0: 00f048a$  This is what the SPDIF status registers look like with different volume levels set.
    #      1: 01f048a$
    #      2: 02f048a$  We check for f048a (SIGNATURE_VALUE) to see if LG Sound Sync is enabled.
    #      3: 03f048a$
    #    100: 64f048a$  The byte to the left is the volume we want to extract.
    #         ~~        The first bit is set to 1 when muted.
    SIGNATURE_MASK = 0xfffff
    SIGNATURE_VALUE = 0xf048a
    SHIFT = 5 * 4
    MUTE_MASK = 0b10000000
    VOLUME_MASK = 0b01111111

    @staticmethod
    def parse_volume_from_status(data):
        bits = int.from_bytes(data, byteorder="big")

        if bits & SoundSync.SIGNATURE_MASK != SoundSync.SIGNATURE_VALUE:
            return None

        if bits >> SoundSync.SHIFT & SoundSync.MUTE_MASK:
            return 0

        return bits >> SoundSync.SHIFT & SoundSync.VOLUME_MASK

    def write_volume(self, volume):
        assert 0 <= volume <= 100
        dspdata = datatools.int_data(self.dsp.decimal_repr(percent2amplification(volume)),
                                     self.dsp.WORD_LENGTH)
        self.spi.write(self.volume_register, dspdata)

    POLL_INTERVAL = 0.3

    def run(self):
        try:
            while not self.finished:
                previously_detected = self.detected

                self.detected = self.update_volume()

                if not previously_detected and self.detected:
                    logging.info("LG Sound Sync started")
                elif previously_detected and not self.detected:
                    logging.info("LG Sound Sync stopped")

                if self.detected:
                    time.sleep(self.POLL_INTERVAL)
                else:
                    time.sleep(self.POLL_INTERVAL * 10)
        except Exception:
            logging.exception("LG Sound Sync crashed")

    def finish(self):
        self.finished = True
