#!/usr/bin/env python3
"""
Tests for the filter autoloading functionality: the boot-time path that
reapplies filters stored for the current DSP profile.

A bug fixed in 1.4.1 silently lost every REST-written filter on reboot,
because writes were keyed by the signature-mode SHA-1 while boot autoload
looked up the length-mode SHA-1. These tests exercise
SigmaTCPHandler.load_and_apply_filters() against its current default
(length-mode SHA-1, via calculate_program_checksums), not the legacy
signature-mode MD5 path that caused that bug -- recovery of filters filed
under that older key is covered separately, by
test_filter_restore_key.py's TestWhatTheDaemonDoesAtStartup.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add the src directory to the path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Importing sigmatcp pulls in adau145x -> spi, whose SpiHandler class opens
# the SPI device at class-definition time unless this flag is already set.
# Setting it here (rather than relying on conftest.py's pytest_configure)
# matches how test_filter_restore_key.py does it, so this module also
# imports cleanly when collected on its own.
import hifiberrydsp
hifiberrydsp._called_from_test = True

from hifiberrydsp.server.sigmatcp import SigmaTCPHandler  # noqa: E402


CHECKSUM = "8B924F2C2210B903CB4226C12C56EE44"


def a_filter():
    return {
        "eq1_band1": {
            "address": "eq1_band1",
            "offset": 0,
            "filter": {
                "a0": 1.0,
                "a1": -1.8,
                "a2": 0.81,
                "b0": 0.5,
                "b1": 0.0,
                "b2": -0.5
            },
            "timestamp": 1699564123.456
        }
    }


class TestFilterAutoloading(unittest.TestCase):

    @patch('hifiberrydsp.server.sigmatcp.adau145x.Adau145x.calculate_program_checksums')
    @patch('hifiberrydsp.server.sigmatcp.SettingsStore')
    @patch('hifiberrydsp.server.sigmatcp.SigmaTCPHandler.get_checked_xml')
    @patch('hifiberrydsp.server.sigmatcp.SigmaTCPHandler._apply_filter')
    def test_autoload_filters_success(self, mock_apply_filter, mock_get_xml,
                                       mock_store_class, mock_checksums):
        """A filter stored under the current length-mode SHA-1 is applied."""

        # Current DSP program hashes to this length-mode SHA-1
        mock_checksums.return_value = {"sha1": CHECKSUM}

        # The settings store holds one filter under that checksum, and
        # nothing under any other checksum, so there is nothing to recover.
        mock_store = MagicMock()
        mock_store.load_store.return_value = {}
        mock_store.load_filters.return_value = a_filter()
        mock_store.load_memory_settings.return_value = {}
        mock_store_class.return_value = mock_store

        # The filter is keyed by metadata name, which resolves through the
        # XML profile to a base address ("4096/0" -> address 4096, offset 0)
        mock_xml = MagicMock()
        mock_xml.get_meta.return_value = "4096/0"
        mock_get_xml.return_value = mock_xml

        mock_apply_filter.return_value = True

        result = SigmaTCPHandler.load_and_apply_filters()

        self.assertTrue(result)
        mock_checksums.assert_called_once_with(
            mode="length", algorithms=["sha1"], cached=True)
        mock_store.load_filters.assert_called_once_with(CHECKSUM)
        mock_apply_filter.assert_called_once_with(
            4096, a_filter()["eq1_band1"]["filter"])

    @patch('hifiberrydsp.server.sigmatcp.adau145x.Adau145x.calculate_program_checksums')
    def test_autoload_filters_no_checksum(self, mock_checksums):
        """No length-mode SHA-1 available -> autoloading bails out."""

        mock_checksums.return_value = {}

        result = SigmaTCPHandler.load_and_apply_filters()

        self.assertFalse(result)
        mock_checksums.assert_called_once_with(
            mode="length", algorithms=["sha1"], cached=True)

    @patch('hifiberrydsp.server.sigmatcp.adau145x.Adau145x.calculate_program_checksums')
    @patch('hifiberrydsp.server.sigmatcp.SettingsStore')
    def test_autoload_filters_no_filters(self, mock_store_class, mock_checksums):
        """Nothing stored under the current checksum counts as success."""

        mock_checksums.return_value = {"sha1": CHECKSUM}

        mock_store = MagicMock()
        mock_store.load_store.return_value = {}
        mock_store.load_filters.return_value = {}
        mock_store.load_memory_settings.return_value = {}
        mock_store_class.return_value = mock_store

        result = SigmaTCPHandler.load_and_apply_filters()

        self.assertTrue(result)
        mock_store.load_filters.assert_called_once_with(CHECKSUM)

    @patch('hifiberrydsp.server.sigmatcp.adau145x.Adau145x.write_biquad')
    @patch('hifiberrydsp.server.sigmatcp.Biquad')
    def test_apply_filter_direct_coefficients(self, mock_biquad_class, mock_write_biquad):
        """A filter given as direct biquad coefficients is written as-is."""

        mock_biquad_instance = MagicMock()
        mock_biquad_class.return_value = mock_biquad_instance

        filter_spec = {
            "a0": 1.0,
            "a1": -1.8,
            "a2": 0.81,
            "b0": 0.5,
            "b1": 0.0,
            "b2": -0.5
        }

        result = SigmaTCPHandler._apply_filter(0x1000, filter_spec)

        self.assertTrue(result)
        mock_biquad_class.assert_called_once_with(
            1.0, -1.8, 0.81, 0.5, 0.0, -0.5, "Autoloaded filter")
        mock_write_biquad.assert_called_once_with(0x1000, mock_biquad_instance)


if __name__ == '__main__':
    unittest.main()
