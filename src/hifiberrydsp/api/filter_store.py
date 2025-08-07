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


class FilterStore:
    """
    Manages the filter store for DSP profiles.
    
    The filter store saves and retrieves filter configurations organized by DSP profile.
    Filters are stored in a JSON file at /var/lib/hifiberry/filters.json.
    """
    
    def __init__(self, profiles_dir="/usr/share/hifiberry/dspprofiles"):
        """
        Initialize the FilterStore
        
        Args:
            profiles_dir (str): Directory where DSP profiles are stored (kept for compatibility)
        """
        self.profiles_dir = profiles_dir
        self.store_file = "/var/lib/hifiberry/filters.json"
    
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
                content = f.read().strip()
                if not content:
                    logging.warning("Filter store file is empty, creating new store")
                    return {}
                
                # Check for and fix common corruption issues
                content = self._fix_json_corruption(content)
                
                data = json.loads(content)
                
                # Normalize checksum keys to uppercase to prevent duplicates
                normalized_data = {}
                for checksum, filters in data.items():
                    normalized_checksum = checksum.upper()
                    if normalized_checksum in normalized_data:
                        # Merge duplicate checksums (same checksum in different cases)
                        logging.warning(f"Found duplicate checksum with different case: {checksum} -> {normalized_checksum}")
                        for filter_key, filter_data in filters.items():
                            if filter_key not in normalized_data[normalized_checksum]:
                                normalized_data[normalized_checksum][filter_key] = filter_data
                            else:
                                # Keep the newer one based on timestamp
                                existing_timestamp = normalized_data[normalized_checksum][filter_key].get("timestamp", 0)
                                new_timestamp = filter_data.get("timestamp", 0)
                                if new_timestamp > existing_timestamp:
                                    normalized_data[normalized_checksum][filter_key] = filter_data
                    else:
                        normalized_data[normalized_checksum] = filters
                
                # Save normalized data if changes were made
                if normalized_data != data:
                    logging.info("Normalizing checksums and removing duplicates in filter store")
                    self.save(normalized_data)
                
                return normalized_data
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error in filter store at line {e.lineno}, column {e.colno}: {e.msg}")
            # Try to recover by backing up the corrupted file and starting fresh
            try:
                backup_file = self.store_file + f".corrupted.{int(time.time())}"
                os.rename(self.store_file, backup_file)
                logging.warning(f"Corrupted filter store backed up to {backup_file}, starting with empty store")
            except Exception as backup_e:
                logging.error(f"Could not backup corrupted filter store: {backup_e}")
            return {}
        except Exception as e:
            logging.error(f"Error loading filter store: {str(e)}")
            return {}
    
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
    
    def save(self, store_data):
        """
        Save the filter store to disk atomically with file locking
        
        Args:
            store_data (dict): The filter store data to save
            
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
            logging.error(f"Error saving filter store: {str(e)}")
            # Clean up temp file if it exists
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
            return False
    
    def store_filter(self, checksum, address, offset, filter_data, bypassed=False):
        """
        Store a filter in the filter store organized by profile checksum
        
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
            checksum = checksum.upper()
            
            store = self.load()
            
            # Initialize checksum section if it doesn't exist
            if checksum not in store:
                store[checksum] = {}
            
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
            if filter_key in store[checksum] and "bypassed" in store[checksum][filter_key]:
                # Preserve existing bypass state if not explicitly set
                existing_bypass = store[checksum][filter_key].get("bypassed", False)
                filter_entry["bypassed"] = existing_bypass
            
            store[checksum][filter_key] = filter_entry
            
            return self.save(store)
        except Exception as e:
            logging.error(f"Error storing filter: {str(e)}")
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
            store = self.load()
            
            if checksum:
                # Normalize checksum to uppercase
                checksum = checksum.upper()
                filters = store.get(checksum, {})
                
                if group_by_bank:
                    return self._group_filters_by_bank(filters)
                else:
                    return filters
            else:
                if group_by_bank:
                    # Group filters for all profiles
                    grouped_store = {}
                    for profile_checksum, filters in store.items():
                        grouped_store[profile_checksum] = self._group_filters_by_bank(filters)
                    return grouped_store
                else:
                    return store
        except Exception as e:
            logging.error(f"Error getting stored filters: {str(e)}")
            return {}
    
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
                # Normalize checksum to uppercase
                checksum = checksum.upper()
                
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
            # Normalize checksum to uppercase
            checksum = checksum.upper()
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
            # Normalize checksum to uppercase
            checksum = checksum.upper()
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
            checksum = checksum.upper()
            
            store = self.load()
            
            if checksum not in store:
                return False, f"No filters found for profile checksum '{checksum}'"
            
            filter_key = f"{address}_{offset}"
            
            if filter_key not in store[checksum]:
                return False, f"No filter found at address '{address}' with offset {offset}"
            
            # Update bypass state
            store[checksum][filter_key]["bypassed"] = bypassed
            store[checksum][filter_key]["timestamp"] = time.time()
            
            if self.save(store):
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
            checksum = checksum.upper()
            
            store = self.load()
            
            if checksum not in store:
                return None
            
            filter_key = f"{address}_{offset}"
            
            if filter_key not in store[checksum]:
                return None
            
            return store[checksum][filter_key].get("bypassed", False)
            
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
            checksum = checksum.upper()
            
            store = self.load()
            
            if checksum not in store:
                return 0, 0, f"No filters found for profile checksum '{checksum}'"
            
            # Find all filters with the same address
            bank_filters = []
            for filter_key, filter_data in store[checksum].items():
                if filter_data.get("address") == address:
                    bank_filters.append(filter_key)
            
            if not bank_filters:
                return 0, 0, f"No filters found for address '{address}'"
            
            # Update bypass state for all filters in the bank
            success_count = 0
            for filter_key in bank_filters:
                store[checksum][filter_key]["bypassed"] = bypassed
                store[checksum][filter_key]["timestamp"] = time.time()
                success_count += 1
            
            if self.save(store):
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
            checksum = checksum.upper()
            
            store = self.load()
            
            if checksum not in store:
                return []
            
            bank_filters = []
            for filter_key, filter_data in store[checksum].items():
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
        Validate the filter store file and attempt to repair it if corrupted
        
        Returns:
            tuple: (is_valid: bool, was_repaired: bool, message: str)
        """
        try:
            if not os.path.exists(self.store_file):
                return True, False, "Filter store file does not exist (will be created on first write)"
            
            # Try to load the file
            try:
                with open(self.store_file, 'r') as f:
                    content = f.read().strip()
                    if not content:
                        return True, False, "Filter store file is empty"
                    
                    # Try to parse as JSON
                    data = json.loads(content)
                    
                    # Validate structure
                    if not isinstance(data, dict):
                        return False, False, "Filter store root is not a dictionary"
                    
                    # Validate each profile section
                    for checksum, filters in data.items():
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
                    
                    return True, False, "Filter store is valid"
                    
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
                    
                    logging.info(f"Successfully repaired filter store. Original backed up to {backup_file}")
                    return True, True, f"Filter store repaired. Original backed up to {backup_file}"
                    
                except json.JSONDecodeError:
                    # Repair failed, move corrupted file and start fresh
                    backup_file = self.store_file + f".corrupted.{int(time.time())}"
                    os.rename(self.store_file, backup_file)
                    logging.warning(f"Could not repair filter store. Corrupted file moved to {backup_file}")
                    return False, True, f"Could not repair filter store. Corrupted file moved to {backup_file}, will start with empty store"
                    
        except Exception as e:
            logging.error(f"Error validating filter store: {str(e)}")
            return False, False, f"Error during validation: {str(e)}"
