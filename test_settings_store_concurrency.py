#!/usr/bin/env python3
"""
Regression tests for hifiberry-os#626.

Concurrent writes to the settings store used to corrupt or truncate
/var/lib/hifiberry/dspsettings.json, because save_store() wrote through a
fixed shared '<store>.tmp' path and took its flock on that temp file *after*
open(..., 'w') had already truncated it.

These tests load settings_store.py directly by file path so they run with a
bare python3 -- importing hifiberrydsp.api pulls in Flask, which is not
installed on a dev machine.
"""

import importlib.util
import json
import os
import shutil
import tempfile
import threading
import unittest

MODULE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'src', 'hifiberrydsp', 'api', 'settings_store.py')

_spec = importlib.util.spec_from_file_location('settings_store_under_test', MODULE_PATH)
settings_store_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(settings_store_module)
SettingsStore = settings_store_module.SettingsStore

CHECKSUM = "8B924F2C2210B903CB4226C12C56EE44"

# Minimum _file_lock() entries each mutating method must produce: its own
# transaction lock plus save_store()'s nested one. These are MEASURED values.
# toggle_filter_bypass is 3 because it delegates to set_filter_bypass, which
# locks as well -- a flat threshold of 2 would let its outer lock be removed
# without the test noticing (see test_toggle_filter_bypass_outer_lock_is_detected).
LOCK_ENTRY_MINIMUMS = {
    "store_filter": 2,
    "store_memory_setting": 2,
    "set_filter_bypass": 2,
    "toggle_filter_bypass": 3,
    "set_filter_bank_bypass": 2,
    "delete_filters": 2,
    "clear_empty_profiles": 2,
}


def a_filter(freq):
    return {"type": "PeakingEq", "f": freq, "db": -3.0, "q": 1.0}


