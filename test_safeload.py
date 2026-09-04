#!/usr/bin/env python3
"""
Tests for SigmaStudio software safeload on the ADAU145x.

A biquad slot is five consecutive 32-bit cells. Writing them one at a time
while the core is running lets the DSP run a frame with a half-updated
filter, which is audible as a click and, for a crossover, as a moment of
wrong slope. SigmaStudio's software safeload exists for exactly this: the
five words plus a target address and a word count go into a staging window
at the start of DM1, and the core copies them to the target between frames.
The DSP clears the count cell when it has consumed the request, so the
handshake is observable.

The tests drive the real SpiHandler byte framing against a fake SPI slave,
so the wire format and the locking are covered, not just the arithmetic.

Run with:
    python3 -m unittest test_safeload -v
"""

import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

import hifiberrydsp  # noqa: E402
hifiberrydsp._called_from_test = True

from hifiberrydsp.filtering.biquad import Biquad  # noqa: E402
from hifiberrydsp.hardware.adau145x import Adau145x  # noqa: E402
from hifiberrydsp.hardware.spi import SpiHandler  # noqa: E402

SAFELOAD_DATA = 0x6000     # first of five staging cells
SAFELOAD_TARGET = 0x6005   # where the DSP should copy them
SAFELOAD_COUNT = 0x6006    # how many words; cleared by the DSP when done

HIBERNATE = 0xf400         # both read back what was written, verified on
KILLCORE = 0xf403          # a Beocreate 4-Channel Amplifier

SLOT = 0x02AE              # an arbitrary biquad slot in data memory


class FakeSigmaDsp:
    """
    Minimal ADAU145x SPI slave: 32-bit cells, and optionally a core that
    services software safeload requests.

    Deliberately holds no lock of its own -- serialising bus access is the
    driver's job, and a lock here would hide the very race being tested.
    """

    def __init__(self, services_safeload=True, reads_before_service=1):
        self.memory = {}
        self.services_safeload = services_safeload
        # a program that happens to store zero in the cell we poll, without
        # implementing safeload at all
        self.clears_count_without_copying = False
        # raise when the count cell is polled, standing in for an SPI error
        # part-way through the handshake. Keyed on the poll rather than on a
        # read count, which drifts whenever the probe gains a read before it.
        self.raise_on_poll = False
        # how many polls of the count cell happen before the core reacts
        self.reads_before_service = reads_before_service
        self.bursts = []            # (address, [words]) one entry per SPI write
        self.collisions = 0         # requests posted while another was pending
        self._pending = None
        self._polls = 0
        # set KILLCORE the moment a request is posted, standing in for a
        # core that goes down while the probe is in flight
        self.stop_core_on_request = False

    # -- SPI device interface -------------------------------------------

    def xfer(self, request):
        opcode = request[0]
        address = (request[1] << 8) | request[2]
        payload = request[3:]
        if opcode == 0:
            self._write(address, payload)
            return [0] * len(request)
        return self._read(address, len(payload))

    # -- internals -------------------------------------------------------

    @staticmethod
    def _cell_len(address):
        # control registers are two bytes wide, memory cells four
        return 2 if address >= 0xf000 else 4

    def _write(self, address, payload):
        size = self._cell_len(address)
        words = [int.from_bytes(bytes(payload[i:i + size]), "big")
                 for i in range(0, len(payload), size)]
        self.bursts.append((address, list(words)))
        for offset, word in enumerate(words):
            cell = address + offset
            self.memory[cell] = word
            if cell == SAFELOAD_COUNT and word != 0:
                if self._pending is not None:
                    self.collisions += 1
                self._pending = word
                self._polls = 0
                if self.stop_core_on_request:
                    self.memory[KILLCORE] = 1

    def _read(self, address, length):
        size = self._cell_len(address)
        cells = length // size
        polling_the_count = address <= SAFELOAD_COUNT < address + cells
        if self.raise_on_poll and polling_the_count and self._pending is not None:
            raise IOError("SPI transfer failed")
        if self._pending is not None and polling_the_count:
            self._polls += 1
            if self._polls > self.reads_before_service:
                if self.services_safeload:
                    self._service()
                elif self.clears_count_without_copying:
                    self.memory[SAFELOAD_COUNT] = 0
                    self._pending = None
        response = [0, 0, 0]
        for offset in range(cells):
            response.extend(self.memory.get(address + offset, 0).to_bytes(size, "big"))
        return response

    def _service(self):
        target = self.memory.get(SAFELOAD_TARGET, 0)
        for offset in range(self._pending):
            self.memory[target + offset] = self.memory.get(SAFELOAD_DATA + offset, 0)
        self.memory[SAFELOAD_COUNT] = 0
        self._pending = None


