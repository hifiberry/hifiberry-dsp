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

import glob
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
    # DEVIATION FROM THE BRIEF: delete_filters's invocation originally read
    # address="bankLeft". delete_filters(address=...) matches the literal
    # filter key, not the bare address (see settings_store.py, filter_key =
    # str(address)) -- stored keys are "bankLeft_<offset>", so "bankLeft"
    # never matches and the method takes its early-return "not found" branch
    # without ever calling save_store(). That made this invocation exercise
    # nothing below delete_filters's own lock. Using "bankLeft_0" (the key
    # setUp actually stores) makes it reach save_store() like every other
    # invocation here.
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

        DEVIATION FROM THE BRIEF: the brief's design counted only _file_lock()
        entries made at "depth 0", attributing that single depth-0 entry to
        "the outermost caller, i.e. the method under test". That attribution
        is not sound: save_store() also opens _file_lock() unconditionally
        (see save_store()), so exactly one depth-0 entry occurs on every call
        into a mutating method whether or not the method takes its own lock --
        if the method locks first, its own entry is the depth-0 one and
        save_store()'s nested entry is skipped (depth > 0); if the method
        doesn't lock, save_store()'s entry becomes the depth-0 one instead.
        Either way the depth-0 count is invariantly 1, so
        assertGreaterEqual(calls, 1) can never fail. Proven with the exact
        mutation this file's own guard test performs (see
        test_lock_coverage_test_can_actually_fail) and independently by
        editing store_filter's `with self._file_lock():` to
        `with contextlib.nullcontext():` in place and re-running this test --
        it still passes.

        What actually distinguishes the two cases is the TOTAL number of
        nested _file_lock() entries (gated by nothing): a correctly locked
        method always produces at least 2 (its own entry, then save_store()'s
        nested one -- toggle_filter_bypass produces 3, since it also nests
        through set_filter_bypass's own lock). A method with no transaction
        lock of its own, whose load-mutate-save reaches save_store() through
        no other locked call, produces exactly 1 (save_store()'s alone).
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

        SettingsStore._file_lock = counting_lock
        try:
            for name in settings_store_module.MUTATING_METHODS:
                calls["n"] = 0
                invocations[name]()
                self.assertGreaterEqual(
                    calls["n"], 2,
                    f"{name} did not open _file_lock itself — its load-mutate-save "
                    f"is not transactional (only save_store()'s own internal lock "
                    f"fired)")
        finally:
            SettingsStore._file_lock = real_lock

    def test_lock_coverage_test_can_actually_fail(self):
        """
        Guard the guard: prove the total-entry counting above detects an
        unlocked method. Without this, a regression in the counting logic
        could silently turn test_mutating_methods_take_the_lock back into a
        test that always passes.
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
            # store_filter with its transaction lock removed; save_store still
            # takes the lock internally, which is exactly the case that fooled
            # the depth-0 counter this replaces (see test_mutating_methods_
            # take_the_lock's docstring for the mechanical proof).
            store = inner_self.load_store()
            store.setdefault(inner_self.normalize_checksum(checksum), {"filters": {}, "memory": {}})
            return inner_self.save_store(store)

        SettingsStore._file_lock = counting_lock
        SettingsStore.store_filter = unlocked_store_filter
        try:
            calls["n"] = 0
            self.store.store_filter(CHECKSUM, "bankLeft", 2, a_filter(300))
            self.assertLess(
                calls["n"], 2,
                "the counter reached the transactional threshold of 2 for a "
                "method that never took its own lock -- "
                "test_mutating_methods_take_the_lock cannot fail")
        finally:
            SettingsStore.store_filter = original
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
