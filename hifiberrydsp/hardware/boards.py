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
import time

GPIO_SELFBOOT = 6
GPIO_RESET = 17
GPIO_MUTE = 27


class Board(object):
    '''
    classdocs
    '''

    def __init__(self, params):
        self.has_selfboot = False
        self.has_reset = False
        self.reset_inverted = False
        self.name = "Generic board"

    def selfboot(self, onoff):
        if not(self.has_selfboot):
            logging.info("%s does not support selfboot control",
                         self.name)
            return

        try:
            import RPi.GPIO as GPIO
        except:
            logging.error(
                "RPi.GPIO not installed, GPIO functions not supported")
            return

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(GPIO_SELFBOOT, GPIO.IN)

        if GPIO.input(GPIO_SELFBOOT) == 1:
            '''
            SELFBOOT jumper is set, do nothing
            '''
            logging.info("Selfboot jumper is set, not toggeling selfboot")

        else:
            GPIO.setup(GPIO_SELFBOOT, GPIO.OUT)
            GPIO.output(GPIO_SELFBOOT, onoff)

        GPIO.cleanup()

    def get_selfboot(self):
        if not(self.has_selfboot):
            logging.info("%s does not support selfboot control",
                         self.name)
            return False

        try:
            import RPi.GPIO as GPIO
        except:
            logging.error(
                "RPi.GPIO not installed, GPIO functions not supported")
            return

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(GPIO_SELFBOOT, GPIO.IN)

        logging.error("get_selfboot")
        logging.error("input: %s", GPIO.input(GPIO_SELFBOOT))

        if GPIO.input(GPIO_SELFBOOT) == 1:
            '''
            SELFBOOT jumper is set, do nothing
            '''
            logging.info("Selfboot jumper is set, not toggling selfboot")
            logging.error("get_selfboot 1")

            selfboot = 1
        else:
            GPIO.setup(GPIO_SELFBOOT, GPIO.OUT)
            selfboot = GPIO.input(GPIO_SELFBOOT)
            logging.error("get_selfboot 2")

        GPIO.cleanup()
        return selfboot

    def reset(self):
        try:
            import RPi.GPIO as GPIO
        except:
            logging.error(
                "RPi.GPIO not installed, GPIO functions not supported")
            return

        if not(self.has_reset):
            logging.info("%s does not support reset control",
                         self.name)
            return False

        resetval = True
        if (self.reset_inverted):
            resetval = not(resetval)

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(GPIO_RESET, GPIO.OUT)
        GPIO.output(GPIO_RESET, resetval)
        time.sleep(0.1)
        GPIO.output(GPIO_RESET, not(resetval))
        GPIO.setup(GPIO_RESET, GPIO.IN)
        GPIO.cleanup()
        return True
