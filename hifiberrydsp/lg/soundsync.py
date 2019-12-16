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
    Implements reverse-engineered LG sound sync to set main volume control
    '''

    def __init__(self):

        self.alsa_control = None
        self.volume_register = None
        self.dsp = Adau145x
        self.volume_register_length = self.dsp.WORD_LENGTH
        self.finished = False
        self.pollinterval = 0.3
        self.spi = SpiHandler
        self.dspdata = None
        self.dspvol = None
        self.lgsoundsyncdetected = False

        Thread.__init__(self)

    def set_registers(self, volume_register, spdif_register):
        logging.info("LG soundsync: using volume at %s and SPDIF active at %s",
                      volume_register, spdif_register)
        self.volume_register = volume_register
        self.spdif_register = spdif_register

    def update_volume(self):

        if self.volume_register is None or self.spdif_register is None:
            return False

        # Read SPDIF status registers
        data = self.spi.read(0xf617, 6)
        if len(data) != 6:
            logging.error("internal error: could not read 6 bytes from SPI")
            return False

        _b1, vol, volid, _b2 = struct.unpack(">BHHB", data)

        if volid != 0x048a:
            return False

        if vol < 0x100f or vol > 0x164f:
            return False

        # Read SPDIF enable register
        data = self.spi.read(self.spdif_register, 4)
        [spdif_active] = struct.unpack(">l", data)
        if spdif_active == 0:
            return False

        volpercent = (vol - 0x100f) / 16
        if volpercent < 0 or volpercent > 100:
            logging.error("internal error, got volume = %s, "
                          "but should be in 0-100 range", volpercent)
        # convert percent to multiplier
        volume = percent2amplification(volpercent)

        # write multiplier to DSP
        dspdata = datatools.int_data(self.dsp.decimal_repr(volume),
                                     self.volume_register_length)
        self.spi.write(self.volume_register, dspdata)
        return True

    def run(self):
        try:
            while not(self.finished):

                sync = self.lgsoundsyncdetected

                if self.update_volume():
                    self.lgsoundsyncdetected = True
                else:
                    self.lgsoundsyncdetected = False

                if sync != self.lgsoundsyncdetected:
                    if self.lgsoundsyncdetected:
                        logging.info("LG SoundSync started")
                    else:
                        logging.info("LG SoundSync stopped")

                if self.lgsoundsyncdetected:
                    time.sleep(self.pollinterval)
                else:
                    time.sleep(self.pollinterval * 10)

        except Exception as e:
            logging.error("ALSA sync crashed: %s", e)

    def finish(self):
        self.finished = True