class SafeloadTestCase(unittest.TestCase):

    def setUp(self):
        self.dsp = FakeSigmaDsp()
        self._real_spi = SpiHandler.spi
        SpiHandler.spi = self.dsp
        self._real_timeout = Adau145x.SAFELOAD_TIMEOUT
        Adau145x.SAFELOAD_TIMEOUT = 0.05
        Adau145x.reset_safeload_detection()

    def tearDown(self):
        SpiHandler.spi = self._real_spi
        Adau145x.SAFELOAD_TIMEOUT = self._real_timeout
        Adau145x.reset_safeload_detection()

    def staging_bursts(self):
        return [words for address, words in self.dsp.bursts
                if address == SAFELOAD_DATA]

    def slot_contents(self, address=SLOT, length=5):
        return [self.dsp.memory.get(address + i, 0) for i in range(length)]


class TestSafeloadPrimitive(SafeloadTestCase):

    def test_posts_the_seven_staging_cells_as_one_spi_burst(self):
        self.assertTrue(Adau145x.safeload_write(SLOT, [0x11, 0x22, 0x33, 0x44, 0x55]))
        self.assertEqual(self.staging_bursts(),
                         [[0x11, 0x22, 0x33, 0x44, 0x55, SLOT, 5]])

    def test_pads_a_short_request_and_posts_the_real_word_count(self):
        self.assertTrue(Adau145x.safeload_write(SLOT, [0x11, 0x22]))
        self.assertEqual(self.staging_bursts(), [[0x11, 0x22, 0, 0, 0, SLOT, 2]])

    def test_the_dsp_copies_the_words_to_the_target_address(self):
        Adau145x.safeload_write(SLOT, [1, 2, 3, 4, 5])
        self.assertEqual(self.slot_contents(), [1, 2, 3, 4, 5])

    def test_reports_failure_when_the_dsp_never_consumes_the_request(self):
        self.dsp.services_safeload = False
        self.assertFalse(Adau145x.safeload_write(SLOT, [1, 2, 3, 4, 5]))

    def test_rejects_more_words_than_the_staging_window_holds(self):
        with self.assertRaises(ValueError):
            Adau145x.safeload_write(SLOT, [1, 2, 3, 4, 5, 6])

    def test_rejects_an_empty_request(self):
        with self.assertRaises(ValueError):
            Adau145x.safeload_write(SLOT, [])

    def test_rejects_a_word_that_does_not_fit_a_cell(self):
        # int_data() truncates silently, so a caller that got the conversion
        # wrong would otherwise post four plausible bytes
        with self.assertRaises(ValueError):
            Adau145x.safeload_write(SLOT, [1, 2, 3, 4, 2 ** 32 + 1])
        with self.assertRaises(ValueError):
            Adau145x.safeload_write(SLOT, [-1])

    def test_accepts_what_decimal_repr_returns_just_below_zero(self):
        # decimal_repr(-1e-14) is 2**32, which int_data() writes as four zero
        # bytes -- long-standing behaviour, not a caller error
        self.assertTrue(Adau145x.safeload_write(SLOT, [2 ** 32]))