class TestStoreFileOverride(unittest.TestCase):
    """The store path must be injectable, otherwise nothing here is testable."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.temp_dir, 'dspsettings.json')

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_store_file_can_be_overridden(self):
        store = SettingsStore(store_file=self.store_path)
        self.assertEqual(store.store_file, self.store_path)
        self.assertTrue(store.store_filter(CHECKSUM, "bankLeft", 0, a_filter(100)))
        self.assertTrue(os.path.exists(self.store_path))

    def test_default_store_file_is_unchanged(self):
        store = SettingsStore()
        self.assertEqual(store.store_file, "/var/lib/hifiberry/dspsettings.json")


class TestAtomicSave(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.temp_dir, 'dspsettings.json')
        self.store = SettingsStore(store_file=self.store_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_each_save_uses_a_distinct_temp_file(self):
        """A shared fixed temp name is the root cause -- forbid it explicitly."""
        sources = []
        real_replace = settings_store_module.os.replace

        def recording_replace(src, dst):
            sources.append(src)
            return real_replace(src, dst)

        settings_store_module.os.replace = recording_replace
        try:
            self.store.save_store({CHECKSUM: {"filters": {}, "memory": {}}})
            self.store.save_store({CHECKSUM: {"filters": {}, "memory": {}}})
        finally:
            settings_store_module.os.replace = real_replace

        self.assertEqual(len(sources), 2)
        self.assertNotEqual(sources[0], sources[1],
                            "save_store must not reuse a fixed temp filename")
        for src in sources:
            self.assertNotEqual(src, self.store_path + '.tmp')

    def test_save_leaves_no_temp_files_behind(self):
        self.store.save_store({CHECKSUM: {"filters": {}, "memory": {}}})
        # NOT glob('*.tmp'): the temp files are dot-prefixed ('.dspsettings-*.tmp')
        # and glob skips hidden names, which would make this assertion vacuous.
        leftovers = [name for name in os.listdir(self.temp_dir)
                     if name.startswith('.dspsettings-') and name.endswith('.tmp')]
        self.assertEqual(leftovers, [], f"temp files left behind: {leftovers}")

    def test_a_brace_in_a_string_value_does_not_block_saving(self):
        """
        save_store() screened its own json.dumps() output by counting '{' and
        '}'. dumps() cannot emit unbalanced JSON, so the count could only ever
        be skewed by a brace inside a string value -- turning a valid save into
        a silent refusal, which is the failure this whole change exists to stop.
        """
        payload = {CHECKSUM: {"filters": {}, "memory": {"profileName": "room{eq"}}}

        self.assertTrue(self.store.save_store(payload),
                        "a brace inside a string value must not block the save")

        with open(self.store_path) as f:
            self.assertEqual(json.load(f), payload)

    def test_a_non_finite_coefficient_is_refused(self):
        """
        NaN and Infinity are not JSON. json.dumps() emits them by default, and
        they pass a brace count untouched, so a bad coefficient could be written
        into the store as text no strict reader will parse.
        """
        self.store.save_store({CHECKSUM: {"filters": {}, "memory": {}}})

        self.assertFalse(
            self.store.save_store({CHECKSUM: {"filters": {}, "memory": {"gain": float('nan')}}}),
            "a non-finite value must be refused, not written as NaN")

        # The previous good store must survive the refused write.
        with open(self.store_path) as f:
            surviving = json.load(f)
        self.assertEqual(surviving, {CHECKSUM: {"filters": {}, "memory": {}}})

    def test_a_stale_temp_file_does_not_break_saving(self):
        with open(self.store_path + '.tmp', 'w') as f:
            f.write('{"garbage": ')
        self.assertTrue(self.store.store_filter(CHECKSUM, "bankLeft", 0, a_filter(100)))
        with open(self.store_path) as f:
            json.load(f)


class TestLockCoverage(unittest.TestCase):
    """Every read-modify-write must run under _file_lock()."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.store = SettingsStore(store_file=os.path.join(self.temp_dir, 'dspsettings.json'))
        self.store.store_filter(CHECKSUM, "bankLeft", 0, a_filter(100))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # One invocation per name in MUTATING_METHODS. Driven from the constant so a
    # new mutating method added without a lock cannot slip through unexercised.
    #
    # NOTE: delete_filters must be given the literal store key ("bankLeft_0"),
    # not the address ("bankLeft"). delete_filters(address=...) matches the
    # literal filter key (settings_store.py: filter_key = str(address)), and
    # stored keys are "bankLeft_<offset>" -- with the bare address it matches
    # nothing, returns "No filter found" before reaching save_store, and the
    # lock count comes up short: a false failure reported as a missing lock.
    #
    # ORDERING COUPLING: this dict is only correct when run in
    # MUTATING_METHODS order, which is how test_mutating_methods_take_the_lock
    # iterates it. set_filter_bypass, set_filter_bank_bypass, and
    # delete_filters all have early-return paths that skip save_store when
    # their target filter/bank isn't found, and delete_filters here deletes
    # "bankLeft_0" (the key set up below) which set_filter_bypass and
    # set_filter_bank_bypass's invocations depend on still being present when
    # they run. Reordering MUTATING_METHODS would run delete_filters before
    # those two, and they'd then hit their own early-return paths -- reported
    # as "did not open _file_lock itself", which is a misleading diagnostic
    # for what's actually just a fixture-ordering dependency. Not restructured
    # because MUTATING_METHODS' declared order already matches this and the
    # coupling is now documented instead.
    def _invocations(self):
        return {
            "store_filter": lambda: self.store.store_filter(CHECKSUM, "bankLeft", 1, a_filter(200)),
            "store_memory_setting": lambda: self.store.store_memory_setting(CHECKSUM, "4744", [1.0]),
            "set_filter_bypass": lambda: self.store.set_filter_bypass(CHECKSUM, "bankLeft", 0, True),
            "toggle_filter_bypass": lambda: self.store.toggle_filter_bypass(CHECKSUM, "bankLeft", 0),
            "set_filter_bank_bypass": lambda: self.store.set_filter_bank_bypass(CHECKSUM, "bankLeft", False),
            "delete_filters": lambda: self.store.delete_filters(checksum=CHECKSUM, address="bankLeft_0"),
            "clear_empty_profiles": lambda: self.store.clear_empty_profiles(),
        }

    def test_mutating_methods_take_the_lock(self):
        """
        Each mutating method must open the lock ITSELF, before its load_store().

        Counting is total, not gated on nesting depth. Two earlier attempts at
        this test could never fail, and it is worth recording why:

          * Counting every entry with a threshold of >= 1 passes trivially,
            because save_store() opens the lock itself.
          * Gating on depth == 0 is no better. If the method locks, the method
            is the depth-0 entry and save_store nests below it: count 1. If the
            method does NOT lock, save_store's own entry is the depth-0 one:
            count 1 again. The value is invariant, so the assertion is
            unfalsifiable. This was measured: 1 in every case, baseline and
            mutants alike -- proven both by running the guard test as written
            (it failed) and independently by editing store_filter's
            `with self._file_lock():` to `with contextlib.nullcontext():` in
            place and re-running this test -- it still passed.

        What actually discriminates is the TOTAL number of entries, compared
        against a per-method minimum, not a flat one. A flat minimum of 2 is
        still not enough: toggle_filter_bypass delegates to set_filter_bypass,
        which locks too, so removing just toggle_filter_bypass's own outer
        lock still yields 2 entries (set_filter_bypass's own + save_store's),
        clearing a flat threshold of 2 while the read and the write are no
        longer one transaction (see
        test_toggle_filter_bypass_outer_lock_is_detected). The minimums are
        measured values, not guesses -- see LOCK_ENTRY_MINIMUMS.
        """
        calls = {"n": 0}
        real_lock = SettingsStore._file_lock

        import contextlib

        @contextlib.contextmanager
        def counting_lock(inner_self):
            calls["n"] += 1
            with real_lock(inner_self):
                yield

        invocations = self._invocations()
        missing = set(settings_store_module.MUTATING_METHODS) - set(invocations)
        self.assertEqual(missing, set(), f"no invocation defined for {missing}")
        unpriced = set(settings_store_module.MUTATING_METHODS) - set(LOCK_ENTRY_MINIMUMS)
        self.assertEqual(unpriced, set(), f"no lock-entry minimum defined for {unpriced}")

        SettingsStore._file_lock = counting_lock
        try:
            for name in settings_store_module.MUTATING_METHODS:
                calls["n"] = 0
                invocations[name]()
                self.assertGreaterEqual(
                    calls["n"], LOCK_ENTRY_MINIMUMS[name],
                    f"{name} took {calls['n']} lock entries, expected at least "
                    f"{LOCK_ENTRY_MINIMUMS[name]} — it did not open _file_lock itself, "
                    f"so its load-mutate-save is not transactional")
        finally:
            SettingsStore._file_lock = real_lock

    def test_lock_coverage_test_can_actually_fail(self):
        """
        Guard the guard: prove the counting above detects an unlocked method.

        Without this, a regression in the counting logic quietly turns
        test_mutating_methods_take_the_lock back into a test that always
        passes -- which is exactly what happened twice while this was written.
        """
        import contextlib

        calls = {"n": 0}
        real_lock = SettingsStore._file_lock

        @contextlib.contextmanager
        def counting_lock(inner_self):
            calls["n"] += 1
            with real_lock(inner_self):
                yield

        original = SettingsStore.store_filter

        def unlocked_store_filter(inner_self, checksum, address, offset, filter_data, bypassed=False):
            # store_filter with its transaction lock removed. save_store still
            # locks internally, which is precisely the case that fooled both
            # earlier versions of the counter.
            store = inner_self.load_store()
            store.setdefault(inner_self.normalize_checksum(checksum), {"filters": {}, "memory": {}})
            return inner_self.save_store(store)

        SettingsStore._file_lock = counting_lock
        SettingsStore.store_filter = unlocked_store_filter
        try:
            calls["n"] = 0
            self.store.store_filter(CHECKSUM, "bankLeft", 2, a_filter(300))
            # Exactly 1: save_store's own entry, and nothing else. Asserting
            # "< 2" would also accept 0, so a counter that stopped incrementing
            # entirely would still pass this guard.
            self.assertEqual(
                calls["n"], 1,
                f"expected exactly save_store's single lock entry, got {calls['n']} — "
                f"the counter no longer distinguishes a locked method from an "
                f"unlocked one, so test_mutating_methods_take_the_lock cannot fail")
            self.assertLess(
                calls["n"], LOCK_ENTRY_MINIMUMS["store_filter"],
                "an unlocked store_filter still met its minimum")
        finally:
            SettingsStore.store_filter = original
            SettingsStore._file_lock = real_lock

    def test_toggle_filter_bypass_outer_lock_is_detected(self):
        """
        toggle_filter_bypass is the only mutating method that calls another
        locking method (set_filter_bypass), so removing just its own outer
        lock still yields 2 entries -- enough to clear a flat threshold of 2
        while the read and the write are no longer one transaction. Its
        minimum is 3 for that reason; this proves the distinction holds.
        """
        import contextlib

        calls = {"n": 0}
        real_lock = SettingsStore._file_lock

        @contextlib.contextmanager
        def counting_lock(inner_self):
            calls["n"] += 1
            with real_lock(inner_self):
                yield

        original = SettingsStore.toggle_filter_bypass

        def unlocked_toggle(inner_self, checksum, address, offset):
            # The outer transaction lock removed; the delegation still locks.
            current = inner_self.get_filter_bypass_state(checksum, address, offset)
            if current is None:
                return False, "Filter not found"
            return inner_self.set_filter_bypass(checksum, address, offset, not current)

        SettingsStore._file_lock = counting_lock
        SettingsStore.toggle_filter_bypass = unlocked_toggle
        try:
            calls["n"] = 0
            self.store.toggle_filter_bypass(CHECKSUM, "bankLeft", 0)
            self.assertLess(
                calls["n"], LOCK_ENTRY_MINIMUMS["toggle_filter_bypass"],
                f"toggle_filter_bypass reached {calls['n']} entries without its own "
                f"lock — the per-method minimum is not catching it")
        finally:
            SettingsStore.toggle_filter_bypass = original
            SettingsStore._file_lock = real_lock

    def test_mutating_methods_constant_matches_reality(self):
        for name in settings_store_module.MUTATING_METHODS:
            self.assertTrue(hasattr(self.store, name), f"unknown method in MUTATING_METHODS: {name}")


