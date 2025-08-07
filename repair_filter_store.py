#!/usr/bin/env python3
"""
Filter Store Repair Utility

This utility repairs corrupted filter store JSON files by:
1. Detecting and fixing extra braces
2. Normalizing checksum keys to uppercase
3. Merging duplicate entries with different case
4. Validating JSON structure
"""

import os
import json
import time
import sys
import logging
import re

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def fix_json_corruption(content):
    """Fix common JSON corruption issues"""
    # Count opening and closing braces
    open_braces = content.count('{')
    close_braces = content.count('}')
    
    if close_braces > open_braces:
        # Remove extra closing braces from the end
        extra_braces = close_braces - open_braces
        logging.info(f"Detected {extra_braces} extra closing braces, fixing...")
        
        # Remove trailing braces and whitespace
        content = content.rstrip()
        for _ in range(extra_braces):
            if content.endswith('}'):
                content = content[:-1].rstrip()
    
    # Remove trailing commas before closing braces/brackets
    content = re.sub(r',\s*}', '}', content)
    content = re.sub(r',\s*]', ']', content)
    
    return content

def normalize_checksums(data):
    """Normalize checksum keys to uppercase and merge duplicates"""
    normalized_data = {}
    
    for checksum, filters in data.items():
        normalized_checksum = checksum.upper()
        
        if normalized_checksum in normalized_data:
            # Merge duplicate checksums
            logging.info(f"Merging duplicate checksum: {checksum} -> {normalized_checksum}")
            for filter_key, filter_data in filters.items():
                if filter_key not in normalized_data[normalized_checksum]:
                    normalized_data[normalized_checksum][filter_key] = filter_data
                else:
                    # Keep the newer one based on timestamp
                    existing_timestamp = normalized_data[normalized_checksum][filter_key].get("timestamp", 0)
                    new_timestamp = filter_data.get("timestamp", 0)
                    if new_timestamp > existing_timestamp:
                        logging.info(f"Keeping newer version of filter {filter_key}")
                        normalized_data[normalized_checksum][filter_key] = filter_data
                    else:
                        logging.info(f"Keeping existing version of filter {filter_key}")
        else:
            normalized_data[normalized_checksum] = filters
    
    return normalized_data

def repair_filter_store(file_path):
    """Repair a corrupted filter store file"""
    if not os.path.exists(file_path):
        logging.error(f"File does not exist: {file_path}")
        return False
    
    # Create backup
    backup_file = f"{file_path}.backup.{int(time.time())}"
    try:
        with open(file_path, 'r') as src, open(backup_file, 'w') as dst:
            dst.write(src.read())
        logging.info(f"Created backup: {backup_file}")
    except Exception as e:
        logging.error(f"Failed to create backup: {e}")
        return False
    
    # Read and attempt to repair the file
    try:
        with open(file_path, 'r') as f:
            content = f.read().strip()
        
        if not content:
            logging.warning("File is empty")
            return True
        
        logging.info(f"Original file size: {len(content)} characters")
        
        # Fix JSON corruption
        fixed_content = fix_json_corruption(content)
        
        if fixed_content != content:
            logging.info("Applied JSON corruption fixes")
        
        # Try to parse the JSON
        try:
            data = json.loads(fixed_content)
        except json.JSONDecodeError as e:
            logging.error(f"JSON is still invalid after basic repairs: {e}")
            return False
        
        # Normalize checksums
        normalized_data = normalize_checksums(data)
        
        changes_made = (normalized_data != data) or (fixed_content != content)
        
        if changes_made:
            # Write the repaired data
            with open(file_path, 'w') as f:
                json.dump(normalized_data, f, indent=2, ensure_ascii=False)
            
            logging.info(f"Repaired filter store saved to: {file_path}")
            
            # Validate the repaired file
            try:
                with open(file_path, 'r') as f:
                    json.load(f)
                logging.info("Repair validation successful - JSON is now valid")
            except json.JSONDecodeError as e:
                logging.error(f"Repair validation failed: {e}")
                return False
        else:
            logging.info("No repairs needed - file is already valid")
        
        # Show summary
        profile_count = len(normalized_data)
        total_filters = sum(len(filters) for filters in normalized_data.values())
        logging.info(f"Summary: {profile_count} profiles, {total_filters} total filters")
        
        return True
        
    except Exception as e:
        logging.error(f"Error during repair: {e}")
        return False

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 repair_filter_store.py <path_to_filters.json>")
        print("Example: python3 repair_filter_store.py /var/lib/hifiberry/filters.json")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    logging.info(f"Repairing filter store: {file_path}")
    
    if repair_filter_store(file_path):
        logging.info("Repair completed successfully")
        sys.exit(0)
    else:
        logging.error("Repair failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
