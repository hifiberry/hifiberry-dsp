#!/usr/bin/env python
'''
Copyright (c) 2020 Modul 9/HiFiBerry

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

#!/usr/bin/env python

import logging
import signal
import time
import sys
from threading import Thread

import alsaaudio

from hifiberrydsp.hardware.adau145x import Adau145x
from hifiberrydsp.client.sigmatcp import SigmaTCPClient

stopped = False
device="default"
waitseconds=0

PERIODSIZE=1024
BYTESPERSAMPLE=8

pcm=None
sigmatcp=None

def silenceloop():
    global stopped
    global pcm
    
    try:
        pcm=alsaaudio.PCM(alsaaudio.PCM_PLAYBACK, device=device)
    except:
        logging.debug("sound card probably in use, doing nothing")
        return
    
    logging.debug("SPDIF lock, playing silence")
    
    while spdifactive() and not(stopped):
        time.sleep(1)
        logging.debug("not stopped")
        
    pcm=None
    

def spdifactive():
    inputlock = int.from_bytes(sigmatcp.read_memory(0xf600, 2),byteorder='big') & 0x0001
    return inputlock > 0 
    
def stop_playback(_signalNumber, _frame):
    global stopped
    
    logging.info("received USR1, stopping music playback")
    stopped = True
    # Re-activate in 15 seconds
    t = Thread(target=activate_again, args=(15,))
    t.start()
    
    
def activate_again(seconds):
    time.sleep(seconds)
    global stopped
    stopped=False



def main():
    global sigmatcp
    
    if len(sys.argv) > 1:
        if "-v" in sys.argv:
            logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                                level=logging.DEBUG,
                                force=True)
    else:
        logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                            level=logging.INFO,
                            force=True)
    
    signal.signal(signal.SIGUSR1, stop_playback)
    
    sigmatcp = SigmaTCPClient(Adau145x(),"127.0.0.1")

    while True:
        time.sleep(1)
        
        if stopped:
            logging.debug("stopped")
            continue
        
        if (spdifactive()):
            silenceloop()
        else:
            logging.debug("no SPDIF lock, sleeping")
        
if __name__ == '__main__':
    main()