class TestConcurrentWrites(unittest.TestCase):
    """The actual #626 reproduction: 8 threads writing filters concurrently."""

    THREADS = 8
    PER_THREAD = 5

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.temp_dir, 'dspsettings.json')
        self.store = SettingsStore(store_file=self.store_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_concurrent_store_filter_keeps_every_filter(self):
        failures = []
        start = threading.Barrier(self.THREADS)

        def writer(thread_index):
            start.wait()
            for i in range(self.PER_THREAD):
                offset = thread_index * self.PER_THREAD + i
                if not self.store.store_filter(CHECKSUM, "bankLeft", offset, a_filter(100 + offset)):
                    failures.append(f"store_filter returned False for offset {offset}")

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(self.THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(failures, [])

        with open(self.store_path) as f:
            data = json.load(f)          # must not raise: "Extra data" was the corruption symptom

        stored = data[CHECKSUM]["filters"]
        expected = {f"bankLeft_{n}" for n in range(self.THREADS * self.PER_THREAD)}
        missing = expected - set(stored)
        self.assertEqual(missing, set(), f"lost {len(missing)} filters to the write race")

    def test_concurrent_writes_to_two_banks_do_not_lose_either(self):
        start = threading.Barrier(2)

        def writer(bank):
            start.wait()
            for offset in range(16):
                self.store.store_filter(CHECKSUM, bank, offset, a_filter(100 + offset))

        threads = [threading.Thread(target=writer, args=(b,))
                   for b in ("bankLeft", "bankRight")]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        with open(self.store_path) as f:
            data = json.load(f)

        stored = data[CHECKSUM]["filters"]
        for bank in ("bankLeft", "bankRight"):
            for offset in range(16):
                self.assertIn(f"{bank}_{offset}", stored,
                              f"{bank} offset {offset} lost -- this is the asymmetric L/R symptom")


if __name__ == '__main__':
    unittest.main()
