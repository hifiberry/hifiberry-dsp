#!/usr/bin/env python3
"""
Tests for the /presets REST endpoints.

    .venv-test/bin/python -m unittest test_speaker_presets_api -v
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

from hifiberrydsp.api import restapi  # noqa: E402
from hifiberrydsp.api import speaker_presets  # noqa: E402
from hifiberrydsp.api.settings_store import SettingsStore  # noqa: E402

CHECKSUM = "8B924F2C2210B903CB4226C12C56EE44"

# Bank base addresses, one per channel, well inside Adau145x memory.
BANKS = {"IIR_A": (0x2000, 80), "IIR_B": (0x2100, 80),
         "IIR_C": (0x2200, 80), "IIR_D": (0x2300, 80)}

METADATA = {
    "programID": "beocreate-universal",
    "profileVersion": "11",
    "sampleRate": "48000",
    "IIR_A": "8192/80", "IIR_B": "8448/80",
    "IIR_C": "8704/80", "IIR_D": "8960/80",
    "channelSelectARegister": "4861", "levelsARegister": "781",
    "delayARegister": "786", "invertARegister": "4867",
    "channelSelectBRegister": "4862", "levelsBRegister": "782",
    "delayBRegister": "787", "invertBRegister": "4868",
    "channelSelectCRegister": "4863", "levelsCRegister": "783",
    "delayCRegister": "788", "invertCRegister": "4869",
    "channelSelectDRegister": "4864", "levelsDRegister": "784",
    "delayDRegister": "789", "invertDRegister": "4870",
    "_attributes": {
        "channelSelectARegister": {"channels": "left,right,mono,side", "multiplier": "1"},
        "channelSelectBRegister": {"channels": "left,right,mono,side", "multiplier": "1"},
        "channelSelectCRegister": {"channels": "left,right,mono,side", "multiplier": "1"},
        "channelSelectDRegister": {"channels": "left,right,mono,side", "multiplier": "1"},
        "delayARegister": {"maxDelay": "2000"},
        "delayBRegister": {"maxDelay": "2000"},
        "delayCRegister": {"maxDelay": "2000"},
        "delayDRegister": {"maxDelay": "2000"},
    },
}


def a_preset(preset_id="beovox-s35", name="Beovox S 35", filters=2,
             role="mono", sample_rate=48000):
    biquad = {"a0": 1.0, "a1": -1.8, "a2": 0.9,
              "b0": 0.9, "b1": -1.6, "b2": 0.8}
    return {
        "schemaVersion": 2, "id": preset_id, "name": name,
        "requiredProfile": "beocreate-universal", "minProfileVersion": 11,
        "sampleRate": sample_rate,
        "channels": {c: {"role": role, "level": 1.0, "delayMs": 0.0,
                         "invert": False, "enabled": True,
                         "filters": [dict(biquad)] * filters}
                     for c in ("a", "b", "c", "d")},
    }


class PresetApiTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.system_dir = os.path.join(self.temp_dir, "system")
        self.user_dir = os.path.join(self.temp_dir, "user")
        os.makedirs(self.system_dir)
        os.makedirs(self.user_dir)

        self.biquad_writes = []     # [address]
        self.memory_writes = []     # [(address, int_value)]

        self._saved = {
            'store': restapi.settings_store,
            'write_biquad': restapi.Adau145x.write_biquad,
            'write_memory': restapi.Adau145x.write_memory,
            'metadata': restapi.get_profile_metadata,
            'resolve_bank': restapi.resolve_bank_from_metadata,
            'checksum': restapi.get_current_program_checksum_sha1,
            'samplerate': restapi.get_or_guess_samplerate,
            'system_dir': speaker_presets.SYSTEM_DIR,
            'user_dir': speaker_presets.USER_DIR,
        }

        speaker_presets.SYSTEM_DIR = self.system_dir
        speaker_presets.USER_DIR = self.user_dir

        self.store_path = os.path.join(self.temp_dir, 'dspsettings.json')
        restapi.settings_store = SettingsStore(store_file=self.store_path)

        restapi.Adau145x.write_biquad = staticmethod(
            lambda address, bq: self.biquad_writes.append(address))
        restapi.Adau145x.write_memory = staticmethod(
            lambda address, data: self.memory_writes.append(
                (address, int.from_bytes(data, 'big'))))
        restapi.get_profile_metadata = lambda: dict(self.metadata)
        restapi.resolve_bank_from_metadata = lambda key: BANKS.get(key)
        restapi.get_current_program_checksum_sha1 = lambda: CHECKSUM
        restapi.get_or_guess_samplerate = lambda: 48000

        self.metadata = dict(METADATA)
        restapi.app.config['TESTING'] = True
        self.client = restapi.app.test_client()

    def tearDown(self):
        restapi.settings_store = self._saved['store']
        restapi.Adau145x.write_biquad = self._saved['write_biquad']
        restapi.Adau145x.write_memory = self._saved['write_memory']
        restapi.get_profile_metadata = self._saved['metadata']
        restapi.resolve_bank_from_metadata = self._saved['resolve_bank']
        restapi.get_current_program_checksum_sha1 = self._saved['checksum']
        restapi.get_or_guess_samplerate = self._saved['samplerate']
        speaker_presets.SYSTEM_DIR = self._saved['system_dir']
        speaker_presets.USER_DIR = self._saved['user_dir']
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def install(self, preset, directory=None):
        directory = directory or self.system_dir
        path = os.path.join(directory, preset["id"] + ".json")
        with open(path, "w") as handle:
            json.dump(preset, handle)


class TestListPresets(PresetApiTestCase):

    def test_lists_installed_presets(self):
        self.install(a_preset())
        payload = self.client.get('/presets').get_json()
        self.assertEqual(len(payload["presets"]), 1)
        entry = payload["presets"][0]
        self.assertEqual(entry["id"], "beovox-s35")
        self.assertEqual(entry["name"], "Beovox S 35")
        self.assertTrue(entry["readOnly"])
        self.assertTrue(entry["compatible"])
        self.assertEqual(entry["filterCounts"], {"a": 2, "b": 2, "c": 2, "d": 2})

    def test_reports_incompatibility_without_failing(self):
        self.install(a_preset(sample_rate=96000))
        entry = self.client.get('/presets').get_json()["presets"][0]
        self.assertFalse(entry["compatible"])
        self.assertIn("96000", entry["incompatibleReason"])

    def test_reports_the_current_selection(self):
        self.install(a_preset())
        restapi.settings_store.store_speaker_preset(CHECKSUM, "beovox-s35")
        self.assertEqual(self.client.get('/presets').get_json()["current"],
                         "beovox-s35")

    def test_no_selection_is_null_not_missing(self):
        self.install(a_preset())
        payload = self.client.get('/presets').get_json()
        self.assertIn("current", payload)
        self.assertIsNone(payload["current"])

    def test_empty_installation_is_an_empty_list(self):
        payload = self.client.get('/presets').get_json()
        self.assertEqual(payload["presets"], [])


class TestGetPreset(PresetApiTestCase):

    def test_returns_the_whole_document(self):
        self.install(a_preset())
        payload = self.client.get('/presets/beovox-s35').get_json()
        self.assertEqual(payload["id"], "beovox-s35")
        self.assertEqual(len(payload["channels"]["a"]["filters"]), 2)
        self.assertTrue(payload["compatible"])

    def test_unknown_preset_is_404(self):
        self.assertEqual(self.client.get('/presets/nosuch').status_code, 404)


if __name__ == "__main__":
    unittest.main()
