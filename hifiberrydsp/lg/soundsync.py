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

from hifiberrydsp.hardware.adau145x import Adau145x
from hifiberrydsp.filtering.volume import percent2amplification
from hifiberrydsp import datatools
from hifiberrydsp.hardware.spi import SpiHandler

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
        if self.volume_register is None or self.spdif_active_register is None:
            return False

        if not self.is_spdif_active():
            return False

        volume = self.try_read_volume()

        if volume is None:
            return False

        self.write_volume(volume)

        return True

    def is_spdif_active(self):
        data = self.spi.read(self.spdif_active_register, 4)
        [spdif_active] = struct.unpack(">l", data)
        return spdif_active != 0

    def try_read_volume(self):
        spdif_status_register = 0xf617
        return self.parse_volume_from_status(self.spi.read(spdif_status_register, 6))

    @staticmethod
    def parse_volume_from_status(data):
        _b1, vol, volid, _b2 = struct.unpack(">BHHB", data)

        if volid != 0x048a:
            return None

        if not 0x100f <= vol <= 0x164f:
            return None

        return (vol - 0x100f) / 16

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
