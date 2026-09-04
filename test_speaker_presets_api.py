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

    def test_malformed_preset_file_is_500_with_a_message(self):
        with open(os.path.join(self.system_dir, "broken.json"), "w") as handle:
            handle.write("{not json")
        response = self.client.get('/presets/broken')
        self.assertEqual(response.status_code, 500)
        self.assertIn("error", response.get_json())


class TestApplyPreset(PresetApiTestCase):

    def test_writes_every_slot_of_every_bank(self):
        """A 16-slot bank is written whole -- the preset's filters, then
        transparent biquads -- so no slot keeps a filter from the preset that
        was applied before this one."""
        self.install(a_preset(filters=2))

        response = self.client.post('/presets/beovox-s35/apply')

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["banksWritten"], 4)
        self.assertEqual(payload["filtersWritten"], 64)

        expected = []
        for key in ("IIR_A", "IIR_B", "IIR_C", "IIR_D"):
            base, _ = BANKS[key]
            expected.extend(base + i * 5 for i in range(16))
        self.assertEqual(self.biquad_writes, expected)

    def test_persists_the_filters(self):
        self.install(a_preset(filters=2))
        self.client.post('/presets/beovox-s35/apply')

        with open(self.store_path) as handle:
            stored = json.load(handle)[CHECKSUM]["filters"]
        self.assertIn("IIR_A_0", stored)
        self.assertIn("IIR_D_15", stored)

    def test_writes_the_channel_registers(self):
        self.install(a_preset(role="mono"))
        response = self.client.post('/presets/beovox-s35/apply')

        self.assertEqual(response.get_json()["registersWritten"], 16)
        addresses = [address for address, _ in self.memory_writes]
        self.assertEqual(addresses[:4], [4861, 781, 786, 4867])

    def test_role_reaches_the_register_as_the_profiles_own_index(self):
        self.install(a_preset(role="mono"))
        self.client.post('/presets/beovox-s35/apply')
        self.assertEqual(
            [value for address, value in self.memory_writes if address == 4861],
            [2])

    def test_unity_level_is_written_as_fixed_point_not_a_raw_word(self):
        """An int 1 would be memory word 1 -- effectively silence. A level
        must reach decimal_repr()."""
        self.install(a_preset())
        self.client.post('/presets/beovox-s35/apply')
        level = [value for address, value in self.memory_writes if address == 781][0]
        self.assertEqual(level, restapi.Adau145x.decimal_repr(1.0))
        self.assertNotEqual(level, 1)

    def test_records_the_selection(self):
        self.install(a_preset())
        self.client.post('/presets/beovox-s35/apply')
        self.assertEqual(
            restapi.settings_store.get_speaker_preset(CHECKSUM), "beovox-s35")

    def test_unknown_preset_is_404(self):
        self.assertEqual(
            self.client.post('/presets/nosuch/apply').status_code, 404)

    def test_incompatible_preset_is_409_and_writes_nothing(self):
        self.install(a_preset(sample_rate=96000))
        response = self.client.post('/presets/beovox-s35/apply')
        self.assertEqual(response.status_code, 409)
        self.assertIn("96000", response.get_json()["incompatibleReason"])
        self.assertEqual(self.biquad_writes, [])
        self.assertEqual(self.memory_writes, [])

    def test_wrong_profile_is_409(self):
        self.metadata["programID"] = "dacdsp"
        self.install(a_preset())
        response = self.client.post('/presets/beovox-s35/apply')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.biquad_writes, [])

    def test_no_checksum_is_503_and_writes_nothing(self):
        """Without a checksum the writes cannot be recorded, so they would be
        lost at the next profile load behind a 200."""
        self.install(a_preset())
        restapi.get_current_program_checksum_sha1 = lambda: None
        response = self.client.post('/presets/beovox-s35/apply')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.biquad_writes, [])

    def test_a_failed_write_reports_what_was_written(self):
        self.install(a_preset())

        def failing_write(address, bq):
            self.biquad_writes.append(address)
            if len(self.biquad_writes) > 20:
                raise IOError("simulated SPI failure")

        restapi.Adau145x.write_biquad = staticmethod(failing_write)

        response = self.client.post('/presets/beovox-s35/apply')
        self.assertEqual(response.status_code, 500)
        payload = response.get_json()
        self.assertEqual(payload["status"], "partial")
        self.assertEqual(payload["banksWritten"], 1)
        self.assertIn("simulated SPI failure", payload["error"])

    def test_a_user_preset_can_be_applied(self):
        self.install(a_preset(preset_id="mine", name="Mine"), self.user_dir)
        self.assertEqual(
            self.client.post('/presets/mine/apply').status_code, 200)


if __name__ == "__main__":
    unittest.main()
