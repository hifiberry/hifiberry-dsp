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
import tempfile
import os

from threading import Thread

from hifiberrydsp.hardware.adau145x import Adau145x
from hifiberrydsp.filtering.volume import percent2amplification, amplification2percent
from hifiberrydsp import datatools
from hifiberrydsp.hardware.spi import SpiHandler

DIRECTION_TO_DSP = 1
DIRECTION_TO_ALSA = 2
DIRECTION_TWO_WAY = 3

ALSA_STATE_FILE = """
state.sndrpihifiberry {
        control.99 {
                iface MIXER
                name %VOLUME%
                value.0 255
                value.1 255
                comment {
                        access 'read write user'
                        type INTEGER
                        count 2
                        range '0 - 255'
                        tlv '0000000100000008ffffdcc400000023'
                        dbmin -9020
                        dbmax -95
                        dbvalue.0 -95
                        dbvalue.1 -95
                }
        }
}
"""


class AlsaSync(Thread):
    '''
    Synchronises a dummy ALSA mixer control with a volume control 
    register of the DSP.
    '''

    def __init__(self):

        self.alsa_control = None
        self.volume_register = None
        self.dsp = Adau145x
        self.volume_register_length = self.dsp.WORD_LENGTH
        self.finished = False
        self.pollinterval = 0.1
        self.spi = SpiHandler
        self.dspdata = None
        self.dspvol = None
        self.alsavol = None
        self.softvol = None
        self.mixername = None

        Thread.__init__(self)

    def set_volume_register(self, volume_register):
        logging.debug("Using volume register %s", volume_register)
        self.volume_register = volume_register
        # When setting a new Volume register, always update ALSA to
        # state of the DSP
        self.read_dsp_data()
        self.update_alsa(self.dspvol)

    def set_alsa_control(self, alsa_control):
        from alsaaudio import Mixer
        try:
            self.mixer = self.get_dsp_mixer(alsa_control)
            logging.debug("using existing ALSA control %s", alsa_control)
        except:
            try:
                logging.debug(
                    "ALSA control %s does not exist, creating it", alsa_control)

                self.mixer = self.create_mixer(alsa_control)
            except Exception as e:
                logging.error(
                    "can't create ALSA mixer control %s (%s)",
                    alsa_control, e)
            return False

        if self.mixer == None:
            logging.error("ALSA mixer %s not found", alsa_control)
            return False

        self.mixername = alsa_control
        return True

    def update_alsa(self, value, mixer=None):
        if value is None:
            return

        from alsaaudio import MIXER_CHANNEL_ALL
        vol = round(value)

        if mixer is None:
            mixer = self.mixer

        if mixer is not None:
            mixer.setvolume(vol, MIXER_CHANNEL_ALL)

        self.alsavol = vol

    def update_dsp(self, value):
        if value is None:
            return

        # convert percent to multiplier
        logging.debug("Updating DSP to %s",value)
        volume = percent2amplification(value)

        # write multiplier to DSP
        dspdata = datatools.int_data(self.dsp.decimal_repr(volume),
                                     self.volume_register_length)
        self.spi.write(self.volume_register, dspdata)

        self.dspdata = dspdata
        self.dspvol = value
    

    def read_alsa_data(self):
        from alsaaudio import Mixer
        volumes = self.get_dsp_mixer(self.mixername).getvolume()
        channels = 0
        vol = 0
        for i in range(len(volumes)):
            channels += 1
            vol += volumes[i]

        if channels > 0:
            vol = round(vol / channels)
            
        if vol != self.alsavol:
            logging.debug(
                "ALSA volume changed from {}% to {}%".format(self.alsavol, vol))
            self.alsavol = vol
            return True
        else:
            return False

    def read_dsp_data(self):
        if self.volume_register is None:
            self.dspdata = None
            self.dspvol = None
            return False

        dspdata = self.spi.read(
            self.volume_register, self.volume_register_length)

        if dspdata != self.dspdata:

            # Convert to percent and round to full percent
            vol = round(amplification2percent(self.dsp.decimal_val(dspdata)))

            if vol < 0:
                vol = 0
            elif vol > 100:
                vol = 100

            logging.debug(
                "DSP volume changed from {}% to {}%".format(self.dspvol, vol))
            self.dspvol = vol

            self.dspdata = dspdata
            return True
        else:
            return False

    def get_dsp_mixer(self, mixername):
        import alsaaudio
        find_card = True
        i=0
        while(find_card):
            try:
                mixers = alsaaudio.mixers(cardindex=i)
                if [match for match in mixers if mixername in match]:
                    hw_dev = "hw:{0}".format(str(i))
                    return alsaaudio.Mixer(mixername,device=hw_dev)
            except:
                find_card = False
            i+=1
        return None

    def check_sync(self):
        alsa_changed = self.read_alsa_data()
        dsp_changed = self.read_dsp_data()

        # Check if one of the control has changed and update the other
        # one. If both have changed, ALSA takes precedence
        if alsa_changed:
            logging.debug("Updating DSP volume from ALSA")
            self.update_dsp(self.alsavol)
        elif dsp_changed:
            logging.debug("Updating ALSA volume from DSP")
            self.update_alsa(self.dspvol)

    def run(self):
        reg_set = True
        try:
            while not(self.finished):
                if self.mixer is None:
                    logging.error(
                        "ALSA mixer not available, aborting volume synchronisation")
                    break

                if self.volume_register is None:
                    # Volume control register can change when a new program is
                    # uploaded, just go on and try again later
                    if reg_set:
                        logging.error(
                            "ALSA mixer not available, volume register unknown in profile")
                        reg_set = False
                    time.sleep(1)
                    continue
                else:
                    reg_set = True

                self.check_sync()
                time.sleep(self.pollinterval)
        except Exception as e:
            logging.error("ALSA sync crashed: %s", e)

    def finish(self):
        self.finished = True

    @staticmethod
    def create_mixer(name):

        with tempfile.NamedTemporaryFile(mode='w', dir="/tmp", delete=False) as asoundstate:
            content = ALSA_STATE_FILE.replace("%VOLUME%", name)
            logging.debug("asoundstate file %s", content)
            asoundstate.write(content)
            asoundstate.close()
            
        

        command = "/usr/sbin/alsactl -f {} restore".format(
            asoundstate.name)
        logging.debug("runnning %s", command)
        os.system(command)
        
        try:
            from alsaaudio import Mixer, mixers
            logging.info("mixers: ", mixers())
            return Mixer(name)
        except:
            from alsaaudio import cards, ALSAAudioError
            raise ALSAAudioError("Mixer {} not found (cards: {})".format(name, cards()))