class TestBiquadWrites(SafeloadTestCase):

    def a_biquad(self):
        return Biquad(1.0, -1.5, 0.5, 0.9, 0.1, -0.2, "test filter")

    def another_biquad(self):
        # different coefficients, so a readback of this one cannot be
        # confused with what a previous write left in the slot
        return Biquad(1.0, -1.2, 0.4, 0.8, 0.2, -0.3, "second test filter")

    def expected_slot(self, bq):
        # the slot holds b2, b1, b0, -a2, -a1, as they go on the wire:
        # decimal_repr can return 2**32, which is four zero bytes
        return [int.from_bytes(
                    Adau145x.int_data(Adau145x.decimal_repr(v),
                                      Adau145x.WORD_LENGTH), "big")
                for v in (bq.b2, bq.b1, bq.b0, -bq.a2, -bq.a1)]

    def test_a_filter_update_goes_through_safeload(self):
        Adau145x.write_biquad(SLOT, self.a_biquad())
        self.assertEqual(len(self.staging_bursts()), 1)

    def test_safeload_preserves_the_slot_coefficient_layout(self):
        bq = self.a_biquad()
        Adau145x.write_biquad(SLOT, bq)
        self.assertEqual(self.slot_contents(), self.expected_slot(bq))

    def test_falls_back_to_direct_writes_when_the_profile_has_no_safeload(self):
        self.dsp.services_safeload = False
        bq = self.a_biquad()
        Adau145x.write_biquad(SLOT, bq)
        self.assertEqual(self.slot_contents(), self.expected_slot(bq))

    def test_a_failed_attempt_leaves_the_staging_window_as_it_found_it(self):
        self.dsp.services_safeload = False
        untouched = {SAFELOAD_DATA + i: 0xA0000 + i for i in range(7)}
        self.dsp.memory.update(untouched)

        Adau145x.write_biquad(SLOT, self.a_biquad())

        self.assertEqual({cell: self.dsp.memory[cell] for cell in untouched},
                         untouched)

    def test_stops_probing_the_staging_window_once_it_is_known_unusable(self):
        self.dsp.services_safeload = False
        Adau145x.write_biquad(SLOT, self.a_biquad())
        self.dsp.bursts.clear()

        Adau145x.write_biquad(SLOT + 5, self.a_biquad())

        self.assertEqual(self.staging_bursts(), [])

    def test_does_not_probe_while_the_core_is_stopped(self):
        # a stopped core cannot answer, and there are several windows in
        # which it is down with the bus free: every block memory read stops
        # it to get a consistent picture. A probe there would say nothing
        # about the program, so it must not be attempted or believed.
        Adau145x.kill_dsp()
        self.dsp.bursts.clear()
        bq = self.a_biquad()

        Adau145x.write_biquad(SLOT, bq)

        self.assertEqual(self.staging_bursts(), [])
        self.assertEqual(self.slot_contents(), self.expected_slot(bq))

    def test_probes_once_the_core_is_running_again(self):
        Adau145x.kill_dsp()
        Adau145x.write_biquad(SLOT, self.a_biquad())
        Adau145x.start_dsp()
        self.dsp.bursts.clear()
        bq = self.another_biquad()

        Adau145x.write_biquad(SLOT, bq)

        self.assertEqual(len(self.staging_bursts()), 1)
        self.assertEqual(self.slot_contents(), self.expected_slot(bq))

    def test_a_program_that_only_zeroes_the_count_cell_is_not_mistaken_for_safeload(self):
        # on a program without safeload those seven cells are ordinary DM1
        # data, so the cell being zero proves nothing on its own
        self.dsp.services_safeload = False
        self.dsp.clears_count_without_copying = True
        bq = self.a_biquad()

        Adau145x.write_biquad(SLOT, bq)

        self.assertEqual(self.slot_contents(), self.expected_slot(bq))
        self.dsp.bursts.clear()
        Adau145x.write_biquad(SLOT, bq)
        self.assertEqual(self.staging_bursts(), [])

    def test_a_core_stopped_during_the_probe_is_not_recorded_as_unsupported(self):
        # the core can also be stopped by a TCP client writing the registers
        # directly, so the probe must not read its own timeout as an answer
        self.dsp.services_safeload = False
        self.dsp.stop_core_on_request = True

        Adau145x.write_biquad(SLOT, self.a_biquad())

        self.assertIsNone(Adau145x._safeload_supported)

        self.dsp.stop_core_on_request = False
        self.dsp.services_safeload = True
        Adau145x.start_dsp()
        bq = self.another_biquad()
        Adau145x.write_biquad(SLOT, bq)
        self.assertTrue(Adau145x._safeload_supported)
        self.assertEqual(self.slot_contents(), self.expected_slot(bq))

    def test_does_not_conclude_anything_from_a_slot_that_already_holds_the_words(self):
        # re-applying a filter that is already in the slot proves nothing:
        # the words would be found there whether safeload ran or not
        bq = self.a_biquad()
        for offset, word in enumerate(self.expected_slot(bq)):
            self.dsp.memory[SLOT + offset] = word
        self.dsp.services_safeload = False
        self.dsp.clears_count_without_copying = True

        Adau145x.write_biquad(SLOT, bq)

        self.assertEqual(self.staging_bursts(), [])
        self.assertIsNone(Adau145x._safeload_supported)

    def test_a_coefficient_that_truncates_to_zero_does_not_defeat_detection(self):
        # decimal_repr(-1e-14) is 2**32, which int_data puts on the wire as
        # four zero bytes, so the readback has to compare wire values
        bq = Biquad(1.0, -1.5, 0.5, 0.9, 0.1, -1e-14, "tiny coefficient")
        self.assertEqual(Adau145x.decimal_repr(bq.b2), 2 ** 32)

        Adau145x.write_biquad(SLOT, bq)

        self.assertTrue(Adau145x._safeload_supported)
        self.assertEqual(self.slot_contents(), self.expected_slot(bq))

    def test_a_failure_mid_probe_still_puts_the_staging_window_back(self):
        untouched = {SAFELOAD_DATA + i: 0xA0000 + i for i in range(7)}
        self.dsp.memory.update(untouched)
        # everything up to and including the request succeeds; the poll that
        # would tell us whether it was consumed is what fails
        self.dsp.raise_on_poll = True

        with self.assertRaises(IOError):
            Adau145x.write_biquad(SLOT, self.a_biquad())

        self.dsp.raise_on_poll = False
        # the request really was posted, so the restore had work to do
        self.assertEqual(len(self.staging_bursts()), 2)
        self.assertEqual({cell: self.dsp.memory[cell] for cell in untouched},
                         untouched)


