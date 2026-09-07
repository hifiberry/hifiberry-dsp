#!/usr/bin/env python3
"""
Tests for recording which speaker preset is applied.

    .venv-test/bin/python -m unittest test_speaker_preset_store -v
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

import hifiberrydsp  # noqa: E402
hifiberrydsp._called_from_test = True

from hifiberrydsp.api.settings_store import SettingsStore  # noqa: E402

CHECKSUM = "8B924F2C2210B903CB4226C12C56EE44"
OTHER_CHECKSUM = "97C9C5A88582888D111259BF70D6D79E"


class TestSpeakerPresetStore(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.store = SettingsStore(
            store_file=os.path.join(self.temp_dir, "dspsettings.json"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_stores_and_reads_back(self):
        self.assertTrue(self.store.store_speaker_preset(CHECKSUM, "beovox-s35"))
        self.assertEqual(self.store.get_speaker_preset(CHECKSUM), "beovox-s35")

    def test_unset_profile_has_no_preset(self):
        self.assertIsNone(self.store.get_speaker_preset(CHECKSUM))

    def test_scoped_per_profile(self):
        """Load a different DSP program and the preset no longer applies."""
        self.store.store_speaker_preset(CHECKSUM, "beovox-s35")
        self.assertIsNone(self.store.get_speaker_preset(OTHER_CHECKSUM))

    def test_replacing_the_preset_replaces_it(self):
        self.store.store_speaker_preset(CHECKSUM, "beovox-s35")
        self.store.store_speaker_preset(CHECKSUM, "beovox-cx100")
        self.assertEqual(self.store.get_speaker_preset(CHECKSUM), "beovox-cx100")

    def test_checksum_case_does_not_create_a_second_entry(self):
        self.store.store_speaker_preset(CHECKSUM.lower(), "beovox-s35")
        self.assertEqual(self.store.get_speaker_preset(CHECKSUM), "beovox-s35")

    def test_does_not_disturb_stored_filters(self):
        self.store.store_filter(CHECKSUM, "IIR_A", 0, {"type": "Volume"})
        self.store.store_speaker_preset(CHECKSUM, "beovox-s35")
        with open(self.store.store_file) as handle:
            data = json.load(handle)
        self.assertIn("IIR_A_0", data[CHECKSUM]["filters"])
        self.assertEqual(data[CHECKSUM]["speakerPreset"]["id"], "beovox-s35")

    def test_clear_removes_the_recorded_preset(self):
        self.store.store_speaker_preset(CHECKSUM, "beovox-s35")
        self.assertTrue(self.store.clear_speaker_preset(CHECKSUM))
        self.assertIsNone(self.store.get_speaker_preset(CHECKSUM))

    def test_clear_of_an_unset_profile_is_not_an_error(self):
        self.assertTrue(self.store.clear_speaker_preset(CHECKSUM))
        self.assertIsNone(self.store.get_speaker_preset(CHECKSUM))

    def test_clear_does_not_disturb_stored_filters(self):
        self.store.store_filter(CHECKSUM, "IIR_A", 0, {"type": "Volume"})
        self.store.store_speaker_preset(CHECKSUM, "beovox-s35")
        self.store.clear_speaker_preset(CHECKSUM)
        with open(self.store.store_file) as handle:
            data = json.load(handle)
        self.assertIn("IIR_A_0", data[CHECKSUM]["filters"])
        self.assertNotIn("speakerPreset", data[CHECKSUM])

    def test_clear_is_scoped_per_profile(self):
        self.store.store_speaker_preset(CHECKSUM, "beovox-s35")
        self.store.store_speaker_preset(OTHER_CHECKSUM, "beovox-cx100")
        self.store.clear_speaker_preset(CHECKSUM)
        self.assertIsNone(self.store.get_speaker_preset(CHECKSUM))
        self.assertEqual(
            self.store.get_speaker_preset(OTHER_CHECKSUM), "beovox-cx100")

    def test_survives_the_duplicate_checksum_merge(self):
        """load_store() merges entries that differ only in case, and used to
        carry only 'filters' and 'memory' across -- silently dropping anything
        else on a store that had both spellings in it."""
        with open(self.store.store_file, "w") as handle:
            json.dump({
                CHECKSUM: {"filters": {}, "memory": {},
                           "speakerPreset": {"id": "beovox-s35",
                                             "timestamp": 100.0}},
                CHECKSUM.lower(): {"filters": {}, "memory": {},
                                   "speakerPreset": {"id": "beovox-cx100",
                                                     "timestamp": 200.0}},
            }, handle)
        self.assertEqual(self.store.get_speaker_preset(CHECKSUM), "beovox-cx100")


if __name__ == "__main__":
    unittest.main()
