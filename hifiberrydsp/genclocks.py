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
import asyncio
import argparse
import logging
import signal
import os
from collections import namedtuple

import alsaaudio

from hifiberrydsp.hardware.adau145x import Adau145x
from hifiberrydsp.client.sigmatcp import SigmaTCPClient

SERVICE_NAME = 'spdifclockgen'
logger = logging.getLogger(SERVICE_NAME)


class LoopStateMachine:
    FutureTask = namedtuple('FutureTask', ['delay', 'coro'])
    def __init__(self, sigma_tcp_client, playback_pcm='default'):
        self.client = sigma_tcp_client
        self.task_queue = asyncio.Queue()
        self.playback_pcm = playback_pcm
        self.loop = None

    @property
    def active(self):
        inputlock = int.from_bytes(
            self.client.read_memory(0xf600, 2),
            byteorder='big') & 0x0001
        logger.debug('inputlock value: %d', inputlock)
        return inputlock > 0

    async def run(self):
        self.loop = asyncio.get_running_loop()
        await self.task_queue.put(
            self.FutureTask(0, self.idle))
        
        while True:
            todo = await self.task_queue.get()
            logger.info('Dispatching task \'%s\' from queue in %.0f seconds',
                         todo.coro.__name__, todo.delay)
            await self._gather()
            self.loop.call_later(todo.delay, asyncio.create_task, todo.coro())

    async def idle(self):
        while not self.active:
            await asyncio.sleep(1)
        await self.task_queue.put(self.FutureTask(0, self.play))

    async def play(self):
        try:
            # Resource will be collected implicitly when exiting this method
            _ = alsaaudio.PCM(alsaaudio.PCM_PLAYBACK, device=self.playback_pcm)
        except alsaaudio.ALSAAudioError as e:
            logger.warning('Error opening playback device: %s', e)
            await self.task_queue.put(self.FutureTask(5, self.idle))
            return

        while self.active:
            await asyncio.sleep(1)

        await self.task_queue.put(self.FutureTask(0, self.idle))

    async def hybernate(self, sig):
        logger.info('Received pause signal %s', sig.name)
        await self.task_queue.put(self.FutureTask(15, self.idle))

    async def _gather(self):
        tasks = [t for t in asyncio.all_tasks() if t is not
                 asyncio.current_task()]
        [task.cancel() for task in tasks]

        logger.info('Cancelling %d outstanding tasks', len(tasks))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def shutdown(self, sig):
        logger.info('Received exit signal %s.', sig.name)
        await self._gather()
        self.loop.stop()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
            '-p', '--playback', default='default',
            help=argparse.SUPPRESS) # Hide this option from normal users
    parser.add_argument(
            '-v', '--verbose', action='store_true',
            help='''Increase logging verbosity to DEBUG''')

    return parser.parse_args()


def logger_config(verbose):
    logging.basicConfig()
    logging.captureWarnings(True)
    logging_level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(logging_level)


def main():
    os.nice(19)
    args = parse_args()
    logger_config(args.verbose)
    logger.info('%s started with PID %d', SERVICE_NAME, os.getpid())
    loop = asyncio.get_event_loop()

    shutdown_signals = (signal.SIGTERM, signal.SIGINT)
    pause_signals = (signal.SIGHUP, signal.SIGUSR1)

    loopsm = LoopStateMachine(SigmaTCPClient(Adau145x(), '127.0.0.1'), args.playback)
    try:
        for s in shutdown_signals:
            loop.add_signal_handler(
                s, lambda s=s: 
                    asyncio.create_task(loopsm.shutdown(s)))

        for s in pause_signals:
            loop.add_signal_handler(
                s, lambda s=s:
                    asyncio.create_task(loopsm.hybernate(s)))

        loop.create_task(loopsm.run())
        loop.run_forever()

    finally:
        loop.close()
        logger.info('Sucessfully shutdown %s', SERVICE_NAME)


if __name__ == '__main__':
    main()
