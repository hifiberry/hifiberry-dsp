#!/usr/bin/env python3
"""
Test script for the filter store functionality using checksums
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Add the src directory to the path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from hifiberrydsp.api.filter_store import FilterStore

class TestFilterStore(unittest.TestCase):
    
    def setUp(self):
        """Set up a temporary directory for testing"""
        self.temp_dir = tempfile.mkdtemp()
        self.filter_store = FilterStore(self.temp_dir)
    
    def tearDown(self):
        """Clean up after tests"""
        # Clean up temp files
        store_file = os.path.join(self.temp_dir, 'filters.json')
        if os.path.exists(store_file):
            os.remove(store_file)
        os.rmdir(self.temp_dir)
    
    def test_empty_filter_store(self):
        """Test loading an empty/non-existent filter store"""
        store = self.filter_store.load()
        self.assertEqual(store, {})
    
    def test_save_and_load_filter_store(self):
        """Test saving and loading filter store data"""
        test_data = {
            "8B924F2C2210B903CB4226C12C56EE44": {
                "eq1_band1_0": {
                    "address": "eq1_band1",
                    "offset": 0,
                    "filter": {"type": "PeakingEq", "f": 1000, "db": -3.0, "q": 1.0},
                    "timestamp": 1699564123.456
                }
            }
        }
        
        # Save the data
        success = self.filter_store.save(test_data)
        self.assertTrue(success)
        
        # Load it back
        loaded_data = self.filter_store.load()
        self.assertEqual(loaded_data, test_data)
    
    def test_store_filter(self):
        """Test storing a single filter"""
        checksum = "8B924F2C2210B903CB4226C12C56EE44"
        filter_data = {"type": "PeakingEq", "f": 1000, "db": -3.0, "q": 1.0}
        
        success = self.filter_store.store_filter(checksum, "eq1_band1", 0, filter_data)
        self.assertTrue(success)
        
        # Verify it was stored correctly
        store = self.filter_store.load()
        self.assertIn(checksum, store)
        self.assertIn("eq1_band1", store[checksum])
        
        stored_filter = store[checksum]["eq1_band1"]
        self.assertEqual(stored_filter["address"], "eq1_band1")
        self.assertEqual(stored_filter["offset"], 0)
        self.assertEqual(stored_filter["filter"], filter_data)
        self.assertIn("timestamp", stored_filter)
    
    def test_store_filter_with_offset(self):
        """Test storing a filter with offset"""
        checksum = "A1B2C3D4E5F6789012345678ABCDEF01"
        filter_data = {"a0": 1.0, "a1": -1.8, "a2": 0.81, "b0": 0.5, "b1": 0.0, "b2": -0.5}
        
        success = self.filter_store.store_filter(checksum, "0x100", 2, filter_data)
        self.assertTrue(success)
        
        # Verify it was stored with the correct key
        store = self.filter_store.load()
        self.assertIn("0x100_2", store[checksum])
        
        stored_filter = store[checksum]["0x100_2"]
        self.assertEqual(stored_filter["offset"], 2)
    
    def test_get_filters_all(self):
        """Test retrieving all stored filters"""
        # Set up some test data
        test_data = {
            "checksum1": {"filter1": {"address": "addr1", "offset": 0, "filter": {}}},
            "checksum2": {"filter2": {"address": "addr2", "offset": 1, "filter": {}}}
        }
        self.filter_store.save(test_data)
        
        # Get all filters
        filters = self.filter_store.get_filters()
        self.assertEqual(filters, test_data)
    
    def test_get_filters_by_checksum(self):
        """Test retrieving filters for a specific checksum"""
        # Set up some test data
        test_data = {
            "checksum1": {"filter1": {"address": "addr1", "offset": 0, "filter": {}}},
            "checksum2": {"filter2": {"address": "addr2", "offset": 1, "filter": {}}}
        }
        self.filter_store.save(test_data)
        
        # Get filters for checksum1 only
        filters = self.filter_store.get_filters("checksum1")
        self.assertEqual(filters, test_data["checksum1"])
        
        # Get filters for non-existent checksum
        filters = self.filter_store.get_filters("nonexistent")
        self.assertEqual(filters, {})
    
    def test_get_profile_info_by_checksum(self):
        """Test getting profile information by checksum"""
        checksum = "8B924F2C2210B903CB4226C12C56EE44"
        test_data = {
            checksum: {"filter1": {"address": "addr1", "offset": 0, "filter": {}}}
        }
        self.filter_store.save(test_data)
        
        profile_info = self.filter_store.get_profile_info_by_checksum(checksum)
        self.assertEqual(profile_info, test_data[checksum])
        
        # Test non-existent checksum
        profile_info = self.filter_store.get_profile_info_by_checksum("nonexistent")
        self.assertEqual(profile_info, {})
    
    def test_delete_filters_by_checksum(self):
        """Test deleting filters by checksum"""
        checksum = "8B924F2C2210B903CB4226C12C56EE44"
        test_data = {
            checksum: {
                "filter1": {"address": "addr1", "offset": 0, "filter": {}},
                "filter2": {"address": "addr2", "offset": 0, "filter": {}}
            }
        }
        self.filter_store.save(test_data)
        
        # Delete all filters for the checksum
        success, message = self.filter_store.delete_filters(checksum=checksum)
        self.assertTrue(success)
        
        # Verify they were deleted
        store = self.filter_store.load()
        self.assertNotIn(checksum, store)
    
    def test_delete_specific_filter(self):
        """Test deleting a specific filter"""
        checksum = "8B924F2C2210B903CB4226C12C56EE44"
        test_data = {
            checksum: {
                "filter1": {"address": "addr1", "offset": 0, "filter": {}},
                "filter2": {"address": "addr2", "offset": 0, "filter": {}}
            }
        }
        self.filter_store.save(test_data)
        
        # Delete specific filter
        success, message = self.filter_store.delete_filters(checksum=checksum, address="addr1")
        self.assertTrue(success)
        
        # Verify only one filter was deleted
        store = self.filter_store.load()
        self.assertIn(checksum, store)
        self.assertNotIn("filter1", store[checksum])
        self.assertIn("filter2", store[checksum])


if __name__ == '__main__':
    unittest.main()
