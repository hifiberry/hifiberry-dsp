#!/usr/bin/env python3
"""
Tests for POST /filters/bank -- the single-request bank write added for
hifiberry-os#626.

Loading a 16-band Room EQ correction used to be 136 sequential POST /biquad
round-trips per channel (the webui rewrote the whole bank on every added
filter), each of which left the not-yet-reached slots holding a transparent
pass-through. Any interruption mid-sequence left the bank half applied.

Requires the test venv:
    python3 -m venv .venv-test
    .venv-test/bin/pip install flask waitress requests xmltodict
    .venv-test/bin/python -m unittest test_filters_bank_api -v

These commands work from a clean checkout: hifiberrydsp._called_from_test is
set below, before `restapi` (and transitively hifiberrydsp.hardware.spi) is
imported, so SpiHandler's class-body init_spi() skips `import spidev` and
never tries to open a real SPI device. Without that flag this import fails
with `ModuleNotFoundError: No module named 'spidev'` even though spidev is
never actually used by these tests.
"""

import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

import hifiberrydsp  # noqa: E402
hifiberrydsp._called_from_test = True

from hifiberrydsp.api import restapi  # noqa: E402
from hifiberrydsp.api.settings_store import SettingsStore  # noqa: E402

BASE_ADDRESS = 0x2000          # inside Adau145x MIN_MEMORY..MAX_MEMORY (0x0000..0xdfff)
BANK_KEY = "customFilterRegisterBankLeft"
CHECKSUM = "8B924F2C2210B903CB4226C12C56EE44"


def a_filter(freq):
    return {"type": "PeakingEq", "f": freq, "db": -3.0, "q": 1.0}


TRANSPARENT = {"a0": 1.0, "a1": 0.0, "a2": 0.0, "b0": 1.0, "b1": 0.0, "b2": 0.0}


class BankApiTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.temp_dir, 'dspsettings.json')

        self.writes = []                     # [(address, thread_name)]
        self.write_delay = 0.0
        self.fail_at_offset = None
        self.first_bank_write = threading.Event()

        self._saved = {
            'store': restapi.settings_store,
            'write_biquad': restapi.Adau145x.write_biquad,
            'resolve': restapi.resolve_address_from_metadata,
            'resolve_bank': getattr(restapi, 'resolve_bank_from_metadata', None),
            'checksum': restapi.get_current_program_checksum_sha1,
            'samplerate': restapi.get_or_guess_samplerate,
        }

        restapi.settings_store = SettingsStore(store_file=self.store_path)

        def fake_write_biquad(address, biquad):
            if self.fail_at_offset is not None and address == BASE_ADDRESS + self.fail_at_offset * 5:
                raise IOError("simulated SPI failure")
            if self.write_delay:
                time.sleep(self.write_delay)
            self.writes.append((address, threading.current_thread().name))
            if threading.current_thread().name == "bank" and not self.first_bank_write.is_set():
                self.first_bank_write.set()

        restapi.Adau145x.write_biquad = staticmethod(fake_write_biquad)
        restapi.resolve_address_from_metadata = lambda key: BASE_ADDRESS if key == BANK_KEY else None
        restapi.resolve_bank_from_metadata = lambda key: (BASE_ADDRESS, 80) if key == BANK_KEY else None
        restapi.get_current_program_checksum_sha1 = lambda: CHECKSUM
        restapi.get_or_guess_samplerate = lambda: 48000

        restapi.app.config['TESTING'] = True
        self.client = restapi.app.test_client()

    def tearDown(self):
        restapi.settings_store = self._saved['store']
        restapi.Adau145x.write_biquad = self._saved['write_biquad']
        restapi.resolve_address_from_metadata = self._saved['resolve']
        restapi.resolve_bank_from_metadata = self._saved['resolve_bank']
        restapi.get_current_program_checksum_sha1 = self._saved['checksum']
        restapi.get_or_guess_samplerate = self._saved['samplerate']
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def bank_body(self, count=16, real=16):
        return {
            "address": BANK_KEY,
            "sampleRate": 48000,
            "filters": [
                {"offset": i, "filter": a_filter(100 * (i + 1)) if i < real else TRANSPARENT}
                for i in range(count)
            ],
        }


