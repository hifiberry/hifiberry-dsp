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
import fcntl


class SettingsStore:
    """
    Manages the DSP settings store for DSP profiles.
    
    The settings store saves and retrieves both filter and memory settings organized by DSP profile.
    Settings are stored in a JSON file at /var/lib/hifiberry/dspsettings.json.
    
    JSON Structure:
    {
      "PROFILE_CHECKSUM": {
        "filters": {
          "filter_key": {
            "address": "eq1_band1",
            "offset": 0,
            "filter": {...},
            "timestamp": 1691234567.89,
            "bypassed": false
          }
        },
        "memory": {
          "memory_address": {
            "address": "4744",
            "values": [1.0, 0.5],
            "timestamp": 1691234567.89
          }
        }
      }
    }
    """
    
    def __init__(self, profiles_dir="/usr/share/hifiberry/dspprofiles"):
        """
        Initialize the SettingsStore
        
        Args:
            profiles_dir (str): Directory where DSP profiles are stored (kept for compatibility)
        """
        self.profiles_dir = profiles_dir
        self.store_file = "/var/lib/hifiberry/dspsettings.json"
    
    def load_store(self):
        """
        Load the settings store from disk
        
        Returns:
            dict: The settings store data structure
        """
        if not os.path.exists(self.store_file):
            return {}
        
        try:
            with open(self.store_file, 'r') as f:
                content = f.read().strip()
                if not content:
                    logging.warning("Settings store file is empty, creating new store")
                    return {}
                
                # Check for and fix common corruption issues
                content = self._fix_json_corruption(content)
                
                data = json.loads(content)
                
                # Migrate old filter-only format to new structure if needed
                migrated_data = self._migrate_legacy_format(data)
                
                # Normalize checksum keys to uppercase to prevent duplicates
                normalized_data = {}
                for checksum, profile_data in migrated_data.items():
                    normalized_checksum = self.normalize_checksum(checksum)
                    if normalized_checksum in normalized_data:
                        # Merge duplicate checksums (same checksum in different cases)
                        logging.warning(f"Found duplicate checksum with different case: {checksum} -> {normalized_checksum}")
                        
                        # Merge filters
                        if "filters" in profile_data:
                            if "filters" not in normalized_data[normalized_checksum]:
                                normalized_data[normalized_checksum]["filters"] = {}
                            for filter_key, filter_data in profile_data["filters"].items():
                                if filter_key not in normalized_data[normalized_checksum]["filters"]:
                                    normalized_data[normalized_checksum]["filters"][filter_key] = filter_data
                                else:
                                    # Keep the newer one based on timestamp
                                    existing_timestamp = normalized_data[normalized_checksum]["filters"][filter_key].get("timestamp", 0)
                                    new_timestamp = filter_data.get("timestamp", 0)
                                    if new_timestamp > existing_timestamp:
                                        normalized_data[normalized_checksum]["filters"][filter_key] = filter_data
                        
                        # Merge memory settings
                        if "memory" in profile_data:
                            if "memory" not in normalized_data[normalized_checksum]:
                                normalized_data[normalized_checksum]["memory"] = {}
                            for mem_key, mem_data in profile_data["memory"].items():
                                if mem_key not in normalized_data[normalized_checksum]["memory"]:
                                    normalized_data[normalized_checksum]["memory"][mem_key] = mem_data
                                else:
                                    # Keep the newer one based on timestamp
                                    existing_timestamp = normalized_data[normalized_checksum]["memory"][mem_key].get("timestamp", 0)
                                    new_timestamp = mem_data.get("timestamp", 0)
                                    if new_timestamp > existing_timestamp:
                                        normalized_data[normalized_checksum]["memory"][mem_key] = mem_data
                    else:
                        normalized_data[normalized_checksum] = profile_data
                
                # Save normalized data if changes were made
                if normalized_data != migrated_data:
                    logging.info("Normalizing checksums and removing duplicates in settings store")
                    self.save_store(normalized_data)
                
                return normalized_data
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error in settings store at line {e.lineno}, column {e.colno}: {e.msg}")
            # Try to recover by backing up the corrupted file and starting fresh
            try:
                backup_file = self.store_file + f".corrupted.{int(time.time())}"
                os.rename(self.store_file, backup_file)
                logging.warning(f"Corrupted settings store backed up to {backup_file}, starting with empty store")
            except Exception as backup_e:
                logging.error(f"Could not backup corrupted settings store: {backup_e}")
            return {}
        except Exception as e:
            logging.error(f"Error loading settings store: {str(e)}")
            return {}
    
    def _migrate_legacy_format(self, data):
        """
        Migrate legacy filter-only format to new settings structure
        
        Args:
            data (dict): Raw data from JSON file
            
        Returns:
            dict: Migrated data in new format
        """
        migrated_data = {}
        
        for checksum, profile_data in data.items():
            if not isinstance(profile_data, dict):
                continue
                
            # Check if this is already in new format (has filters/memory keys)
            if any(key in profile_data for key in ["filters", "memory"]):
                # Already in new format
                migrated_data[checksum] = profile_data
            else:
                # Legacy format - all entries are filters
                migrated_profile = {"filters": {}, "memory": {}}
                
                for key, value in profile_data.items():
                    if isinstance(value, dict) and "filter" in value:
                        # This looks like a filter entry
                        migrated_profile["filters"][key] = value
                    else:
                        # Unknown entry, keep as filter for backward compatibility
                        logging.warning(f"Unknown entry format in profile {checksum}, keeping as filter: {key}")
                        migrated_profile["filters"][key] = value
                
                migrated_data[checksum] = migrated_profile
        
        return migrated_data
    
    def normalize_checksum(self, checksum):
        """
        Normalize checksum to uppercase to prevent duplicates
        
        Args:
            checksum (str): Original checksum
            
        Returns:
            str: Normalized checksum
        """
        return str(checksum).upper()
    
    def _fix_json_corruption(self, content):
        """
        Fix common JSON corruption issues
        
        Args:
            content (str): Raw JSON content
            
        Returns:
            str: Fixed JSON content
        """
        import re
        
        # Remove trailing extra braces (most common corruption)
        # Count opening and closing braces
        open_braces = content.count('{')
        close_braces = content.count('}')
        
        if close_braces > open_braces:
            # Remove extra closing braces from the end
            extra_braces = close_braces - open_braces
            logging.warning(f"Detected {extra_braces} extra closing braces in JSON, attempting to fix")
            
            # Remove trailing braces and whitespace
            content = content.rstrip()
            for _ in range(extra_braces):
                if content.endswith('}'):
                    content = content[:-1].rstrip()
        
        # Remove trailing commas before closing braces/brackets
        content = re.sub(r',\s*}', '}', content)
        content = re.sub(r',\s*]', ']', content)
        
        return content
    
    def save_store(self, store_data):
        """
        Save the settings store to disk atomically with file locking
        
        Args:
            store_data (dict): The settings store data to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.store_file), exist_ok=True)
            
            # Write to a temporary file first for atomic operation
            temp_file = self.store_file + '.tmp'
            
            # Use file locking to prevent concurrent writes
            with open(temp_file, 'w') as f:
                # Apply exclusive lock (blocks until available)
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                
                try:
                    # Validate JSON structure before writing
                    json_content = json.dumps(store_data, indent=2, ensure_ascii=False)
                    
                    # Double-check for corruption patterns
                    open_braces = json_content.count('{')
                    close_braces = json_content.count('}')
                    if close_braces != open_braces:
                        logging.error(f"JSON brace mismatch detected: {open_braces} open vs {close_braces} close")
                        return False
                    
                    # Write the content
                    f.write(json_content)
                    f.flush()
                    os.fsync(f.fileno())  # Ensure data is written to disk
                    
                finally:
                    # Release lock (automatically released when file closes, but explicit is better)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            
            # Atomically move the temp file to the final location
            os.rename(temp_file, self.store_file)
            return True
        except Exception as e:
            logging.error(f"Error saving settings store: {str(e)}")
            # Clean up temp file if it exists
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
            return False
    
    def load_filters(self, checksum):
        """
        Load all filters for the specified DSP profile checksum.
        
        Args:
            checksum (str): DSP profile checksum
            
        Returns:
            dict: Dictionary mapping filter keys to filter data
        """
        store_data = self.load_store()
        normalized_checksum = self.normalize_checksum(checksum)
        profile_data = store_data.get(normalized_checksum, {})
        return profile_data.get("filters", {})
    
    def load_memory_settings(self, checksum):
        """
        Load all memory settings for the specified DSP profile checksum.
        
        Args:
            checksum (str): DSP profile checksum
            
        Returns:
            dict: Dictionary mapping memory addresses to memory data
        """
        store_data = self.load_store()
        normalized_checksum = self.normalize_checksum(checksum)
        profile_data = store_data.get(normalized_checksum, {})
        return profile_data.get("memory", {})
    
    def store_filter(self, checksum, address, offset, filter_data, bypassed=False):
        """
        Store a filter in the settings store organized by profile checksum
        
        Args:
            checksum (str): DSP profile checksum
            address (str): Memory address or metadata key 
            offset (int): Offset value
            filter_data (dict): The filter data
            bypassed (bool): Whether the filter is currently bypassed
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Normalize checksum to uppercase to prevent duplicates
            checksum = self.normalize_checksum(checksum)
            
            store = self.load_store()
            
            # Initialize checksum section if it doesn't exist
            if checksum not in store:
                store[checksum] = {"filters": {}, "memory": {}}
            
            # Ensure filters section exists
            if "filters" not in store[checksum]:
                store[checksum]["filters"] = {}
            
            # Create a unique key for this filter location
            # Always include offset suffix for consistency
            filter_key = f"{address}_{offset}"
            
            # Store the filter with timestamp and bypass state
            filter_entry = {
                "address": address,
                "offset": offset,
                "filter": filter_data,
                "timestamp": time.time(),
                "bypassed": bypassed
            }
            
            # If this filter already exists, preserve bypass state unless explicitly overridden
            if filter_key in store[checksum]["filters"] and "bypassed" in store[checksum]["filters"][filter_key]:
                # Preserve existing bypass state if not explicitly set
                existing_bypass = store[checksum]["filters"][filter_key].get("bypassed", False)
                filter_entry["bypassed"] = existing_bypass
            
            store[checksum]["filters"][filter_key] = filter_entry
            
            return self.save_store(store)
        except Exception as e:
            logging.error(f"Error storing filter: {str(e)}")
            return False
    
    def store_memory_setting(self, checksum, address, values):
        """
        Store a memory setting in the settings store organized by profile checksum
        
        Args:
            checksum (str): DSP profile checksum
            address (str): Memory address 
            values (list): The memory values to store
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Normalize checksum to uppercase to prevent duplicates
            checksum = self.normalize_checksum(checksum)
            
            store = self.load_store()
            
            # Initialize checksum section if it doesn't exist
            if checksum not in store:
                store[checksum] = {"filters": {}, "memory": {}}
            
            # Ensure memory section exists
            if "memory" not in store[checksum]:
                store[checksum]["memory"] = {}
            
            # Store the memory setting with timestamp
            memory_entry = {
                "address": address,
                "values": values,
                "timestamp": time.time()
            }
            
            store[checksum]["memory"][address] = memory_entry
            
            return self.save_store(store)
        except Exception as e:
            logging.error(f"Error storing memory setting: {str(e)}")
            return False
    
    def get_filters(self, checksum=None, group_by_bank=False):
        """
        Get stored filters, optionally filtered by checksum
        
        Args:
            checksum (str, optional): DSP profile checksum to filter by
            group_by_bank (bool): If True, group filters by bank (same address)
            
        Returns:
            dict: The stored filters
        """
        try:
            store = self.load_store()
            
            if checksum:
                # Normalize checksum to uppercase
                checksum = self.normalize_checksum(checksum)
                profile_data = store.get(checksum, {})
                filters = profile_data.get("filters", {})
                
                if group_by_bank:
                    return self._group_filters_by_bank(filters)
                else:
                    return filters
            else:
                if group_by_bank:
                    # Group filters for all profiles
                    grouped_store = {}
                    for profile_checksum, profile_data in store.items():
                        filters = profile_data.get("filters", {})
                        grouped_store[profile_checksum] = self._group_filters_by_bank(filters)
                    return grouped_store
                else:
                    # Return only filters from all profiles
                    filters_only = {}
                    for profile_checksum, profile_data in store.items():
                        filters = profile_data.get("filters", {})
                        if filters:  # Only include profiles that have filters
                            filters_only[profile_checksum] = filters
                    return filters_only
        except Exception as e:
            logging.error(f"Error getting stored filters: {str(e)}")
            return {}
    
    # Backward compatibility methods
    def load(self):
        """Legacy method - load store data in old format for compatibility"""
        store = self.load_store()
        # Convert new format back to old format for compatibility
        legacy_store = {}
        for checksum, profile_data in store.items():
            if "filters" in profile_data:
                legacy_store[checksum] = profile_data["filters"]
            else:
                legacy_store[checksum] = {}
        return legacy_store
    
    def save(self, legacy_data):
        """Legacy method - save data in old format for compatibility"""
        # Convert legacy format to new format
        new_store = {}
        for checksum, filters in legacy_data.items():
            new_store[checksum] = {"filters": filters, "memory": {}}
        return self.save_store(new_store)
    
    def _group_filters_by_bank(self, filters):
        """
        Group filters by their base address (bank)
        
        Args:
            filters (dict): Individual filters keyed by filter_key
            
        Returns:
            dict: Filters grouped by bank address
        """
        banks = {}
        
        for filter_key, filter_data in filters.items():
            address = filter_data.get("address", "")
            offset = filter_data.get("offset", 0)
            
            # Use the base address as the bank key
            if address not in banks:
                banks[address] = []
            
            # Add filter to the bank array, sorted by offset
            banks[address].append({
                "offset": offset,
                "filter": filter_data.get("filter", {}),
                "timestamp": filter_data.get("timestamp", 0)
            })
        
        # Sort filters within each bank by offset
        for bank_address in banks:
            banks[bank_address].sort(key=lambda f: f["offset"])
        
        return banks
        """
        Group filters by their base address (bank)
        
        Args:
            filters (dict): Individual filters keyed by filter_key
            
        Returns:
            dict: Filters grouped by bank address
        """
        banks = {}
        
        for filter_key, filter_data in filters.items():
            address = filter_data.get("address", "")
            offset = filter_data.get("offset", 0)
            
            # Use the base address as the bank key
            if address not in banks:
                banks[address] = []
            
            # Add filter to the bank array, sorted by offset
            banks[address].append({
                "offset": offset,
                "filter": filter_data.get("filter", {}),
                "timestamp": filter_data.get("timestamp", 0)
            })
        
        # Sort filters within each bank by offset
        for bank_address in banks:
            banks[bank_address].sort(key=lambda f: f["offset"])
        
        return banks
    
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
                # Delete all filters for all profiles, but keep memory settings
                store = self.load_store()
                for checksum in store:
                    if "filters" in store[checksum]:
                        store[checksum]["filters"] = {}
                
                if self.save_store(store):
                    return True, "All filters deleted"
                else:
                    return False, "Failed to delete filters"
            
            elif checksum:
                # Normalize checksum to uppercase
                checksum = self.normalize_checksum(checksum)
                
                store = self.load_store()
                
                if checksum not in store:
                    return False, f"No settings found for profile checksum '{checksum}'"
                
                # Ensure filters section exists
                if "filters" not in store[checksum]:
                    store[checksum]["filters"] = {}
                
                if address:
                    # Delete specific filter
                    filter_key = str(address)
                    if filter_key in store[checksum]["filters"]:
                        del store[checksum]["filters"][filter_key]
                        if self.save_store(store):
                            return True, f"Filter at {address} deleted from profile checksum '{checksum}'"
                        else:
                            return False, "Failed to save changes"
                    else:
                        return False, f"No filter found at address '{address}' for profile checksum '{checksum}'"
                else:
                    # Delete all filters for the profile checksum, but keep memory settings
                    store[checksum]["filters"] = {}
                    if self.save_store(store):
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
            # Normalize checksum to uppercase
            checksum = self.normalize_checksum(checksum)
            filters = self.load_filters(checksum)
            return len(filters)
        except Exception as e:
            logging.error(f"Error getting filter count for profile checksum '{checksum}': {str(e)}")
            return 0
    
    def get_all_profile_checksums(self):
        """
        Get all profile checksums that have settings stored
        
        Returns:
            list: List of profile checksums
        """
        try:
            store = self.load_store()
            return list(store.keys())
        except Exception as e:
            logging.error(f"Error getting profile checksums: {str(e)}")
            return []
    
    def get_profile_info_by_checksum(self, checksum):
        """
        Get all settings for a specific checksum
        
        Args:
            checksum (str): DSP profile checksum
            
        Returns:
            dict: Settings for the checksum (both filters and memory)
        """
        try:
            # Normalize checksum to uppercase
            checksum = self.normalize_checksum(checksum)
            store = self.load_store()
            return store.get(checksum, {"filters": {}, "memory": {}})
        except Exception as e:
            logging.error(f"Error getting settings for checksum '{checksum}': {str(e)}")
            return {"filters": {}, "memory": {}}
    
    def clear_empty_profiles(self):
        """
        Remove profiles that have no settings stored
        
        Returns:
            tuple: (success: bool, removed_count: int)
        """
        try:
            store = self.load_store()
            original_count = len(store)
            
            # Remove empty profile sections
            cleaned_store = {}
            for checksum, profile_data in store.items():
                # Check if profile has any filters or memory settings
                has_filters = bool(profile_data.get("filters", {}))
                has_memory = bool(profile_data.get("memory", {}))
                
                if has_filters or has_memory:
                    cleaned_store[checksum] = profile_data
            
            if self.save_store(cleaned_store):
                removed_count = original_count - len(cleaned_store)
                return True, removed_count
            else:
                return False, 0
                
        except Exception as e:
            logging.error(f"Error clearing empty profiles: {str(e)}")
            return False, 0
    
    def set_filter_bypass(self, checksum, address, offset, bypassed):
        """
        Set the bypass state of a specific filter
        
        Args:
            checksum (str): DSP profile checksum
            address (str): Memory address or metadata key
            offset (int): Offset value
            bypassed (bool): True to bypass, False to enable
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # Normalize checksum to uppercase
            checksum = self.normalize_checksum(checksum)
            
            store = self.load_store()
            
            if checksum not in store:
                return False, f"No settings found for profile checksum '{checksum}'"
            
            if "filters" not in store[checksum]:
                store[checksum]["filters"] = {}
            
            filter_key = f"{address}_{offset}"
            
            if filter_key not in store[checksum]["filters"]:
                return False, f"No filter found at address '{address}' with offset {offset}"
            
            # Update bypass state
            store[checksum]["filters"][filter_key]["bypassed"] = bypassed
            store[checksum]["filters"][filter_key]["timestamp"] = time.time()
            
            if self.save_store(store):
                state = "bypassed" if bypassed else "enabled"
                return True, f"Filter at {address}+{offset} {state}"
            else:
                return False, "Failed to save bypass state"
                
        except Exception as e:
            logging.error(f"Error setting filter bypass: {str(e)}")
            return False, str(e)
    
    def get_filter_bypass_state(self, checksum, address, offset):
        """
        Get the bypass state of a specific filter
        
        Args:
            checksum (str): DSP profile checksum
            address (str): Memory address or metadata key
            offset (int): Offset value
            
        Returns:
            bool: True if bypassed, False if enabled, None if not found
        """
        try:
            # Normalize checksum to uppercase
            checksum = self.normalize_checksum(checksum)
            
            store = self.load_store()
            
            if checksum not in store:
                return None
            
            if "filters" not in store[checksum]:
                return None
            
            filter_key = f"{address}_{offset}"
            
            if filter_key not in store[checksum]["filters"]:
                return None
            
            return store[checksum]["filters"][filter_key].get("bypassed", False)
            
        except Exception as e:
            logging.error(f"Error getting filter bypass state: {str(e)}")
            return None
    
    def toggle_filter_bypass(self, checksum, address, offset):
        """
        Toggle the bypass state of a specific filter
        
        Args:
            checksum (str): DSP profile checksum
            address (str): Memory address or metadata key
            offset (int): Offset value
            
        Returns:
            tuple: (success: bool, new_state: bool, message: str)
        """
        try:
            # Normalize checksum to uppercase
            checksum = checksum.upper()
            
            current_state = self.get_filter_bypass_state(checksum, address, offset)
            
            if current_state is None:
                return False, False, f"Filter not found at {address}+{offset}"
            
            new_state = not current_state
            success, message = self.set_filter_bypass(checksum, address, offset, new_state)
            
            return success, new_state, message
            
        except Exception as e:
            logging.error(f"Error toggling filter bypass: {str(e)}")
            return False, False, str(e)
    
    def set_filter_bank_bypass(self, checksum, address, bypassed):
        """
        Set the bypass state of all filters in a filter bank (same address)
        
        Args:
            checksum (str): DSP profile checksum
            address (str): Memory address or metadata key
            bypassed (bool): True to bypass, False to enable
            
        Returns:
            tuple: (success_count: int, total_count: int, message: str)
        """
        try:
            # Normalize checksum to uppercase
            checksum = self.normalize_checksum(checksum)
            
            store = self.load_store()
            
            if checksum not in store:
                return 0, 0, f"No settings found for profile checksum '{checksum}'"
            
            if "filters" not in store[checksum]:
                store[checksum]["filters"] = {}
            
            # Find all filters with the same address
            bank_filters = []
            for filter_key, filter_data in store[checksum]["filters"].items():
                if filter_data.get("address") == address:
                    bank_filters.append(filter_key)
            
            if not bank_filters:
                return 0, 0, f"No filters found for address '{address}'"
            
            # Update bypass state for all filters in the bank
            success_count = 0
            for filter_key in bank_filters:
                store[checksum]["filters"][filter_key]["bypassed"] = bypassed
                store[checksum]["filters"][filter_key]["timestamp"] = time.time()
                success_count += 1
            
            if self.save_store(store):
                state = "bypassed" if bypassed else "enabled"
                return success_count, len(bank_filters), f"Filter bank at {address} {state} ({success_count} filters)"
            else:
                return 0, len(bank_filters), "Failed to save bypass state"
                
        except Exception as e:
            logging.error(f"Error setting filter bank bypass: {str(e)}")
            return 0, 0, str(e)
    
    def get_filter_bank_bypass_states(self, checksum, address):
        """
        Get the bypass states of all filters in a filter bank
        
        Args:
            checksum (str): DSP profile checksum
            address (str): Memory address or metadata key
            
        Returns:
            list: List of dictionaries with offset and bypass state, or empty list if not found
        """
        try:
            # Normalize checksum to uppercase
            checksum = self.normalize_checksum(checksum)
            
            store = self.load_store()
            
            if checksum not in store:
                return []
            
            if "filters" not in store[checksum]:
                return []
            
            bank_filters = []
            for filter_key, filter_data in store[checksum]["filters"].items():
                if filter_data.get("address") == address:
                    bank_filters.append({
                        "offset": filter_data.get("offset", 0),
                        "bypassed": filter_data.get("bypassed", False),
                        "filter_key": filter_key,
                        "timestamp": filter_data.get("timestamp", 0)
                    })
            
            # Sort by offset
            bank_filters.sort(key=lambda x: x["offset"])
            return bank_filters
            
        except Exception as e:
            logging.error(f"Error getting filter bank bypass states: {str(e)}")
            return []
    
    def validate_and_repair(self):
        """
        Validate the settings store file and attempt to repair it if corrupted
        
        Returns:
            tuple: (is_valid: bool, was_repaired: bool, message: str)
        """
        try:
            if not os.path.exists(self.store_file):
                return True, False, "Settings store file does not exist (will be created on first write)"
            
            # Try to load the file
            try:
                with open(self.store_file, 'r') as f:
                    content = f.read().strip()
                    if not content:
                        return True, False, "Settings store file is empty"
                    
                    # Try to parse as JSON
                    data = json.loads(content)
                    
                    # Validate structure
                    if not isinstance(data, dict):
                        return False, False, "Settings store root is not a dictionary"
                    
                    # Validate each profile section
                    for checksum, profile_data in data.items():
                        if not isinstance(profile_data, dict):
                            logging.warning(f"Profile {checksum} data is not a dictionary")
                            continue
                        
                        # Check for new format (with filters/memory sections)
                        if "filters" in profile_data or "memory" in profile_data:
                            # New format validation
                            if "filters" in profile_data:
                                filters = profile_data["filters"]
                                if not isinstance(filters, dict):
                                    logging.warning(f"Profile {checksum} filters section is not a dictionary")
                                    continue
                                
                                for filter_key, filter_data in filters.items():
                                    if not isinstance(filter_data, dict):
                                        logging.warning(f"Filter {filter_key} in profile {checksum} is not a dictionary")
                                        continue
                                    
                                    # Check for required fields
                                    required_fields = ['address', 'offset', 'filter']
                                    missing_fields = [field for field in required_fields if field not in filter_data]
                                    if missing_fields:
                                        logging.warning(f"Filter {filter_key} in profile {checksum} missing fields: {missing_fields}")
                            
                            if "memory" in profile_data:
                                memory = profile_data["memory"]
                                if not isinstance(memory, dict):
                                    logging.warning(f"Profile {checksum} memory section is not a dictionary")
                                    continue
                                
                                for mem_key, mem_data in memory.items():
                                    if not isinstance(mem_data, dict):
                                        logging.warning(f"Memory {mem_key} in profile {checksum} is not a dictionary")
                                        continue
                                    
                                    # Check for required fields
                                    required_fields = ['address', 'values']
                                    missing_fields = [field for field in required_fields if field not in mem_data]
                                    if missing_fields:
                                        logging.warning(f"Memory {mem_key} in profile {checksum} missing fields: {missing_fields}")
                        else:
                            # Legacy format validation
                            for filter_key, filter_data in profile_data.items():
                                if not isinstance(filter_data, dict):
                                    logging.warning(f"Filter {filter_key} in profile {checksum} is not a dictionary")
                                    continue
                                
                                # Check for required fields in legacy format
                                required_fields = ['address', 'offset', 'filter']
                                missing_fields = [field for field in required_fields if field not in filter_data]
                                if missing_fields:
                                    logging.warning(f"Filter {filter_key} in profile {checksum} missing fields: {missing_fields}")
                    
                    return True, False, "Settings store is valid"
                    
            except json.JSONDecodeError as e:
                # Try to repair the JSON
                logging.warning(f"JSON decode error: {e.msg} at line {e.lineno}, column {e.colno}")
                
                # Read the file content
                with open(self.store_file, 'r') as f:
                    content = f.read()
                
                # Attempt simple repairs
                repaired = False
                original_content = content
                
                # Fix common JSON issues
                # 1. Remove trailing commas
                import re
                content = re.sub(r',\s*}', '}', content)
                content = re.sub(r',\s*]', ']', content)
                
                # 2. Fix missing quotes around keys (basic attempt)
                content = re.sub(r'(\w+):', r'"\1":', content)
                
                # 3. Try to parse again
                try:
                    json.loads(content)
                    # If successful, save the repaired version
                    backup_file = self.store_file + f".original.{int(time.time())}"
                    with open(backup_file, 'w') as f:
                        f.write(original_content)
                    
                    with open(self.store_file, 'w') as f:
                        f.write(content)
                    
                    logging.info(f"Successfully repaired settings store. Original backed up to {backup_file}")
                    return True, True, f"Settings store repaired. Original backed up to {backup_file}"
                    
                except json.JSONDecodeError:
                    # Repair failed, move corrupted file and start fresh
                    backup_file = self.store_file + f".corrupted.{int(time.time())}"
                    os.rename(self.store_file, backup_file)
                    logging.warning(f"Could not repair settings store. Corrupted file moved to {backup_file}")
                    return False, True, f"Could not repair settings store. Corrupted file moved to {backup_file}, will start with empty store"
                    
        except Exception as e:
            logging.error(f"Error validating settings store: {str(e)}")
            return False, False, f"Error during validation: {str(e)}"
