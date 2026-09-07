#!/usr/bin/env python3
"""
Tests for speaker preset discovery, validation and compatibility.

    .venv-test/bin/python -m unittest test_speaker_presets -v
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

from hifiberrydsp.api import speaker_presets  # noqa: E402


def a_channel(filters=0, role="mono", level=1.0, delay_ms=0.0,
              invert=False, enabled=True):
    return {
        "role": role, "level": level, "delayMs": delay_ms,
        "invert": invert, "enabled": enabled,
        "filters": [{"a0": 1.0, "a1": -1.8, "a2": 0.9,
                     "b0": 0.9, "b1": -1.6, "b2": 0.8}] * filters,
    }


def a_preset(preset_id="test-speaker", filters=2, **channel_kwargs):
    return {
        "schemaVersion": 2, "id": preset_id, "name": "Test Speaker",
        "requiredProfile": "beocreate-universal", "minProfileVersion": 11,
        "sampleRate": 48000,
        "channels": {c: a_channel(filters, **channel_kwargs)
                     for c in ("a", "b", "c", "d")},
    }


METADATA = {
    "programID": "beocreate-universal",
    "profileVersion": "11",
    "sampleRate": "48000",
    "IIR_A": "691/80", "IIR_B": "611/80",
    "IIR_C": "531/80", "IIR_D": "451/80",
    "channelSelectARegister": "4861", "levelsARegister": "781",
    "delayARegister": "786", "invertARegister": "4867",
    "_attributes": {
        "channelSelectARegister": {"channels": "left,right,mono,side",
                                   "multiplier": "1"},
        "delayARegister": {"maxDelay": "2000"},
    },
}


class PresetDirTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.system_dir = os.path.join(self.temp_dir, "system")
        self.user_dir = os.path.join(self.temp_dir, "user")
        os.makedirs(self.system_dir)
        os.makedirs(self.user_dir)
        self._saved = (speaker_presets.SYSTEM_DIR, speaker_presets.USER_DIR)
        speaker_presets.SYSTEM_DIR = self.system_dir
        speaker_presets.USER_DIR = self.user_dir

    def tearDown(self):
        speaker_presets.SYSTEM_DIR, speaker_presets.USER_DIR = self._saved
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def write(self, directory, preset_id, preset):
        with open(os.path.join(directory, preset_id + ".json"), "w") as handle:
            json.dump(preset, handle)


class TestDiscovery(PresetDirTestCase):

    def test_lists_system_presets_as_read_only(self):
        self.write(self.system_dir, "beovox-s35", a_preset("beovox-s35"))
        presets = speaker_presets.list_presets()
        self.assertIn("beovox-s35", presets)
        _, read_only = presets["beovox-s35"]
        self.assertTrue(read_only)

    def test_lists_user_presets_as_writable(self):
        self.write(self.user_dir, "mine", a_preset("mine"))
        _, read_only = speaker_presets.list_presets()["mine"]
        self.assertFalse(read_only)

    def test_a_user_preset_shadows_the_system_one(self):
        self.write(self.system_dir, "beovox-s35", a_preset("beovox-s35"))
        mine = a_preset("beovox-s35")
        mine["name"] = "My S 35"
        self.write(self.user_dir, "beovox-s35", mine)
        preset, read_only = speaker_presets.list_presets()["beovox-s35"]
        self.assertEqual(preset["name"], "My S 35")
        self.assertFalse(read_only)

    def test_an_invalid_file_is_skipped_not_fatal(self):
        self.write(self.system_dir, "good", a_preset("good"))
        with open(os.path.join(self.system_dir, "broken.json"), "w") as handle:
            handle.write("{not json")
        presets = speaker_presets.list_presets()
        self.assertIn("good", presets)
        self.assertNotIn("broken", presets)

    def test_missing_directory_is_not_an_error(self):
        shutil.rmtree(self.user_dir)
        self.write(self.system_dir, "good", a_preset("good"))
        self.assertIn("good", speaker_presets.list_presets())

    def test_get_preset_raises_for_unknown_id(self):
        with self.assertRaises(speaker_presets.PresetNotFound):
            speaker_presets.get_preset("nosuch")

    def test_get_preset_on_a_malformed_file_raises_invalid_not_not_found(self):
        # Skipped from the listing (test_an_invalid_file_is_skipped_not_fatal
        # above must keep passing unchanged), but a direct fetch of that id
        # should explain what's wrong rather than claim it doesn't exist.
        with open(os.path.join(self.system_dir, "broken.json"), "w") as handle:
            handle.write("{not json")
        self.assertNotIn("broken", speaker_presets.list_presets())
        with self.assertRaises(speaker_presets.PresetInvalid):
            speaker_presets.get_preset("broken")

    def test_get_preset_with_no_file_at_all_is_still_not_found(self):
        self.write(self.system_dir, "good", a_preset("good"))
        with self.assertRaises(speaker_presets.PresetNotFound):
            speaker_presets.get_preset("nosuch-either")


class TestValidation(PresetDirTestCase):

    def test_filename_must_match_the_id_field(self):
        self.write(self.system_dir, "renamed", a_preset("original"))
        self.assertNotIn("renamed", speaker_presets.list_presets())

    def test_unknown_schema_version_is_rejected(self):
        preset = a_preset()
        preset["schemaVersion"] = 99
        self.write(self.system_dir, "test-speaker", preset)
        self.assertNotIn("test-speaker", speaker_presets.list_presets())

    def test_missing_channel_is_rejected(self):
        preset = a_preset()
        del preset["channels"]["d"]
        self.write(self.system_dir, "test-speaker", preset)
        self.assertNotIn("test-speaker", speaker_presets.list_presets())

    def test_filter_missing_a_coefficient_is_rejected(self):
        preset = a_preset()
        del preset["channels"]["a"]["filters"][0]["b2"]
        self.write(self.system_dir, "test-speaker", preset)
        self.assertNotIn("test-speaker", speaker_presets.list_presets())

    def test_a_filter_that_is_not_an_object_is_rejected(self):
        # It has to be PresetInvalid rather than the TypeError the coefficient
        # check used to raise: list_presets() only catches PresetInvalid, so
        # anything else takes the whole listing down with it -- including the
        # bundled presets in the system directory.
        preset = a_preset()
        preset["channels"]["a"]["filters"] = [5]
        self.write(self.user_dir, "test-speaker", preset)
        self.write(self.system_dir, "good", a_preset("good"))
        presets = speaker_presets.list_presets()
        self.assertNotIn("test-speaker", presets)
        self.assertIn("good", presets)

    def test_non_numeric_coefficient_is_rejected(self):
        # Coefficients reach the DSP verbatim, and applying is a whole-bank
        # write: caught here, or the float() fails partway through an apply.
        preset = a_preset()
        preset["channels"]["a"]["filters"][0]["b2"] = "nope"
        self.write(self.system_dir, "test-speaker", preset)
        self.assertNotIn("test-speaker", speaker_presets.list_presets())

    def test_non_numeric_delay_is_rejected(self):
        preset = a_preset()
        preset["channels"]["a"]["delayMs"] = "bad"
        self.write(self.system_dir, "test-speaker", preset)
        self.assertNotIn("test-speaker", speaker_presets.list_presets())

    def test_negative_delay_is_rejected(self):
        preset = a_preset()
        preset["channels"]["a"]["delayMs"] = -1.0
        self.write(self.system_dir, "test-speaker", preset)
        self.assertNotIn("test-speaker", speaker_presets.list_presets())

    def test_non_numeric_level_is_rejected(self):
        preset = a_preset()
        preset["channels"]["a"]["level"] = "loud"
        self.write(self.system_dir, "test-speaker", preset)
        self.assertNotIn("test-speaker", speaker_presets.list_presets())

    def test_non_boolean_invert_is_rejected(self):
        preset = a_preset()
        preset["channels"]["a"]["invert"] = "yes"
        self.write(self.system_dir, "test-speaker", preset)
        self.assertNotIn("test-speaker", speaker_presets.list_presets())

    def test_a_channel_omitting_the_optional_fields_is_still_accepted(self):
        preset = a_preset()
        for field in ("level", "delayMs", "invert", "enabled"):
            del preset["channels"]["a"][field]
        self.write(self.system_dir, "test-speaker", preset)
        self.assertIn("test-speaker", speaker_presets.list_presets())


class TestBankSlots(unittest.TestCase):

    def test_parses_address_slash_cells(self):
        self.assertEqual(speaker_presets.bank_slots("691/80"), 16)

    def test_plain_register_is_not_a_bank(self):
        self.assertIsNone(speaker_presets.bank_slots("4861"))

    def test_missing_is_not_a_bank(self):
        self.assertIsNone(speaker_presets.bank_slots(None))


class TestCompatibility(unittest.TestCase):

    def test_a_matching_profile_is_compatible(self):
        self.assertIsNone(
            speaker_presets.incompatibility_reason(a_preset(), METADATA))

    def test_wrong_program_is_named_in_the_reason(self):
        metadata = dict(METADATA, programID="dacdsp")
        reason = speaker_presets.incompatibility_reason(a_preset(), metadata)
        self.assertIn("beocreate-universal", reason)
        self.assertIn("dacdsp", reason)

    def test_older_profile_version_is_rejected(self):
        metadata = dict(METADATA, profileVersion="10")
        reason = speaker_presets.incompatibility_reason(a_preset(), metadata)
        self.assertIn("11", reason)

    def test_sample_rate_mismatch_is_rejected(self):
        """Coefficients are computed for one rate. Applying 48 kHz biquads to
        a 96 kHz program gives a plausible-looking, wrong crossover."""
        metadata = dict(METADATA, sampleRate="96000")
        reason = speaker_presets.incompatibility_reason(a_preset(), metadata)
        self.assertIn("48000", reason)
        self.assertIn("96000", reason)

    def test_missing_bank_is_rejected(self):
        metadata = dict(METADATA)
        del metadata["IIR_C"]
        reason = speaker_presets.incompatibility_reason(a_preset(), metadata)
        self.assertIn("IIR_C", reason)

    def test_bank_too_small_is_rejected(self):
        metadata = dict(METADATA, IIR_A="691/25")   # 5 slots
        reason = speaker_presets.incompatibility_reason(
            a_preset(filters=8), metadata)
        self.assertIn("8", reason)
        self.assertIn("5", reason)

    def test_empty_metadata_is_rejected_rather_than_assumed_good(self):
        self.assertIsNotNone(
            speaker_presets.incompatibility_reason(a_preset(), {}))


class TestChannelRegisterWrites(unittest.TestCase):

    def writes(self, **channel_kwargs):
        settings = a_channel(**channel_kwargs)
        return speaker_presets.channel_register_writes(
            "a", settings, METADATA, 48000)

    def test_role_is_an_index_into_the_profiles_own_ordering(self):
        """left,right,mono,side -> mono is 2. Hardcoding the order would break
        silently on a profile that lists them differently."""
        self.assertIn((4861, 2), self.writes(role="mono"))
        self.assertIn((4861, 0), self.writes(role="left"))
        self.assertIn((4861, 3), self.writes(role="side"))

    def test_unknown_role_is_rejected(self):
        with self.assertRaises(speaker_presets.PresetInvalid):
            self.writes(role="rear")

    def test_level_is_written_as_a_float(self):
        """POST /memory writes an int as a raw word and a float as fixed
        point. A level arriving as int 1 would be memory word 1, silence."""
        address, value = [w for w in self.writes(level=1.0) if w[0] == 781][0]
        self.assertIsInstance(value, float)
        self.assertEqual(value, 1.0)

    def test_a_disabled_channel_is_muted(self):
        _, value = [w for w in self.writes(enabled=False) if w[0] == 781][0]
        self.assertEqual(value, 0.0)

    def test_delay_converts_milliseconds_to_samples(self):
        _, value = [w for w in self.writes(delay_ms=10.0) if w[0] == 786][0]
        self.assertEqual(value, 480)
        self.assertIsInstance(value, int)

    def test_delay_is_clamped_to_the_profiles_maximum(self):
        _, value = [w for w in self.writes(delay_ms=100.0) if w[0] == 786][0]
        self.assertEqual(value, 2000)

    def test_invert_is_written_as_an_integer_flag(self):
        _, value = [w for w in self.writes(invert=True) if w[0] == 4867][0]
        self.assertEqual(value, 1)
        self.assertIsInstance(value, int)

    def test_delay_never_goes_below_zero(self):
        """channel_register_writes() does not itself call validate(), so a
        negative delay that reached it some other way must still clamp to
        zero rather than reach a register write negative."""
        writes = speaker_presets.channel_register_writes(
            "a", a_channel(delay_ms=-10.0), METADATA, 48000)
        _, value = [w for w in writes if w[0] == 786][0]
        self.assertEqual(value, 0)

    def test_registers_the_profile_lacks_are_skipped(self):
        metadata = dict(METADATA)
        del metadata["invertARegister"]
        writes = speaker_presets.channel_register_writes(
            "a", a_channel(), metadata, 48000)
        self.assertEqual([address for address, _ in writes], [4861, 781, 786])


if __name__ == "__main__":
    unittest.main()