class TestBankWrite(BankApiTestCase):

    def test_writes_every_slot_in_offset_order(self):
        response = self.client.post('/filters/bank', json=self.bank_body())

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["written"], 16)
        self.assertEqual(payload["total"], 16)

        self.assertEqual([addr for addr, _ in self.writes],
                         [BASE_ADDRESS + i * 5 for i in range(16)])

    def test_persists_every_slot_to_the_settings_store(self):
        self.client.post('/filters/bank', json=self.bank_body())

        with open(self.store_path) as f:
            data = json.load(f)

        stored = data[CHECKSUM]["filters"]
        for i in range(16):
            self.assertIn(f"{BANK_KEY}_{i}", stored, f"offset {i} was not persisted")

    def test_one_request_replaces_the_old_136_round_trips(self):
        """The whole point: a 16-band correction is one HTTP call."""
        response = self.client.post('/filters/bank', json=self.bank_body())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.writes), 16)

    def test_partial_failure_is_reported_not_swallowed(self):
        self.fail_at_offset = 7
        response = self.client.post('/filters/bank', json=self.bank_body())

        self.assertEqual(response.status_code, 207)
        payload = response.get_json()
        self.assertEqual(payload["status"], "partial")
        self.assertEqual(payload["written"], 15)
        self.assertTrue(any("offset 7" in e for e in payload["errors"]))

    def test_missing_address_is_rejected(self):
        response = self.client.post('/filters/bank', json={"filters": []})
        self.assertEqual(response.status_code, 400)

    def test_filters_must_be_a_list(self):
        response = self.client.post('/filters/bank',
                                    json={"address": BANK_KEY, "filters": {"offset": 0}})
        self.assertEqual(response.status_code, 400)

    def test_unknown_address_is_404(self):
        response = self.client.post('/filters/bank',
                                    json={"address": "nosuchbank", "filters": []})
        self.assertEqual(response.status_code, 404)

    def test_duplicate_offsets_are_rejected_not_silently_collapsed(self):
        body = self.bank_body()
        body["filters"][3]["offset"] = 0          # two entries now claim slot 0
        response = self.client.post('/filters/bank', json=body)

        self.assertEqual(response.status_code, 400)
        self.assertIn("duplicate", response.get_json()["error"].lower())
        self.assertEqual(self.writes, [], "a rejected request must write nothing")

    def test_negative_offset_is_rejected(self):
        body = self.bank_body()
        body["filters"][2]["offset"] = -1
        response = self.client.post('/filters/bank', json=body)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.writes, [])

    def test_offset_past_the_end_of_the_bank_is_rejected(self):
        body = self.bank_body()
        body["filters"][2]["offset"] = 16          # bank holds 16 slots, 0..15
        response = self.client.post('/filters/bank', json=body)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.writes, [])

    def test_a_failed_store_write_is_reported_not_swallowed(self):
        def failing_store_filter(*args, **kwargs):
            return False

        restapi.settings_store.store_filter = failing_store_filter
        response = self.client.post('/filters/bank', json=self.bank_body())

        self.assertEqual(response.status_code, 207)
        payload = response.get_json()
        self.assertEqual(payload["status"], "partial")
        self.assertEqual(payload["written"], 0)
        self.assertTrue(any("persist" in e for e in payload["errors"]))


class TestWriteSerialisation(BankApiTestCase):

    def test_a_concurrent_biquad_write_cannot_interleave_into_a_bank_write(self):
        """
        Two clients writing at the same time must not interleave their DSP
        writes -- that is what left one channel half-corrected.
        """
        self.write_delay = 0.002
        other_client = restapi.app.test_client()
        results = {}

        def post_bank():
            results['bank'] = self.client.post('/filters/bank', json=self.bank_body()).status_code

        def post_single():
            # Land in the middle of the bank write: wait for the bank thread's
            # first register write rather than sleeping a fixed guess, so this
            # cannot race ahead of (or land after) the bank write on a loaded
            # machine.
            self.first_bank_write.wait(timeout=5)
            results['single'] = other_client.post('/biquad', json={
                "address": BANK_KEY, "offset": 3, "sampleRate": 48000,
                "filter": a_filter(999)}).status_code

        threads = [threading.Thread(target=post_bank, name="bank"),
                   threading.Thread(target=post_single, name="single")]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(results['bank'], 200)
        self.assertEqual(results['single'], 200)

        # If the single write never actually landed (e.g. the handshake wait
        # timed out) this would silently pass with a shorter, still-contiguous
        # list -- pin the total count so that failure mode cannot pass.
        self.assertEqual(len(self.writes), 17)

        bank_positions = [i for i, (_, name) in enumerate(self.writes) if name == "bank"]
        self.assertEqual(len(bank_positions), 16)
        self.assertEqual(bank_positions, list(range(min(bank_positions), min(bank_positions) + 16)),
                         f"bank write was interleaved: {self.writes}")


if __name__ == '__main__':
    unittest.main()
