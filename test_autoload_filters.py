#!/usr/bin/env python3
"""
Test script for the filter autoloading functionality
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Add the src directory to the path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from hifiberrydsp.server.sigmatcp import SigmaTCPHandler
from hifiberrydsp.api.filter_store import FilterStore

class TestFilterAutoloading(unittest.TestCase):
    
    def setUp(self):
        """Set up a temporary directory for testing"""
        self.temp_dir = tempfile.mkdtemp()
        self.filter_store = FilterStore(self.temp_dir)
        
        # Set up some test filters
        test_checksum = "8B924F2C2210B903CB4226C12C56EE44"
        test_filters = {
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
            },
            "0x1000_1": {
                "address": "0x1000",
                "offset": 1,
                "filter": {
                    "type": "PeakingEq",
                    "f": 1000,
                    "db": -3.0,
                    "q": 1.0
                },
                "timestamp": 1699564156.789
            }
        }
        
        # Save test data
        store_data = {test_checksum: test_filters}
        self.filter_store.save(store_data)
    
    def tearDown(self):
        """Clean up after tests"""
        # Clean up temp files
        store_file = os.path.join(self.temp_dir, 'filters.json')
        if os.path.exists(store_file):
            os.remove(store_file)
        os.rmdir(self.temp_dir)
    
    @patch('hifiberrydsp.server.sigmatcp.adau145x.Adau145x.calculate_program_checksum')
    @patch('hifiberrydsp.server.sigmatcp.FilterStore')
    @patch('hifiberrydsp.server.sigmatcp.SigmaTCPHandler.get_checked_xml')
    @patch('hifiberrydsp.server.sigmatcp.SigmaTCPHandler._apply_filter')
    def test_autoload_filters_success(self, mock_apply_filter, mock_get_xml, mock_filter_store_class, mock_checksum):
        """Test successful filter autoloading"""
        
        # Mock the checksum calculation
        mock_checksum.return_value = bytes.fromhex("8B924F2C2210B903CB4226C12C56EE44")
        
        # Mock the filter store
        mock_filter_store_instance = MagicMock()
        mock_filter_store_instance.get_filters.return_value = {
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
                }
            }
        }
        mock_filter_store_class.return_value = mock_filter_store_instance
        
        # Mock the XML profile
        mock_xml = MagicMock()
        mock_xml.get_meta.return_value = "4096/0"  # Mock metadata value
        mock_get_xml.return_value = mock_xml
        
        # Mock the filter application
        mock_apply_filter.return_value = True
        
        # Test the autoloading
        result = SigmaTCPHandler.load_and_apply_filters()
        
        # Verify results
        self.assertTrue(result)
        mock_checksum.assert_called_once()
        mock_filter_store_instance.get_filters.assert_called_once_with("8B924F2C2210B903CB4226C12C56EE44")
        mock_apply_filter.assert_called_once()
    
    @patch('hifiberrydsp.server.sigmatcp.adau145x.Adau145x.calculate_program_checksum')
    @patch('hifiberrydsp.server.sigmatcp.FilterStore')
    def test_autoload_filters_no_checksum(self, mock_filter_store_class, mock_checksum):
        """Test autoloading when checksum cannot be calculated"""
        
        # Mock checksum to return None
        mock_checksum.return_value = None
        
        # Test the autoloading
        result = SigmaTCPHandler.load_and_apply_filters()
        
        # Verify results
        self.assertFalse(result)
        mock_checksum.assert_called_once()
    
    @patch('hifiberrydsp.server.sigmatcp.adau145x.Adau145x.calculate_program_checksum')
    @patch('hifiberrydsp.server.sigmatcp.FilterStore')
    def test_autoload_filters_no_filters(self, mock_filter_store_class, mock_checksum):
        """Test autoloading when no filters are stored"""
        
        # Mock the checksum calculation
        mock_checksum.return_value = bytes.fromhex("8B924F2C2210B903CB4226C12C56EE44")
        
        # Mock the filter store to return empty
        mock_filter_store_instance = MagicMock()
        mock_filter_store_instance.get_filters.return_value = {}
        mock_filter_store_class.return_value = mock_filter_store_instance
        
        # Test the autoloading
        result = SigmaTCPHandler.load_and_apply_filters()
        
        # Verify results
        self.assertTrue(result)  # Should return True even with no filters
        mock_checksum.assert_called_once()
        mock_filter_store_instance.get_filters.assert_called_once_with("8B924F2C2210B903CB4226C12C56EE44")
    
    @patch('hifiberrydsp.server.sigmatcp.adau145x.Adau145x.is_valid_memory_address')
    @patch('hifiberrydsp.server.sigmatcp.adau145x.Adau145x.write_biquad')
    @patch('hifiberrydsp.server.sigmatcp.Biquad')
    def test_apply_filter_direct_coefficients(self, mock_biquad_class, mock_write_biquad, mock_is_valid):
        """Test applying a filter with direct coefficients"""
        
        # Mock address validation
        mock_is_valid.return_value = True
        
        # Mock Biquad creation
        mock_biquad_instance = MagicMock()
        mock_biquad_class.return_value = mock_biquad_instance
        
        # Test filter specification with direct coefficients
        filter_spec = {
            "a0": 1.0,
            "a1": -1.8,
            "a2": 0.81,
            "b0": 0.5,
            "b1": 0.0,
            "b2": -0.5
        }
        
        # Test the filter application
        result = SigmaTCPHandler._apply_filter(0x1000, filter_spec)
        
        # Verify results
        self.assertTrue(result)
        mock_biquad_class.assert_called_once_with(1.0, -1.8, 0.81, 0.5, 0.0, -0.5, "Autoloaded filter")
        mock_write_biquad.assert_called_once_with(0x1000, mock_biquad_instance)


if __name__ == '__main__':
    unittest.main()
