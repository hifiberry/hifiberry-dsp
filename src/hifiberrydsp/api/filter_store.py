'''
Copyright (c) 2023 Modul 9/HiFiBerry

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

import logging
import os
import json
import time


class FilterStore:
    """
    Manages the filter store for DSP profiles.
    
    The filter store saves and retrieves filter configurations organized by DSP profile.
    Filters are stored in a JSON file in the same directory as DSP profiles.
    """
    
    def __init__(self, profiles_dir="/usr/share/hifiberry/dspprofiles"):
        """
        Initialize the FilterStore
        
        Args:
            profiles_dir (str): Directory where DSP profiles are stored
        """
        self.profiles_dir = profiles_dir
        self.store_file = os.path.join(profiles_dir, "filters.json")
    
    def load(self):
        """
        Load the filter store from disk
        
        Returns:
            dict: The filter store data structure
        """
        if not os.path.exists(self.store_file):
            return {}
        
        try:
            with open(self.store_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading filter store: {str(e)}")
            return {}
    
    def save(self, store_data):
        """
        Save the filter store to disk
        
        Args:
            store_data (dict): The filter store data to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.store_file), exist_ok=True)
            
            with open(self.store_file, 'w') as f:
                json.dump(store_data, f, indent=2)
            return True
        except Exception as e:
            logging.error(f"Error saving filter store: {str(e)}")
            return False
    
    def store_filter(self, checksum, address, offset, filter_data):
        """
        Store a filter in the filter store organized by profile checksum
        
        Args:
            checksum (str): DSP profile checksum
            address (str): Memory address or metadata key 
            offset (int): Offset value
            filter_data (dict): The filter data
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            store = self.load()
            
            # Initialize checksum section if it doesn't exist
            if checksum not in store:
                store[checksum] = {}
            
            # Create a unique key for this filter location
            filter_key = f"{address}_{offset}" if offset > 0 else str(address)
            
            # Store the filter with timestamp
            store[checksum][filter_key] = {
                "address": address,
                "offset": offset,
                "filter": filter_data,
                "timestamp": time.time()
            }
            
            return self.save(store)
        except Exception as e:
            logging.error(f"Error storing filter: {str(e)}")
            return False
    
    def get_filters(self, checksum=None):
        """
        Get stored filters, optionally filtered by checksum
        
        Args:
            checksum (str, optional): DSP profile checksum to filter by
            
        Returns:
            dict: The stored filters
        """
        try:
            store = self.load()
            
            if checksum:
                return store.get(checksum, {})
            else:
                return store
        except Exception as e:
            logging.error(f"Error getting stored filters: {str(e)}")
            return {}
    
    def delete_filters(self, checksum=None, address=None, all_profiles=False):
        """
        Delete stored filters
        
        Args:
            checksum (str, optional): Profile checksum to delete filters for
            address (str, optional): Specific address to delete
            all_profiles (bool): Delete all filters for all profiles
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            if all_profiles:
                # Delete all filters for all profiles
                if self.save({}):
                    return True, "All filters deleted"
                else:
                    return False, "Failed to delete filters"
            
            elif checksum:
                store = self.load()
                
                if checksum not in store:
                    return False, f"No filters found for profile checksum '{checksum}'"
                
                if address:
                    # Delete specific filter
                    filter_key = str(address)
                    if filter_key in store[checksum]:
                        del store[checksum][filter_key]
                        if self.save(store):
                            return True, f"Filter at {address} deleted from profile checksum '{checksum}'"
                        else:
                            return False, "Failed to save changes"
                    else:
                        return False, f"No filter found at address '{address}' for profile checksum '{checksum}'"
                else:
                    # Delete all filters for the profile checksum
                    del store[checksum]
                    if self.save(store):
                        return True, f"All filters deleted for profile checksum '{checksum}'"
                    else:
                        return False, "Failed to save changes"
            
            else:
                return False, "Either 'checksum' or 'all_profiles=True' is required"
                
        except Exception as e:
            logging.error(f"Error deleting filters: {str(e)}")
            return False, str(e)
    
    def get_profile_filter_count(self, checksum):
        """
        Get the number of filters stored for a specific profile checksum
        
        Args:
            checksum (str): DSP profile checksum
            
        Returns:
            int: Number of filters stored for the profile
        """
        try:
            filters = self.get_filters(checksum)
            return len(filters)
        except Exception as e:
            logging.error(f"Error getting filter count for profile checksum '{checksum}': {str(e)}")
            return 0
    
    def get_all_profile_checksums(self):
        """
        Get all profile checksums that have filters stored
        
        Returns:
            list: List of profile checksums
        """
        try:
            store = self.load()
            return list(store.keys())
        except Exception as e:
            logging.error(f"Error getting profile checksums: {str(e)}")
            return []
    
    def get_profile_info_by_checksum(self, checksum):
        """
        Get filters for a specific checksum
        
        Args:
            checksum (str): DSP profile checksum
            
        Returns:
            dict: Filters for the checksum
        """
        try:
            store = self.load()
            return store.get(checksum, {})
        except Exception as e:
            logging.error(f"Error getting filters for checksum '{checksum}': {str(e)}")
            return {}
    
    def clear_empty_profiles(self):
        """
        Remove profiles that have no filters stored
        
        Returns:
            tuple: (success: bool, removed_count: int)
        """
        try:
            store = self.load()
            original_count = len(store)
            
            # Remove empty profile sections
            store = {checksum: filters for checksum, filters in store.items() if filters}
            
            if self.save(store):
                removed_count = original_count - len(store)
                return True, removed_count
            else:
                return False, 0
                
        except Exception as e:
            logging.error(f"Error clearing empty profiles: {str(e)}")
            return False, 0
