#!/usr/bin/env python3
"""
Tests that a stored filter survives a reboot.

A filter written through the REST API is recorded in the settings store
under the checksum of the DSP program it belongs to, and the daemon looks
that checksum up at startup to put the filters back. The two have to agree
on which checksum that is.

There are two of them. Signature mode hashes program memory up to the end
signature; length mode hashes the number of words the length registers
report. They cover different bytes and so produce different digests for
the same program. Length-mode SHA-1 is the one the daemon restores from.

Requires the test venv:
    python3 -m venv .venv-test
    .venv-test/bin/pip install flask waitress requests xmltodict
    .venv-test/bin/python -m unittest test_filter_restore_key -v
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
from hifiberrydsp.api.settings_store import SettingsStore  # noqa: E402

BASE_ADDRESS = 0x2000
BANK_KEY = "customFilterRegisterBankLeft"

# Distinct digests, so a test can tell which mode produced the key.
LENGTH_SHA1 = "E9C0BF069CC96EA37EDF7E8DEC0720F969EE0D66"
SIGNATURE_SHA1 = "B7F024C15A1EE7082BFE387716C1CBEA12B6D25D"
SIGNATURE_MD5 = "97C9C5A88582888D111259BF70D6D79E"

A_FILTER = {"type": "PeakingEq", "f": 1000, "db": -3.0, "q": 1.0}


def fake_checksums(mode="signature", algorithms=None, cached=True):
    digests = ({"sha1": LENGTH_SHA1, "md5": "0B3162182BC95A2E99FF3A8912C60E35"}
               if mode == "length"
               else {"sha1": SIGNATURE_SHA1, "md5": SIGNATURE_MD5})
    if algorithms:
        return {name: digests[name] for name in algorithms}
    return digests


class StoreKeyTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.temp_dir, 'dspsettings.json')
        self.store = SettingsStore(store_file=self.store_path)

        self._saved = {
            'store': restapi.settings_store,
            'write_biquad': restapi.Adau145x.write_biquad,
            'checksums': restapi.Adau145x.calculate_program_checksums,
            'program_len': restapi.Adau145x.get_program_len,
            'resolve': restapi.resolve_address_from_metadata,
            'samplerate': restapi.get_or_guess_samplerate,
        }
        restapi.settings_store = self.store
        restapi.Adau145x.write_biquad = staticmethod(lambda address, biquad: None)
        restapi.Adau145x.calculate_program_checksums = staticmethod(fake_checksums)
        restapi.Adau145x.get_program_len = staticmethod(lambda: 1142)
        restapi.resolve_address_from_metadata = lambda key: (
            BASE_ADDRESS if key == BANK_KEY else None)
        restapi.get_or_guess_samplerate = lambda: 48000
        restapi.clear_checksum_cache()

        restapi.app.config['TESTING'] = True
        self.client = restapi.app.test_client()

    def tearDown(self):
        restapi.settings_store = self._saved['store']
        restapi.Adau145x.write_biquad = self._saved['write_biquad']
        restapi.Adau145x.calculate_program_checksums = self._saved['checksums']
        restapi.Adau145x.get_program_len = self._saved['program_len']
        restapi.resolve_address_from_metadata = self._saved['resolve']
        restapi.get_or_guess_samplerate = self._saved['samplerate']
        restapi.clear_checksum_cache()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def stored_keys(self):
        with open(self.store_path) as handle:
            return sorted(json.load(handle).keys())


class TestTheKeyAFilterIsStoredUnder(StoreKeyTestCase):

    def test_is_the_length_based_checksum_the_daemon_restores_from(self):
        response = self.client.post('/biquad', json={
            "address": BANK_KEY, "offset": 0, "filter": A_FILTER})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.stored_keys(), [LENGTH_SHA1])

    def test_makes_the_filter_findable_by_the_restore_lookup(self):
        self.client.post('/biquad', json={
            "address": BANK_KEY, "offset": 0, "filter": A_FILTER})

        restored = self.store.load_filters(LENGTH_SHA1)

        self.assertEqual(list(restored), [f"{BANK_KEY}_0"])

    def test_is_reported_the_same_way_by_the_helper(self):
        self.assertEqual(restapi.get_current_program_checksum_sha1(), LENGTH_SHA1)


class TestRecoveringFiltersStoredUnderTheOldKey(StoreKeyTestCase):

    def a_stored_profile(self, checksum):
        self.store.store_filter(checksum, BANK_KEY, 0,
                                {"type": "PeakingEq", "f": 900, "db": -2.0, "q": 1.0})

    def test_moves_a_profile_from_the_old_checksum_to_the_new_one(self):
        self.a_stored_profile(SIGNATURE_SHA1)

        moved = self.store.migrate_checksum(SIGNATURE_SHA1, LENGTH_SHA1)

        self.assertTrue(moved)
        self.assertEqual(self.stored_keys(), [LENGTH_SHA1])
        self.assertEqual(list(self.store.load_filters(LENGTH_SHA1)),
                         [f"{BANK_KEY}_0"])

    def test_refuses_to_overwrite_settings_already_held_under_the_new_one(self):
        self.a_stored_profile(SIGNATURE_SHA1)
        self.store.store_filter(LENGTH_SHA1, BANK_KEY, 3, A_FILTER)

        moved = self.store.migrate_checksum(SIGNATURE_SHA1, LENGTH_SHA1)

        self.assertFalse(moved)
        self.assertEqual(list(self.store.load_filters(LENGTH_SHA1)),
                         [f"{BANK_KEY}_3"])
        self.assertEqual(list(self.store.load_filters(SIGNATURE_SHA1)),
                         [f"{BANK_KEY}_0"])

    def test_leaves_profiles_belonging_to_other_programs_alone(self):
        other = "1111111111111111111111111111111111111111"
        self.a_stored_profile(other)

        moved = self.store.migrate_checksum(SIGNATURE_SHA1, LENGTH_SHA1)

        self.assertFalse(moved)
        self.assertEqual(self.stored_keys(), [other])

    def test_moves_a_profile_that_holds_only_memory_settings(self):
        # memory is half of what a profile can hold, and half the emptiness
        # test the refusal is built on
        self.store.store_memory_setting(SIGNATURE_SHA1, "4744", [1.0, 0.5])

        moved = self.store.migrate_checksum(SIGNATURE_SHA1, LENGTH_SHA1)

        self.assertTrue(moved)
        self.assertEqual(list(self.store.load_memory_settings(LENGTH_SHA1)), ["4744"])
        self.assertEqual(self.stored_keys(), [LENGTH_SHA1])

    def test_does_nothing_when_there_is_nothing_under_the_old_checksum(self):
        self.a_stored_profile(LENGTH_SHA1)

        moved = self.store.migrate_checksum(SIGNATURE_SHA1, LENGTH_SHA1)

        self.assertFalse(moved)
        self.assertEqual(self.stored_keys(), [LENGTH_SHA1])


class TestMigrationRefusals(StoreKeyTestCase):

    def a_stored_profile(self, checksum):
        self.store.store_filter(checksum, BANK_KEY, 0,
                                {"type": "PeakingEq", "f": 900, "db": -2.0, "q": 1.0})

    def test_reports_failure_when_the_store_cannot_be_written(self):
        # save_store() returns False rather than raising, so a migration that
        # says True while the file is untouched would send the caller away
        # satisfied and skip the remaining candidate
        self.a_stored_profile(SIGNATURE_SHA1)
        # stub only the save the migration itself performs, so the stub does
        # not also stand in for the one load_store() may do while normalising
        real_save = self.store.save_store
        calls = {"n": 0}

        def failing_save(data):
            calls["n"] += 1
            return False if calls["n"] > 0 else real_save(data)

        self.store.save_store = failing_save

        self.assertFalse(self.store.migrate_checksum(SIGNATURE_SHA1, LENGTH_SHA1))

        self.store.save_store = real_save
        self.assertEqual(list(self.store.load_filters(SIGNATURE_SHA1)),
                         [f"{BANK_KEY}_0"])
        self.assertEqual(self.store.load_filters(LENGTH_SHA1), {})

    def test_does_not_resurrect_filters_that_were_deleted(self):
        # delete_filters() empties a profile but keeps the key, and that
        # emptiness is a decision the user made
        self.store.store_filter(LENGTH_SHA1, BANK_KEY, 0, A_FILTER)
        self.store.delete_filters(checksum=LENGTH_SHA1)
        self.a_stored_profile(SIGNATURE_SHA1)

        moved = self.store.migrate_checksum(SIGNATURE_SHA1, LENGTH_SHA1)

        self.assertFalse(moved)
        self.assertEqual(self.store.load_filters(LENGTH_SHA1), {})


class TestTheKeyAfterAProgramChange(StoreKeyTestCase):

    def test_does_not_stop_the_core_to_answer_a_cold_cache(self):
        # cached=False bypasses the Adau145x memory cache and re-reads
        # program memory with the core stopped, which is about a third of a
        # second of silence. A cache that holds nothing yet is not a reason
        # for that: the program has not changed, nobody has asked before.
        asked = []

        def checksums(mode="signature", algorithms=None, cached=True):
            asked.append(cached)
            return {"sha1": LENGTH_SHA1}

        restapi.Adau145x.calculate_program_checksums = staticmethod(checksums)

        self.assertEqual(restapi.get_current_program_checksum_sha1(), LENGTH_SHA1)

        self.assertEqual(asked, [True])

    def test_is_recomputed_instead_of_reusing_the_previous_programs_digest(self):
        # Clearing the module cache does not reach the one inside Adau145x,
        # so asking it for a cached digest after the program changed hands
        # back the digest of the program that is no longer loaded.
        loaded = {"program": "first", "length": 1142}
        digest_of = {"first": SIGNATURE_SHA1, "second": LENGTH_SHA1}
        hardware_cache = {"sha1": None}

        def checksums(mode="signature", algorithms=None, cached=True):
            if not (cached and hardware_cache["sha1"]):
                hardware_cache["sha1"] = digest_of[loaded["program"]]
            return {"sha1": hardware_cache["sha1"]}

        restapi.Adau145x.get_program_len = staticmethod(lambda: loaded["length"])
        restapi.Adau145x.calculate_program_checksums = staticmethod(checksums)

        self.assertEqual(restapi.get_current_program_checksum_sha1(),
                         digest_of["first"])

        loaded.update(program="second", length=2000)

        self.assertEqual(restapi.get_current_program_checksum_sha1(),
                         digest_of["second"])


class TestWhatTheDaemonDoesAtStartup(unittest.TestCase):
    """
    The end the user sees: a filter set before a reboot is there after it,
    including one recorded by a version that filed it under the old key.
    """

    def setUp(self):
        from hifiberrydsp.server import sigmatcp

        self.sigmatcp = sigmatcp
        self.temp_dir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.temp_dir, 'dspsettings.json')
        self.store = SettingsStore(store_file=self.store_path)

        self._saved = {
            'SettingsStore': sigmatcp.SettingsStore,
            'checksums': sigmatcp.adau145x.Adau145x.calculate_program_checksums,
            'checksum': sigmatcp.adau145x.Adau145x.calculate_program_checksum,
            'xml': sigmatcp.SigmaTCPHandler.get_checked_xml,
        }
        sigmatcp.SettingsStore = lambda *a, **kw: SettingsStore(store_file=self.store_path)
        sigmatcp.adau145x.Adau145x.calculate_program_checksums = staticmethod(fake_checksums)
        sigmatcp.adau145x.Adau145x.calculate_program_checksum = staticmethod(
            lambda *a, **kw: bytes.fromhex(SIGNATURE_MD5))
        sigmatcp.SigmaTCPHandler.get_checked_xml = staticmethod(lambda: None)

    def tearDown(self):
        self.sigmatcp.SettingsStore = self._saved['SettingsStore']
        self.sigmatcp.adau145x.Adau145x.calculate_program_checksums = self._saved['checksums']
        self.sigmatcp.adau145x.Adau145x.calculate_program_checksum = self._saved['checksum']
        self.sigmatcp.SigmaTCPHandler.get_checked_xml = self._saved['xml']
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_finds_a_filter_stored_under_the_old_signature_checksum(self):
        self.store.store_filter(SIGNATURE_SHA1, BANK_KEY, 0, A_FILTER)

        self.sigmatcp.SigmaTCPHandler.load_and_apply_filters()

        self.assertEqual(list(self.store.load_filters(LENGTH_SHA1)),
                         [f"{BANK_KEY}_0"])
        self.assertEqual(self.store.load_filters(SIGNATURE_SHA1), {})

    def test_finds_a_filter_stored_under_the_older_md5_checksum(self):
        self.store.store_filter(SIGNATURE_MD5, BANK_KEY, 0, A_FILTER)

        self.sigmatcp.SigmaTCPHandler.load_and_apply_filters()

        self.assertEqual(list(self.store.load_filters(LENGTH_SHA1)),
                         [f"{BANK_KEY}_0"])

    def test_takes_the_sha1_entry_when_both_older_keys_are_present(self):
        # a device that ran an affected version and an older one before it
        # holds both, which is the state the field device is in
        self.store.store_filter(SIGNATURE_SHA1, BANK_KEY, 0, A_FILTER)
        self.store.store_filter(SIGNATURE_MD5, BANK_KEY, 7, A_FILTER)

        self.sigmatcp.SigmaTCPHandler.load_and_apply_filters()

        self.assertEqual(list(self.store.load_filters(LENGTH_SHA1)),
                         [f"{BANK_KEY}_0"])
        # the older one is left where it is rather than merged or dropped
        self.assertEqual(list(self.store.load_filters(SIGNATURE_MD5)),
                         [f"{BANK_KEY}_7"])

    def test_does_not_look_for_older_keys_once_the_canonical_one_exists(self):
        self.store.store_filter(LENGTH_SHA1, BANK_KEY, 2, A_FILTER)
        self.store.store_filter(SIGNATURE_SHA1, BANK_KEY, 0, A_FILTER)
        seen = []
        real = self.sigmatcp.adau145x.Adau145x.calculate_program_checksum
        self.sigmatcp.adau145x.Adau145x.calculate_program_checksum = staticmethod(
            lambda *a, **kw: seen.append("md5") or real(*a, **kw))

        self.sigmatcp.SigmaTCPHandler.load_and_apply_filters()

        self.sigmatcp.adau145x.Adau145x.calculate_program_checksum = real
        self.assertEqual(seen, [], "computed a legacy checksum it did not need")

    def test_does_not_compute_legacy_checksums_when_there_is_nothing_to_migrate(self):
        # a device that has never stored a filter would otherwise pay a
        # signature-mode program read, which stops the core, on every start
        # and after every profile install
        modes = []
        real = self.sigmatcp.adau145x.Adau145x.calculate_program_checksums

        def checksums(mode="signature", algorithms=None, cached=True):
            modes.append(mode)
            return real(mode, algorithms, cached)

        self.sigmatcp.adau145x.Adau145x.calculate_program_checksums = staticmethod(checksums)

        self.sigmatcp.SigmaTCPHandler.load_and_apply_filters()

        self.sigmatcp.adau145x.Adau145x.calculate_program_checksums = staticmethod(real)
        self.assertNotIn("signature", modes)

    def test_leaves_a_store_that_is_already_keyed_correctly_alone(self):
        self.store.store_filter(LENGTH_SHA1, BANK_KEY, 2, A_FILTER)

        self.sigmatcp.SigmaTCPHandler.load_and_apply_filters()

        self.assertEqual(list(self.store.load_filters(LENGTH_SHA1)),
                         [f"{BANK_KEY}_2"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