class TestForgettingTheAnswer(SafeloadTestCase):

    def test_takes_the_bus_lock(self):
        # The probe reads and writes the recorded answer under the bus lock,
        # and spans several transactions plus the poll. A reset that does not
        # take the lock can land in the middle of one, after which the probe
        # writes the answer for the program that has just been replaced back
        # over it -- and a stale "supported" is the dangerous way round,
        # since that path neither verifies nor restores the window.
        entries = []
        real_lock = SpiHandler.lock

        class CountingLock:
            def __enter__(self):
                entries.append(1)
                return real_lock.__enter__()

            def __exit__(self, *exc):
                return real_lock.__exit__(*exc)

        SpiHandler.lock = CountingLock()
        try:
            Adau145x.reset_safeload_detection()
        finally:
            SpiHandler.lock = real_lock

        self.assertEqual(len(entries), 1)


class TestConcurrentSafeload(SafeloadTestCase):

    def test_concurrent_requests_do_not_overwrite_each_other(self):
        # two polls per request widens the window in which a second writer
        # could clobber the first one's staging cells
        self.dsp.reads_before_service = 2
        slots = [0x0300 + n * 5 for n in range(8)]

        def write(n):
            Adau145x.safeload_write(slots[n], [n + 1] * 5)

        threads = [threading.Thread(target=write, args=(n,)) for n in range(len(slots))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(self.dsp.collisions, 0)
        for n, slot in enumerate(slots):
            self.assertEqual(self.slot_contents(slot), [n + 1] * 5,
                             "request for slot {} was lost".format(n))


if __name__ == "__main__":
    unittest.main(verbosity=2)
