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
import binascii
import time
import requests
from flask import Flask, jsonify, request
from hifiberrydsp.parser.xmlprofile import XmlProfile, get_default_dspprofile_path
from hifiberrydsp.api.filters import Filter
from hifiberrydsp.api.settings_store import SettingsStore
from hifiberrydsp import __version__
from waitress import serve
import numpy as np
from hifiberrydsp.hardware.adau145x import Adau145x
from hifiberrydsp.filtering.biquad import Biquad


DEFAULT_PORT = 13141
DEFAULT_HOST = "localhost"
PROFILES_DIR = "/usr/share/hifiberry/dspprofiles"

# Initialize filter store
settings_store = SettingsStore(PROFILES_DIR)

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Cache for XML profile
_xml_profile_cache = {
    "profile": None,
    "path": None,
    "metadata": None,
    "valid": None
}

# Cache for current DSP program checksum
_checksum_cache = {
    "md5": None,       # MD5 checksum (signature-based)
    "sha1": None,      # SHA-1 checksum (length-based)
    "program_length": None,  # Program length for cache validation
}


def isBiquad(value):
    """
    Check if a value follows the format xxx/yy where xxx and yy are integers,
    and yy is a multiple of 5.
    
    Args:
        value (str): The string to check
        
    Returns:
        bool: True if the string matches the required format, False otherwise
    """
    try:
        if '/' not in value:
            return False
            
        parts = value.split('/')
        if len(parts) != 2:
            return False
            
        xxx = int(parts[0])
        yy = int(parts[1])
        
        # Check if yy is a multiple of 5
        return yy % 5 == 0
    except ValueError:
        # If conversion to int fails
        return False


def get_xml_profile():
    """
    Get the cached XML profile or read from disk if needed.
    Validates that the XML profile's checksum matches what's in memory.
    
    Returns:
        XmlProfile: The cached or newly read XML profile, or None if invalid or not found
    """
    global _xml_profile_cache
    
    profile_path = get_default_dspprofile_path()
    
    # Check if file exists
    if not os.path.exists(profile_path):
        return None
    
    # Check if we need to refresh the cache
    cache_valid = (
        _xml_profile_cache["profile"] is not None and
        _xml_profile_cache["path"] == profile_path
    )
    
    # If we have a cached profile, check if it's valid or invalid
    if cache_valid:
        logging.debug("XML profile cache hit")
        if _xml_profile_cache["valid"] is False:
            logging.warning("Cached XML profile is marked as invalid (checksum mismatch) - returning None")
            return None
        return _xml_profile_cache["profile"]
    
    # Cache miss - read from disk
    logging.debug("XML profile cache miss - reading from disk")
    try:
        xml_profile = XmlProfile(profile_path)
        
        # Validate checksum - compare memory checksums with XML profile checksums
        profile_valid = True
        try:
            # Get memory checksums using the same approach as /program-info endpoint
            # MD5 from signature-based mode, SHA-1 from length-based mode
            signature_checksums = Adau145x.calculate_program_checksums(mode="signature", algorithms=["md5"], cached=True)
            length_checksums = Adau145x.calculate_program_checksums(mode="length", algorithms=["sha1"], cached=True)
                
            memory_checksum_md5 = signature_checksums.get("md5") if signature_checksums else None
            memory_checksum_sha1 = length_checksums.get("sha1") if length_checksums else None
                
            # Get XML profile checksums
            profile_checksum_sha1 = xml_profile.get_meta("checksum_sha1")
            profile_checksum_md5 = xml_profile.get_meta("checksum")
            
            # Only validate if we have both memory and profile checksums
            checksum_match = None  # None means validation not possible
            
            # Check SHA-1 first if both are available
            if profile_checksum_sha1 and memory_checksum_sha1:
                if profile_checksum_sha1.lower() == memory_checksum_sha1.lower():
                    checksum_match = True
                    logging.debug(f"SHA-1 checksum match - Memory: {memory_checksum_sha1}, XML: {profile_checksum_sha1}")
                else:
                    checksum_match = False
                    logging.warning(f"SHA-1 checksum mismatch - Memory: {memory_checksum_sha1}, XML: {profile_checksum_sha1}")
            
            # Fall back to MD5 if SHA-1 validation didn't happen or failed
            elif profile_checksum_md5 and memory_checksum_md5:
                if profile_checksum_md5.lower() == memory_checksum_md5.lower():
                    checksum_match = True
                    logging.debug(f"MD5 checksum match - Memory: {memory_checksum_md5}, XML: {profile_checksum_md5}")
                else:
                    checksum_match = False
                    logging.warning(f"MD5 checksum mismatch - Memory: {memory_checksum_md5}, XML: {profile_checksum_md5}")
            
            # Set profile validity based on checksum results
            if checksum_match is None:
                # Can't validate (checksums not available) - assume valid
                if not memory_checksum_md5 and not memory_checksum_sha1:
                    logging.info("Memory checksums not available (not cached yet) - assuming profile is valid")
                elif not profile_checksum_md5 and not profile_checksum_sha1:
                    logging.info("XML profile has no checksums - cannot validate against memory")
                else:
                    logging.info("Partial checksum data available - cannot validate reliably")
                profile_valid = True
            else:
                # We have validation result - use it
                profile_valid = checksum_match
                
        except Exception as e:
            logging.error(f"Error validating checksums: {str(e)}")
            # If we can't validate, assume it's valid rather than blocking
            profile_valid = True
        
        # Update the cache
        _xml_profile_cache["profile"] = xml_profile
        _xml_profile_cache["path"] = profile_path
        _xml_profile_cache["metadata"] = None  # Reset metadata cache
        _xml_profile_cache["valid"] = profile_valid
        
        # Return profile if valid, None if invalid
        if profile_valid:
            return xml_profile
        else:
            return None
            
    except Exception as e:
        logging.error(f"Error reading XML profile: {str(e)}")
        return None


def get_profile_metadata():
    """
    Retrieve metadata from the active DSP profile by reading the XML file (using cache when possible).

    Returns:
        Dictionary containing metadata from the DSP profile
    """
    global _xml_profile_cache
    
    try:
        # Check if we have cached metadata
        if _xml_profile_cache["metadata"] is not None:
            logging.debug("Using cached metadata")
            return _xml_profile_cache["metadata"]
        
        metadata = {}

        # Calculate program checksum
        try:
            checksum_bytes = Adau145x.calculate_program_checksum(cached=True)
            if checksum_bytes:
                checksum_hex = binascii.hexlify(checksum_bytes).decode('utf-8')
                metadata["checksum"] = checksum_hex
        except Exception as e:
            logging.warning(f"Could not get checksum: {str(e)}")

        # Get XML profile from cache or disk
        xml_profile = get_xml_profile()
        if not xml_profile:
            return {"error": "DSP profile file not found or invalid"}
        
        # Extract metadata from XML
        for k in xml_profile.get_meta_keys():
            logging.debug("Meta key: %s", k)
            metadata[k] = xml_profile.get_meta(k)
        
        # Add system metadata
        metadata["_system"] = {
            "profileName": xml_profile.get_meta("profileName") or "Unknown Profile",
            "profileVersion": xml_profile.get_meta("profileVersion") or "Unknown Version",
            "sampleRate": xml_profile.samplerate()
        }
        
        # Cache the metadata
        _xml_profile_cache["metadata"] = metadata
        
        return metadata

    except Exception as e:
        logging.error(f"Error getting metadata: {str(e)}")
        return {"error": str(e)}


def invalidate_cache():
    """
    Invalidate the XML profile cache and checksum cache
    """
    global _xml_profile_cache, _checksum_cache
    _xml_profile_cache["profile"] = None
    _xml_profile_cache["metadata"] = None
    _xml_profile_cache["valid"] = None
    
    # Also clear the checksum cache when invalidating
    clear_checksum_cache()


def get_or_guess_samplerate():
    """
    Get the sample rate from the profile metadata or try to guess it from the DSP registers.
    Falls back to default 48000 Hz if not available.
    
    Returns:
        int: Sample rate in Hz
    """
    sample_rate = None
    try:
        metadata = get_profile_metadata()
        if "_system" in metadata and "sampleRate" in metadata["_system"]:
            sample_rate = metadata["_system"]["sampleRate"]
            logging.debug("Using sample rate from profile metadata: %d", sample_rate)
        else:
            sample_rate = Adau145x.guess_samplerate()
            if sample_rate is None:
                logging.warning("Could not guess sample rate from DSP registers, and none given in DSP profile")
            else:
                logging.debug("Using guessed sample rate from DSP registers: %d", sample_rate)
    except Exception as e:
        logging.warning(f"Could not get sample rate from profile, using default: {str(e)}")
    
    if sample_rate is None:
        sample_rate = 48000
        
    return sample_rate


def get_current_profile_name():
    """
    Get the name of the currently active DSP profile
    
    Returns:
        str: Profile name or "default" if not found
    """
    try:
        metadata = get_profile_metadata()
        if metadata and "_system" in metadata and "profileName" in metadata["_system"]:
            profile_name = metadata["_system"]["profileName"]
            if profile_name and profile_name != "Unknown Profile":
                return profile_name
    except Exception as e:
        logging.warning(f"Error getting profile name: {str(e)}")
    
    return "default"


def clear_checksum_cache():
    """
    Clear the cached checksums and program length. This should be called when a new DSP program is installed.
    """
    global _checksum_cache
    _checksum_cache["md5"] = None
    _checksum_cache["sha1"] = None
    _checksum_cache["program_length"] = None
    logging.debug("Checksum cache cleared")


def is_checksum_cache_valid():
    """
    Check if the checksum cache is still valid by comparing current program length
    with the cached program length.
    
    Returns:
        bool: True if cache is valid, False if it should be invalidated
    """
    global _checksum_cache
    
    # If no cached program length, consider invalid
    if _checksum_cache["program_length"] is None:
        return False
    
    try:
        # Get current program length
        current_length = Adau145x.get_program_len()
        
        # Compare with cached length
        if current_length != _checksum_cache["program_length"]:
            logging.debug(f"Program length changed: cached={_checksum_cache['program_length']}, current={current_length}")
            return False
        
        return True
    except Exception as e:
        logging.error(f"Error checking program length for cache validation: {str(e)}")
        return False


def get_current_program_checksum():
    """
    Get the MD5 checksum of the currently active DSP profile (signature-based, for backward compatibility)
    
    Returns:
        str: Profile MD5 checksum or None if not found
    """
    global _checksum_cache
    
    # Check if cache is valid and we have cached MD5 checksum
    if _checksum_cache["md5"] is not None and is_checksum_cache_valid():
        logging.debug("Using cached MD5 checksum")
        return _checksum_cache["md5"]
    
    # Clear invalid cache
    if not is_checksum_cache_valid():
        logging.debug("Cache invalidated due to program length change")
        clear_checksum_cache()
    
    try:
        # Get current program length for cache validation
        program_length = Adau145x.get_program_len()
        
        # Calculate MD5 checksum (signature-based)
        checksum_bytes = Adau145x.calculate_program_checksum(cached=True)
        if checksum_bytes:
            checksum_hex = binascii.hexlify(checksum_bytes).decode('utf-8').upper()
            _checksum_cache["md5"] = checksum_hex
            _checksum_cache["program_length"] = program_length
            logging.debug(f"Calculated and cached MD5 checksum: {checksum_hex} (program length: {program_length})")
            return checksum_hex
        else:
            logging.warning("Could not calculate MD5 checksum")
            return None
    except Exception as e:
        logging.error(f"Error calculating MD5 checksum: {str(e)}")
        return None


def get_current_program_checksum_sha1():
    """
    Get the SHA-1 checksum of the currently active DSP profile (length-based, for internal use)
    
    Returns:
        str: Profile SHA-1 checksum or None if not found
    """
    global _checksum_cache
    
    # Check if cache is valid and we have cached SHA-1 checksum
    if _checksum_cache["sha1"] is not None and is_checksum_cache_valid():
        logging.debug("Using cached SHA-1 checksum")
        return _checksum_cache["sha1"]
    
    # Clear invalid cache
    if not is_checksum_cache_valid():
        logging.debug("Cache invalidated due to program length change")
        clear_checksum_cache()
    
    try:
        # Get current program length for cache validation
        program_length = Adau145x.get_program_len()
        
        # Calculate SHA-1 checksum (length-based)
        checksums = Adau145x.calculate_program_checksums(cached=True)
        if checksums and "sha1" in checksums:
            checksum_hex = checksums["sha1"]
            _checksum_cache["sha1"] = checksum_hex
            _checksum_cache["program_length"] = program_length
            logging.debug(f"Calculated and cached SHA-1 checksum: {checksum_hex} (program length: {program_length})")
            return checksum_hex
        else:
            logging.warning("Could not calculate SHA-1 checksum")
            return None
    except Exception as e:
        logging.error(f"Error calculating SHA-1 checksum: {str(e)}")
        return None


@app.route('/version', methods=['GET'])
def get_version():
    """
    API endpoint to get the version information of the HiFiBerry DSP toolkit
    
    Returns version information including the package version.
    """
    try:
        version_info = {
            "version": __version__,
            "name": "hifiberry-dsp",
            "description": "HiFiBerry DSP toolkit"
        }
        
        return jsonify(version_info)
        
    except Exception as e:
        logging.error(f"Error getting version info: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/hardware/dsp', methods=['GET'])
def get_hardware_info():
    """
    API endpoint to get information about the detected DSP hardware
    
    Returns information about the DSP chip detected by the sigmatcpserver,
    equivalent to 'dsptoolkit get-meta detected_dsp' command.
    """
    try:
        # Import here to avoid circular imports
        from hifiberrydsp.server.sigmatcp import SigmaTCPHandler
        
        # Get the detected DSP information
        detected_dsp = SigmaTCPHandler.get_meta("detected_dsp")
        
        # Format the response
        hardware_info = {
            "detected_dsp": detected_dsp if detected_dsp else "",
            "status": "detected" if detected_dsp and detected_dsp.strip() else "not_detected"
        }
        
        return jsonify(hardware_info)
        
    except Exception as e:
        logging.error(f"Error getting hardware info: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/profiles', methods=['GET'])
def list_dsp_profiles():
    """
    API endpoint to list all available DSP profiles
    
    Returns a list of XML profile filenames from /usr/share/hifiberry/dspprofiles/
    """
    logging.info("=== DSP PROFILES ENDPOINT CALLED ===")
    print("=== DSP PROFILES ENDPOINT CALLED ===")
    try:
        # Check if directory exists
        if not os.path.exists(PROFILES_DIR):
            logging.error(f"Profiles directory {PROFILES_DIR} does not exist")
            print(f"ERROR: Profiles directory {PROFILES_DIR} does not exist")
            return jsonify({"error": f"Profiles directory {PROFILES_DIR} does not exist"}), 404
        
        # Get all XML files in the directory
        try:
            files = os.listdir(PROFILES_DIR)
            xml_files = [f for f in files if f.lower().endswith('.xml')]
            xml_files.sort()  # Sort alphabetically
            
            return jsonify({
                "profiles": xml_files,
                "count": len(xml_files),
                "directory": PROFILES_DIR
            })
            
        except PermissionError:
            return jsonify({"error": f"Permission denied accessing {PROFILES_DIR}"}), 403
        except Exception as e:
            return jsonify({"error": f"Error reading directory: {str(e)}"}), 500
            
    except Exception as e:
        logging.error(f"Error listing DSP profiles: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/profiles/metadata', methods=['GET'])
def get_all_profiles_metadata():
    """
    API endpoint to get metadata for all available DSP profiles
    
    Returns a dictionary with filename as key and profile metadata as value
    """
    try:
        # Check if directory exists
        if not os.path.exists(PROFILES_DIR):
            return jsonify({"error": f"Profiles directory {PROFILES_DIR} does not exist"}), 404
        
        # Get all XML files in the directory
        try:
            files = os.listdir(PROFILES_DIR)
            xml_files = [f for f in files if f.lower().endswith('.xml')]
            
            profiles_metadata = {}
            
            for filename in xml_files:
                filepath = os.path.join(PROFILES_DIR, filename)
                try:
                    # Load the XML profile
                    xml_profile = XmlProfile(filepath)
                    
                    # Extract metadata
                    metadata = {}
                    for key in xml_profile.get_meta_keys():
                        metadata[key] = xml_profile.get_meta(key)
                    
                    # Add system metadata
                    metadata["_system"] = {
                        "profileName": xml_profile.get_meta("profileName") or "Unknown Profile",
                        "profileVersion": xml_profile.get_meta("profileVersion") or "Unknown Version",
                        "sampleRate": xml_profile.samplerate(),
                        "filename": filename,
                        "filepath": filepath
                    }
                    
                    profiles_metadata[filename] = metadata
                    
                except Exception as e:
                    # If we can't parse a profile, include error info
                    logging.warning(f"Error parsing profile {filename}: {str(e)}")
                    profiles_metadata[filename] = {
                        "error": f"Failed to parse profile: {str(e)}",
                        "_system": {
                            "filename": filename,
                            "filepath": filepath
                        }
                    }
            
            return jsonify({
                "profiles": profiles_metadata,
                "count": len(xml_files),
                "directory": PROFILES_DIR
            })
            
        except PermissionError:
            return jsonify({"error": f"Permission denied accessing {PROFILES_DIR}"}), 403
        except Exception as e:
            return jsonify({"error": f"Error reading directory: {str(e)}"}), 500
            
    except Exception as e:
        logging.error(f"Error getting profiles metadata: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/metadata', methods=['GET'])
def get_metadata():
    """
    API endpoint to retrieve metadata from the current DSP profile
    
    Query Parameters:
        start (str): Optional parameter to filter metadata keys that start with this string
        filter (str): Optional parameter to filter metadata by type (e.g., 'biquad')
    """
    metadata = get_profile_metadata()
    
    # Get start parameter with empty string as default
    start_filter = request.args.get('start', '')
    # Get filter type parameter
    filter_type = request.args.get('filter', '')
    
    # Apply filters
    filtered_metadata = {}
    
    for key, value in metadata.items():
        # Skip system metadata unless copying to final result
        if key == "_system":
            continue
            
        # Apply start filter
        if start_filter and not key.startswith(start_filter):
            continue
            
        # Apply type filter if specified
        if filter_type == 'biquad':
            if isinstance(value, str) and isBiquad(value):
                filtered_metadata[key] = value
        elif not filter_type:  # No filter type specified, include all items passing start filter
            filtered_metadata[key] = value
        # Future filter types can be added here with additional elif clauses
    
    # Always include system metadata if it exists
    if "_system" in metadata:
        filtered_metadata["_system"] = metadata["_system"]
    
    return jsonify(filtered_metadata)


def split_to_bytes(value, byte_count):
    """Splits an integer value into a list of bytes.

    Args:
        value (int): The integer value to split.
        byte_count (int): The number of bytes to split into.

    Returns:
        list: A list of bytes representing the integer value.
    """
    return [(value >> (8 * i)) & 0xFF for i in reversed(range(byte_count))]


@app.route('/memory', methods=['POST'])
def memory_access():
    """API endpoint to write 32-bit memory cells in hex or float notation."""
    try:
        if request.method == 'POST':
            # Write memory cells
            data = request.json
            if not data or 'address' not in data or 'value' not in data:
                return jsonify({"error": "Address and value are required in the request body"}), 400

            # Check if we should store this setting in the filter store
            store_setting = data.get('store', False)

            try:
                address = int(data['address'], 0)  # Auto-detect base: 0x prefix = hex, no prefix = decimal
                
                # Check if address is valid memory address
                if not Adau145x.is_valid_memory_address(address):
                    return jsonify({"error": f"Invalid memory address: {hex(address)}. Valid range is {hex(Adau145x.MIN_MEMORY)} to {hex(Adau145x.MAX_MEMORY)}"}), 400
                
                values = data['value']

                if not isinstance(values, list):
                    values = [values]  # Convert single value to list

                processed_values = []
                for i, value in enumerate(values):
                    # Check if next address is still valid
                    current_addr = address + i
                    if not Adau145x.is_valid_memory_address(current_addr):
                        return jsonify({"error": f"Invalid memory address: {hex(current_addr)}. Valid range is {hex(Adau145x.MIN_MEMORY)} to {hex(Adau145x.MAX_MEMORY)}"}), 400
                        
                    if isinstance(value, str) and value.startswith("0x"):
                        int_value = int(value, 16)  # Hexadecimal value
                    elif isinstance(value, (float, int)):
                        if isinstance(value, float):
                            int_value = Adau145x.decimal_repr(value)  # Convert float to fixed-point
                        else:
                            int_value = value
                    else:
                        raise ValueError(f"Unsupported value type: {value}")

                    # Convert to bytes and write directly to DSP memory
                    byte_data = Adau145x.int_data(int_value, 4)
                    Adau145x.write_memory(current_addr, byte_data)
                    processed_values.append(value)

                # Store in settings store if requested
                if store_setting:
                    try:
                        # Get current profile checksum for storage
                        checksum = get_current_program_checksum_sha1()
                        if checksum:
                            # Store as a memory setting using the new method
                            success = settings_store.store_memory_setting(checksum, data['address'], processed_values)
                            if success:
                                logging.info(f"Stored memory setting at address {data['address']} in settings store")
                            else:
                                logging.warning(f"Failed to store memory setting at address {data['address']} in settings store")
                        else:
                            logging.warning("Could not get current profile checksum for storing memory setting")
                    except Exception as e:
                        logging.error(f"Error storing memory setting: {str(e)}")
                        # Don't fail the request if storage fails, just log the error

                response_data = {
                    "address": hex(address), 
                    "values": [hex(v) if isinstance(v, int) else v for v in processed_values], 
                    "status": "success"
                }
                
                if store_setting:
                    response_data["stored"] = True
                    
                return jsonify(response_data)
            except Exception as e:
                return jsonify({"error": str(e)}), 500

    except Exception as e:
        logging.error(f"Error in memory_access: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/memory/<address>', defaults={'length': 1}, methods=['GET'])
@app.route('/memory/<address>/<int:length>', methods=['GET'])
def memory_read(address, length):
    """API endpoint to read memory cells in hex, int, or float notation (32-bit)"""
    try:
        if length < 1:
            return jsonify({"error": "Length must be at least 1"}), 400

        try:
            # Support hex or decimal address
            address = int(address, 0)  # Automatically handles 0x... or decimal
            
            # Check if address is valid memory address
            if not Adau145x.is_valid_memory_address(address):
                return jsonify({"error": f"Invalid memory address: {hex(address)}. Valid range is {hex(Adau145x.MIN_MEMORY)} to {hex(Adau145x.MAX_MEMORY)}"}), 400
            
            # Check if last address in the range is still valid
            if not Adau145x.is_valid_memory_address(address + length - 1):
                return jsonify({"error": f"Invalid memory range: {hex(address)} to {hex(address + length - 1)}. Valid range is {hex(Adau145x.MIN_MEMORY)} to {hex(Adau145x.MAX_MEMORY)}"}), 400

            # Read bytes from memory directly using Adau145x
            byte_count = length * 4  # 4 bytes per 32-bit memory cell
            bytes_data = Adau145x.read_memory(address, byte_count)

            # Get format parameter
            output_format = request.args.get('format', 'hex').lower()
            if output_format not in ['hex', 'int', 'float']:
                return jsonify({"error": "Invalid format. Supported values are 'hex', 'int', 'float'"}), 400

            # Concatenate 4 bytes to form 32-bit values
            values_32bit = []
            for i in range(0, len(bytes_data), 4):
                value = (bytes_data[i] << 24) | (bytes_data[i + 1] << 16) | (bytes_data[i + 2] << 8) | bytes_data[i + 3]
                if output_format == 'hex':
                    values_32bit.append(hex(value))
                elif output_format == 'int':
                    values_32bit.append(value)
                elif output_format == 'float':
                    values_32bit.append(Adau145x.decimal_val(value))

            return jsonify({"address": hex(address), "values": values_32bit})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    except Exception as e:
        logging.error(f"Error in memory_read: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/register/<address>', defaults={'length': 1}, methods=['GET'])
@app.route('/register/<address>/<int:length>', methods=['GET'])
def register_read(address, length):
    """API endpoint to read registers in hex notation (16-bit)"""
    try:
        if length < 1:
            return jsonify({"error": "Length must be at least 1"}), 400

        try:
            # Support hex or decimal address
            address = int(address, 0)  # Automatically handles 0x... or decimal
            
            # Check if address is valid register address
            if not Adau145x.is_valid_register_address(address):
                return jsonify({"error": f"Invalid register address: {hex(address)}. Valid range is {hex(Adau145x.MIN_REGISTER)} to {hex(Adau145x.MAX_REGISTER)}"}), 400
            
            # Check if last address in the range is still valid
            if not Adau145x.is_valid_register_address(address + length - 1):
                return jsonify({"error": f"Invalid register range: {hex(address)} to {hex(address + length - 1)}. Valid range is {hex(Adau145x.MIN_REGISTER)} to {hex(Adau145x.MAX_REGISTER)}"}), 400

            # Read directly from registers using Adau145x
            byte_count = length * 2  # 2 bytes per 16-bit register
            bytes_data = Adau145x.read_memory(address, byte_count)

            # Concatenate 2 bytes to form 16-bit values
            values_16bit = []
            for i in range(0, len(bytes_data), 2):
                value = (bytes_data[i] << 8) | bytes_data[i + 1]
                values_16bit.append(value & 0xFFFF)

            return jsonify({"address": hex(address), "values": [hex(value) for value in values_16bit]})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    except Exception as e:
        logging.error(f"Error in register_read: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/register', methods=['POST'])
def register_write():
    """API endpoint to write a 16-bit register in hex notation"""
    try:
        data = request.json
        if not data or 'address' not in data or 'value' not in data:
            return jsonify({"error": "Address and value are required in the request body"}), 400

        try:
            address = int(data['address'], 16)
            
            # Check if address is valid register address
            if not Adau145x.is_valid_register_address(address):
                return jsonify({"error": f"Invalid register address: {hex(address)}. Valid range is {hex(Adau145x.MIN_REGISTER)} to {hex(Adau145x.MAX_REGISTER)}"}), 400
            
            value = int(data['value'], 16)

            # Use Adau145x.int_data to convert value to bytes
            byte_data = Adau145x.int_data(value, 2)
            
            # Write directly to registers using Adau145x
            Adau145x.write_memory(address, byte_data)
            
            return jsonify({"address": hex(address), "value": hex(value), "status": "success"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    except Exception as e:
        logging.error(f"Error in register_write: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/checksum', methods=['GET'])
def get_program_checksum():
    """API endpoint to get the checksum of the current DSP program"""
    logging.info("=== CHECKSUM ENDPOINT CALLED ===")
    print("=== CHECKSUM ENDPOINT CALLED ===")
    try:
        # Calculate both signature and length-based checksums efficiently
        signature_checksums = Adau145x.calculate_program_checksums(mode="signature", cached=True)
        length_checksums = Adau145x.calculate_program_checksums(mode="length", cached=True)
        
        # Prepare response
        response = {
            "format": "checksums"
        }
        
        # Add signature-based checksums
        if "md5" in signature_checksums:
            response["checksum"] = signature_checksums["md5"]  # Backward compatibility
            response["signature"] = {
                "md5": signature_checksums["md5"]
            }
            if "sha1" in signature_checksums:
                response["signature"]["sha1"] = signature_checksums["sha1"]
            
            logging.info(f"Signature-based checksums: {signature_checksums}")
            print(f"Signature-based checksums: {signature_checksums}")
        else:
            logging.error("Failed to retrieve signature-based checksums")
            print("ERROR: Failed to retrieve signature-based checksums")
            response["signature"] = None
        
        # Add length-based checksums
        if "md5" in length_checksums:
            response["length"] = {
                "md5": length_checksums["md5"]
            }
            if "sha1" in length_checksums:
                response["length"]["sha1"] = length_checksums["sha1"]
            
            logging.info(f"Length-based checksums: {length_checksums}")
            print(f"Length-based checksums: {length_checksums}")
        else:
            logging.warning("Failed to retrieve length-based checksums")
            print("WARNING: Failed to retrieve length-based checksums")
            response["length"] = None
        
        # Return error only if both checksum types failed
        if not signature_checksums and not length_checksums:
            return jsonify({"error": "Failed to retrieve any checksums"}), 500
        
        return jsonify(response)
            
    except Exception as e:
        logging.error(f"Error getting program checksum: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/program-info', methods=['GET'])
def get_program_info():
    """
    Get comprehensive program information including checksums and length
    
    Returns:
        JSON response with program checksums (signature/length based) and program length
    """
    try:
        # Get program length
        program_length = Adau145x.get_program_len()
        
        # Get checksums for both modes
        signature_checksums = Adau145x.calculate_program_checksums(mode="signature", algorithms=["md5", "sha1"], cached=True)
        length_checksums = Adau145x.calculate_program_checksums(mode="length", algorithms=["md5", "sha1"], cached=True)
        
        result = {
            "program_length": program_length,
            "checksums": {
                "md5": signature_checksums.get("md5"),
                "sha1": length_checksums.get("sha1")
            }
        }
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Error getting program info: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/program-length', methods=['GET'])
def get_program_length():
    """API endpoint to get the length of the current DSP program"""
    logging.info("=== PROGRAM LENGTH ENDPOINT CALLED ===")
    print("=== PROGRAM LENGTH ENDPOINT CALLED ===")
    try:
        # Get max parameter from query string
        max_length = request.args.get('max', '').lower() in ('true', '1', 'yes')
        
        # Use Adau145x directly to get program length
        program_length = Adau145x.get_program_len(max=max_length)
        
        if program_length is not None:
            length_type = "maximum" if max_length else "current"
            logging.info(f"{length_type.capitalize()} DSP program length: {program_length} bytes")
            print(f"{length_type.capitalize()} DSP program length: {program_length} bytes")
            return jsonify({
                "length": program_length,
                "unit": "words",
                "bytes": program_length * 4,  # Convert words to bytes
                "type": length_type
            })
        else:
            length_type = "maximum" if max_length else "current"
            logging.error(f"Failed to retrieve {length_type} program length")
            print(f"ERROR: Failed to retrieve {length_type} program length")
            return jsonify({"error": f"Failed to retrieve {length_type} program length"}), 500
            
    except Exception as e:
        logging.error(f"Error getting program length: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/program-memory', methods=['GET'])
def get_program_memory():
    """API endpoint to get the program memory from the DSP"""
    logging.info("=== PROGRAM MEMORY ENDPOINT CALLED ===")
    print("=== PROGRAM MEMORY ENDPOINT CALLED ===")
    try:
        # Get format parameter
        output_format = request.args.get('format', 'hex').lower()
        if output_format not in ['hex', 'raw', 'base64']:
            return jsonify({"error": "Invalid format. Supported values are 'hex', 'raw', 'base64'"}), 400
        
        # Get end parameter
        end_mode = request.args.get('end', 'signature').lower()
        if end_mode not in ['signature', 'full', 'len']:
            return jsonify({"error": "Invalid end mode. Supported values are 'signature', 'full', 'len'"}), 400
        
        # Use Adau145x directly to get program memory
        program_memory = Adau145x.get_program_memory(end=end_mode)
        
        if program_memory is not None:
            logging.info(f"Retrieved DSP program memory ({end_mode} mode): {len(program_memory)} bytes")
            print(f"Retrieved DSP program memory ({end_mode} mode): {len(program_memory)} bytes")
            
            if output_format == 'hex':
                # Convert to hex string representation
                hex_data = program_memory.hex().upper()
                return jsonify({
                    "memory": hex_data,
                    "length": len(program_memory),
                    "format": "hex",
                    "end_mode": end_mode
                })
            elif output_format == 'base64':
                # Convert to base64 for binary transfer
                import base64
                b64_data = base64.b64encode(program_memory).decode('ascii')
                return jsonify({
                    "memory": b64_data,
                    "length": len(program_memory),
                    "format": "base64",
                    "end_mode": end_mode
                })
            elif output_format == 'raw':
                # Return raw bytes (will be JSON encoded as array of integers)
                return jsonify({
                    "memory": list(program_memory),
                    "length": len(program_memory),
                    "format": "raw",
                    "end_mode": end_mode
                })
        else:
            logging.error(f"Failed to retrieve program memory (end mode: {end_mode})")
            print(f"ERROR: Failed to retrieve program memory (end mode: {end_mode})")
            return jsonify({"error": f"Failed to retrieve program memory (end mode: {end_mode})"}), 500
            
    except Exception as e:
        logging.error(f"Error getting program memory: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/frequency-response', methods=['POST'])
def get_frequency_response():
    """API endpoint to calculate frequency response of a filter chain"""
    try:
        data = request.json
        if not data or 'filters' not in data:
            return jsonify({"error": "Filter definitions are required in the request body"}), 400
            
        # Get filters from request
        filter_defs = data['filters']
        if not isinstance(filter_defs, list):
            filter_defs = [filter_defs]  # Convert single filter to list
            
        # Create filter objects
        filters = []
        for filter_def in filter_defs:
            try:
                # Convert dict to JSON string and then create filter object
                filter_json = json.dumps(filter_def)
                filter_obj = Filter.fromJSON(filter_json)
                filters.append(filter_obj)
            except Exception as e:
                logging.error(f"Error creating filter: {str(e)}")
                return jsonify({"error": f"Invalid filter definition: {str(e)}"}), 400
                
        # Get sample rate from profile or guess it
        sample_rate = get_or_guess_samplerate()
            
        # Get custom frequencies if provided
        frequencies = None
        if 'frequencies' in data and isinstance(data['frequencies'], list):
            try:
                frequencies = [float(f) for f in data['frequencies']]
            except (ValueError, TypeError):
                return jsonify({"error": "Frequencies must be numeric values"}), 400
                
        # Get points per octave if provided
        points_per_octave = 8  # Default
        if 'pointsPerOctave' in data:
            try:
                points_per_octave = int(data['pointsPerOctave'])
                if points_per_octave < 1:
                    points_per_octave = 8
            except (ValueError, TypeError):
                pass
                
        # Calculate frequency response
        if not frequencies:
            frequencies = Filter.logspace_frequencies(20, 20000, points_per_octave)
            
        response_data = Filter.getFrequencyResponse(sample_rate, filters, frequencies)
        
        return jsonify(response_data)
        
    except Exception as e:
        logging.error(f"Error calculating frequency response: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/cache/clear', methods=['POST'])
def clear_cache():
    """API endpoint to clear the XML profile cache"""
    try:
        invalidate_cache()
        return jsonify({"status": "success", "message": "Cache cleared"})
    except Exception as e:
        logging.error(f"Error clearing cache: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/cache', methods=['GET'])
def get_cache_status():
    """API endpoint to get information about the current cache status"""
    try:
        global _xml_profile_cache, _checksum_cache
        
        # Create response with cache information
        cache_info = {
            "profile": {
                "cached": _xml_profile_cache["profile"] is not None,
                "path": _xml_profile_cache["path"],
                "valid": _xml_profile_cache["valid"]
            },
            "metadata": {
                "cached": _xml_profile_cache["metadata"] is not None
            },
            "checksum": {
                "cached": is_checksum_cache_valid(),
                "md5": _checksum_cache["md5"],
                "sha1": _checksum_cache["sha1"],
                "program_length": _checksum_cache["program_length"]
            }
        }
        
        # Add profile name if available
        if _xml_profile_cache["profile"] is not None:
            try:
                profile_name = _xml_profile_cache["profile"].get_meta("profileName")
                if profile_name:
                    cache_info["profile"]["name"] = profile_name
            except:
                pass
                
        # Add metadata key count if available
        if _xml_profile_cache["metadata"] is not None:
            try:
                # Count non-system metadata keys
                meta_count = len(_xml_profile_cache["metadata"]) - (1 if "_system" in _xml_profile_cache["metadata"] else 0)
                cache_info["metadata"]["keyCount"] = meta_count
                
                # Add system metadata if available
                if "_system" in _xml_profile_cache["metadata"]:
                    cache_info["metadata"]["system"] = _xml_profile_cache["metadata"]["_system"]
            except:
                pass
                
        return jsonify(cache_info)
    except Exception as e:
        logging.error(f"Error getting cache status: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/dspprofile', methods=['GET', 'POST'])
def get_xml_profile_data():
    """
    API endpoint to get or update the DSP profile
    
    GET: Retrieve the full XML profile data
    POST: Upload a new DSP profile from:
      - Raw XML content (Content-Type: application/xml or text/xml)
      - JSON with embedded XML, file path, or URL (Content-Type: application/json)
    """
    if request.method == 'GET':
        try:
            # Get the XML profile from cache or disk
            xml_profile = get_xml_profile()
            if not xml_profile:
                return jsonify({"error": "DSP profile file not found or invalid"}), 404
            
            # Get the raw XML data as string
            xml_data = str(xml_profile)
            
            # Return the XML data with the correct content type
            return xml_data, 200, {'Content-Type': 'application/xml'}
            
        except Exception as e:
            logging.error(f"Error retrieving XML profile: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    elif request.method == 'POST':
        try:
            # Check request format - accept both JSON and raw XML
            if request.is_json:
                # JSON format with embedded XML content
                data = request.json
                
                # Check which source type is provided
                if 'xml' in data:
                    # Direct XML content
                    xml_content = data['xml']
                    source_type = 'direct'
                    
                elif 'file' in data:
                    # Local file path
                    file_path = data['file']
                    try:
                        with open(file_path, 'r') as f:
                            xml_content = f.read()
                        source_type = 'file'
                    except Exception as e:
                        return jsonify({"error": f"Could not read file {file_path}: {str(e)}"}), 400
                
                elif 'url' in data:
                    # URL to remote file
                    url = data['url']
                    try:
                        import requests
                        response = requests.get(url, timeout=10)
                        if response.status_code != 200:
                            return jsonify({"error": f"Failed to retrieve profile from URL, status code: {response.status_code}"}), 400
                        xml_content = response.text
                        source_type = 'url'
                    except Exception as e:
                        return jsonify({"error": f"Could not download from URL {url}: {str(e)}"}), 400
                
                else:
                    return jsonify({"error": "Request must contain one of: 'xml', 'file', or 'url'"}), 400
                    
            elif request.content_type and ('xml' in request.content_type or 'text' in request.content_type):
                # Raw XML content
                xml_content = request.get_data(as_text=True)
                if not xml_content.strip():
                    return jsonify({"error": "Empty XML content provided"}), 400
                source_type = 'raw'
                
            else:
                return jsonify({"error": "Content-Type must be application/json, application/xml, or text/xml"}), 400
            
            # Write the profile to EEPROM
            from hifiberrydsp.hardware.adau145x import Adau145x
            
            # Invalidate cache before writing
            invalidate_cache()
            
            # Write the EEPROM content
            result = Adau145x.write_eeprom_content(xml_content)
            
            if not result:
                return jsonify({"status": "error", "message": "Failed to write profile to EEPROM"}), 500
            
            # Verify the checksum after writing
            try:
                # Wait a moment for the DSP to stabilize
                import time
                time.sleep(0.5)
                
                # Calculate new program checksums
                memory_checksums = Adau145x.calculate_program_checksums(mode="length", algorithms=["sha1", "md5"], cached=False)
                if not memory_checksums:
                    # Fallback to signature-based if length-based fails
                    memory_checksums = Adau145x.calculate_program_checksums(mode="signature", algorithms=["sha1", "md5"], cached=False)
                
                memory_checksum_sha1 = memory_checksums.get("sha1") if memory_checksums else None
                memory_checksum_md5 = memory_checksums.get("md5") if memory_checksums else None
                
                # Load the profile again to get its checksums
                profile_path = get_default_dspprofile_path()
                xml_profile = XmlProfile(profile_path)
                profile_checksum_sha1 = xml_profile.get_meta("checksum_sha1")
                profile_checksum_md5 = xml_profile.get_meta("checksum")
                
                # Check checksums with priority: SHA-1 first, then MD5
                checksums_match = False
                checksum_info = {}
                
                if profile_checksum_sha1 and memory_checksum_sha1:
                    sha1_match = profile_checksum_sha1.lower() == memory_checksum_sha1.lower()
                    checksums_match = sha1_match
                    checksum_info["sha1"] = {
                        "memory": memory_checksum_sha1,
                        "profile": profile_checksum_sha1,
                        "match": sha1_match
                    }
                
                if profile_checksum_md5 and memory_checksum_md5:
                    md5_match = profile_checksum_md5.lower() == memory_checksum_md5.lower()
                    if not checksums_match:  # Only use MD5 if SHA-1 didn't match
                        checksums_match = md5_match
                    checksum_info["md5"] = {
                        "memory": memory_checksum_md5,
                        "profile": profile_checksum_md5,
                        "match": md5_match
                    }
                
                # The cache should have already been updated by the write_eeprom_content function,
                # but we'll invalidate it again to be sure the next read loads the new profile
                invalidate_cache()
                
                return jsonify({
                    "status": "success",
                    "message": f"Profile from {source_type} successfully written to EEPROM",
                    "checksums": checksum_info,
                    "match": checksums_match
                })
                
            except Exception as e:
                logging.error(f"Error verifying checksum after profile write: {str(e)}")
                return jsonify({
                    "status": "warning",
                    "message": f"Profile from {source_type} written to EEPROM, but checksum verification failed",
                    "error": str(e)
                }), 200
                
        except Exception as e:
            logging.error(f"Error processing DSP profile update: {str(e)}")
            return jsonify({"error": str(e)}), 500


def resolve_address_from_metadata(key):
    """
    Resolve a memory address from a metadata key.
    
    Args:
        key (str): The metadata key to resolve
        
    Returns:
        int or None: The resolved memory address or None if not found
    """
    try:
        metadata = get_profile_metadata()
        if key in metadata:
            value = metadata[key]
            # Check if value is in biquad format (address/offset)
            if isinstance(value, str) and isBiquad(value):
                parts = value.split('/')
                base_addr = int(parts[0])
                return base_addr
        return None
    except Exception as e:
        logging.error(f"Error resolving address from metadata: {str(e)}")
        return None


@app.route('/biquad', methods=['POST'])
def set_biquad_filter():
    """
    API endpoint to set a biquad filter at the specified address
    
    The request body should contain:
    - address: Memory address or metadata key
    - offset: Offset (will be multiplied by 5)
    - filter: Filter parameters (either as object with a0,a1,a2,b0,b1,b2 or as a Filter object)
    - sampleRate: (optional) Override the sample rate for filter calculation
    """
    try:
        data = request.json
        if not data or 'address' not in data or 'filter' not in data:
            return jsonify({"error": "Address and filter are required in the request body"}), 400
            
        # Get offset (default to 0)
        offset = int(data.get('offset', 0))
        
        # Resolve address
        raw_address = data['address']
        base_address = None
        
        # Check if address is a direct hex or integer value
        if isinstance(raw_address, (int, float)) or (isinstance(raw_address, str) and 
                                                   (raw_address.startswith('0x') or raw_address.isdigit())):
            try:
                base_address = int(raw_address, 0)
            except ValueError:
                return jsonify({"error": f"Invalid address format: {raw_address}"}), 400
        else:
            # Try to resolve from metadata
            base_address = resolve_address_from_metadata(raw_address)
            if base_address is None:
                return jsonify({"error": f"Could not resolve address from metadata key: {raw_address}"}), 404
                
        # Calculate actual address with offset
        actual_address = base_address + (offset * 5)
        
        # Check if address is valid
        if not Adau145x.is_valid_memory_address(actual_address) or not Adau145x.is_valid_memory_address(actual_address + 4):
            return jsonify({"error": f"Invalid memory address range: {hex(actual_address)} to {hex(actual_address + 4)}"}), 400
            
        # Process filter parameters
        filter_data = data['filter']
        
        # Override sample rate if provided, otherwise get from profile or guess
        sample_rate = None
        if 'sampleRate' in data:
            try:
                sample_rate = int(data['sampleRate'])
                logging.debug(f"Using provided sample rate: {sample_rate}")
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid sample rate value"}), 400
        
        # If sample rate wasn't provided or was invalid, get it from profile or guess
        if not sample_rate:
            sample_rate = get_or_guess_samplerate()
        
        try:
            if isinstance(filter_data, dict) and all(k in filter_data for k in ['a0', 'a1', 'a2', 'b0', 'b1', 'b2']):
                # Direct coefficients provided
                a0 = float(filter_data['a0'])
                a1 = float(filter_data['a1'])
                a2 = float(filter_data['a2'])
                b0 = float(filter_data['b0'])
                b1 = float(filter_data['b1'])
                b2 = float(filter_data['b2'])
                
                # Create a Biquad object and write it to DSP memory
                bq = Biquad(a0, a1, a2, b0, b1, b2, "Custom biquad")
                Adau145x.write_biquad(actual_address, bq)
                
                # Store the filter in the filter store using checksum
                checksum = get_current_program_checksum_sha1()
                if checksum:
                    settings_store.store_filter(checksum, raw_address, offset, filter_data)
                
                return jsonify({
                    "status": "success", 
                    "address": hex(actual_address),
                    "sampleRate": sample_rate,
                    "coefficients": {
                        "a0": a0, "a1": a1, "a2": a2,
                        "b0": b0, "b1": b1, "b2": b2
                    }
                })
                
            elif isinstance(filter_data, dict) and 'type' in filter_data:
                # This is a filter specification, create a Filter object
                filter_json = json.dumps(filter_data)
                filter_obj = Filter.fromJSON(filter_json)
                
                # Calculate biquad coefficients
                coeffs = filter_obj.biquadCoefficients(sample_rate)
                
                if not coeffs or len(coeffs) != 6:
                    return jsonify({"error": "Invalid coefficients returned from filter"}), 500
                
                # Extract coefficients
                b0, b1, b2, a0, a1, a2 = coeffs
                
                # Create a Biquad object
                description = f"{filter_data.get('type', 'Filter')} at {filter_data.get('f', '')}Hz"
                bq = Biquad(a0, a1, a2, b0, b1, b2, description)
                
                # Write the biquad to DSP memory
                Adau145x.write_biquad(actual_address, bq)
                
                # Store the filter in the filter store using checksum
                checksum = get_current_program_checksum_sha1()
                if checksum:
                    settings_store.store_filter(checksum, raw_address, offset, filter_data)
                
                return jsonify({
                    "status": "success", 
                    "address": hex(actual_address),
                    "sampleRate": sample_rate,
                    "filter": filter_data,
                    "coefficients": {
                        "a0": a0, "a1": a1, "a2": a2,
                        "b0": b0, "b1": b1, "b2": b2
                    }
                })
            else:
                return jsonify({"error": "Invalid filter format. Expected direct coefficients or filter specification"}), 400
                
        except Exception as e:
            logging.error(f"Error processing filter parameters: {str(e)}")
            return jsonify({"error": f"Error processing filter: {str(e)}"}), 500
                
    except Exception as e:
        logging.error(f"Error setting biquad filter: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/filters', methods=['GET'])
def get_filters():
    """
    API endpoint to retrieve stored filters
    
    Query Parameters:
        checksum (str): Optional profile checksum to filter by
        current (bool): Set to 'true' to get filters for the currently active profile
    """
    try:
        checksum = request.args.get('checksum')
        current = request.args.get('current', '').lower() in ('true', '1', 'yes')
        
        if current:
            # Get filters for the currently active profile
            current_checksum = get_current_program_checksum_sha1()
            if not current_checksum:
                return jsonify({"error": "No active DSP profile found"}), 404
            
            filters = settings_store.get_filters(current_checksum)
            
            return jsonify({
                "checksum": current_checksum,
                "filters": filters,
                "current": True
            })
        elif checksum:
            # Use checksum to get filters
            filters = settings_store.get_filters(checksum)
            
            return jsonify({
                "checksum": checksum,
                "filters": filters
            })
        else:
            # Return all profiles organized by checksum
            all_filters = settings_store.get_filters()
            return jsonify({
                "profiles": all_filters
            })
            
    except Exception as e:
        logging.error(f"Error getting stored filters: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/filters', methods=['POST'])
def set_filters():
    """
    API endpoint to manually store filters in the filter store
    
    The request body should contain:
    - checksum: DSP profile checksum (optional, will use current SHA-1 checksum if not provided)
    - filters: Array of filter objects with address, offset, and filter data
    
    Note: This endpoint uses SHA-1 checksums internally for DSP program identification.
    """
    try:
        data = request.json
        if not data or 'filters' not in data:
            return jsonify({"error": "Filters array is required in the request body"}), 400
        
        # Get checksum (always use SHA-1 for internal DSP program identification)
        checksum = data.get('checksum', get_current_program_checksum_sha1())
        
        # If no checksum provided and we can't get current, return error
        if not checksum:
            return jsonify({"error": "Profile checksum is required (no active profile found)"}), 400
        
        filters_data = data['filters']
        
        if not isinstance(filters_data, list):
            return jsonify({"error": "Filters must be an array"}), 400
        
        success_count = 0
        errors = []
        
        for i, filter_entry in enumerate(filters_data):
            if not isinstance(filter_entry, dict):
                errors.append(f"Filter {i}: Must be an object")
                continue
                
            if 'address' not in filter_entry or 'filter' not in filter_entry:
                errors.append(f"Filter {i}: Address and filter are required")
                continue
            
            address = filter_entry['address']
            offset = filter_entry.get('offset', 0)
            filter_data = filter_entry['filter']
            
            if settings_store.store_filter(checksum, address, offset, filter_data):
                success_count += 1
            else:
                errors.append(f"Filter {i}: Failed to store filter at {address}")
        
        response = {
            "status": "success" if success_count > 0 else "error",
            "checksum": checksum,
            "stored": success_count,
            "total": len(filters_data)
        }
        
        if errors:
            response["errors"] = errors
        
        return jsonify(response)
        
    except Exception as e:
        logging.error(f"Error storing filters: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/filters', methods=['DELETE'])
def delete_filters():
    """
    API endpoint to delete stored filters
    
    Query Parameters:
        checksum (str): Profile checksum to delete filters for
        address (str): Optional specific address to delete
        all (bool): Delete all filters for all profiles
    """
    try:
        checksum = request.args.get('checksum')
        address = request.args.get('address')
        delete_all = request.args.get('all', '').lower() in ('true', '1', 'yes')
        
        success, message = settings_store.delete_filters(
            checksum=checksum,
            address=address,
            all_profiles=delete_all
        )
        
        if success:
            return jsonify({"status": "success", "message": message})
        else:
            return jsonify({"error": message}), 400 if "not found" in message.lower() else 500
            
    except Exception as e:
        logging.error(f"Error deleting filters: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/filters/bypass', methods=['GET'])
def get_filter_bypass():
    """
    API endpoint to get bypass state of filters
    
    Query Parameters:
        checksum (str): Profile checksum (optional, will use current if not provided)
        address (str): Memory address or metadata key
        offset (int): Offset value (default: 0, or omit for entire bank)
        bank (bool): Set to 'true' to get bypass state of entire filter bank
    """
    try:
        checksum = request.args.get('checksum')
        address = request.args.get('address')
        offset_param = request.args.get('offset')
        bank_mode = request.args.get('bank', '').lower() in ('true', '1', 'yes')
        
        if not address:
            return jsonify({"error": "Address parameter is required"}), 400
        
        if not checksum:
            checksum = get_current_program_checksum_sha1()
            if not checksum:
                return jsonify({"error": "No active DSP profile found and no checksum provided"}), 404
        
        if bank_mode or offset_param is None:
            # Get bypass state for entire filter bank
            filters = settings_store.get_filters(checksum)
            bank_filters = []
            
            for filter_key, filter_data in filters.items():
                if filter_data.get("address") == address:
                    bank_filters.append({
                        "offset": filter_data.get("offset", 0),
                        "bypassed": filter_data.get("bypassed", False),
                        "filter_key": filter_key
                    })
            
            if not bank_filters:
                return jsonify({"error": f"No filters found for address '{address}'"}), 404
            
            # Sort by offset
            bank_filters.sort(key=lambda x: x["offset"])
            
            return jsonify({
                "checksum": checksum,
                "address": address,
                "bank_mode": True,
                "filters": bank_filters,
                "total_filters": len(bank_filters)
            })
        else:
            # Get bypass state for single filter
            try:
                offset = int(offset_param)
            except ValueError:
                return jsonify({"error": "Offset must be a valid integer"}), 400
            
            bypass_state = settings_store.get_filter_bypass_state(checksum, address, offset)
            
            if bypass_state is None:
                return jsonify({"error": f"Filter not found at address '{address}' with offset {offset}"}), 404
            
            return jsonify({
                "checksum": checksum,
                "address": address,
                "offset": offset,
                "bank_mode": False,
                "bypassed": bypass_state
            })
        
    except Exception as e:
        logging.error(f"Error getting filter bypass state: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/filters/bypass', methods=['POST'])
def set_filter_bypass():
    """
    API endpoint to set bypass state of filters and apply to the DSP
    
    Request body for single filter:
    {
        "checksum": "profile_checksum",  // Optional, uses current if not provided
        "address": "eq1_band1",         // Memory address or metadata key
        "offset": 0,                    // Optional, default 0
        "bypassed": true                // true to bypass, false to enable
    }
    
    Request body for entire filter bank:
    {
        "checksum": "profile_checksum",  // Optional, uses current if not provided
        "address": "eq1_band1",         // Memory address or metadata key
        "bank": true,                   // Set to true to bypass entire bank
        "bypassed": true                // true to bypass, false to enable all filters in bank
    }
    """
    try:
        data = request.json
        if not data:
            return jsonify({"error": "JSON body required"}), 400
        
        address = data.get('address')
        offset = data.get('offset', 0)
        bypassed = data.get('bypassed')
        checksum = data.get('checksum')
        bank_mode = data.get('bank', False)
        
        if not address:
            return jsonify({"error": "Address is required"}), 400
        
        if bypassed is None:
            return jsonify({"error": "Bypassed state (true/false) is required"}), 400
        
        if not isinstance(bypassed, bool):
            return jsonify({"error": "Bypassed must be true or false"}), 400
        
        if not checksum:
            checksum = get_current_program_checksum_sha1()
            if not checksum:
                return jsonify({"error": "No active DSP profile found and no checksum provided"}), 404
        
        if bank_mode:
            # Set bypass state for entire filter bank
            filters = settings_store.get_filters(checksum)
            bank_filters = []
            
            # Find all filters with the same address
            for filter_key, filter_data in filters.items():
                if filter_data.get("address") == address:
                    bank_filters.append({
                        "offset": filter_data.get("offset", 0),
                        "filter_key": filter_key
                    })
            
            if not bank_filters:
                return jsonify({"error": f"No filters found for address '{address}'"}), 404
            
            # Apply bypass state to all filters in the bank
            success_count = 0
            failed_filters = []
            
            for filter_info in bank_filters:
                filter_offset = filter_info["offset"]
                
                # Update bypass state in store
                success, message = settings_store.set_filter_bypass(checksum, address, filter_offset, bypassed)
                
                if success:
                    # Apply the change to the DSP
                    try:
                        dsp_success = apply_filter_bypass_to_dsp(checksum, address, filter_offset, bypassed)
                        if dsp_success:
                            success_count += 1
                        else:
                            failed_filters.append(f"offset {filter_offset} (DSP write failed)")
                    except Exception as e:
                        logging.error(f"Error applying bypass to DSP for offset {filter_offset}: {str(e)}")
                        failed_filters.append(f"offset {filter_offset} ({str(e)})")
                else:
                    failed_filters.append(f"offset {filter_offset} (store update failed)")
            
            result = {
                "status": "success" if success_count > 0 else "error",
                "checksum": checksum,
                "address": address,
                "bank_mode": True,
                "bypassed": bypassed,
                "total_filters": len(bank_filters),
                "successful": success_count
            }
            
            if failed_filters:
                result["failed_filters"] = failed_filters
                result["message"] = f"Successfully updated {success_count}/{len(bank_filters)} filters"
            else:
                state = "bypassed" if bypassed else "enabled"
                result["message"] = f"All {success_count} filters in bank {state}"
            
            return jsonify(result)
        
        else:
            # Set bypass state for single filter
            # Update bypass state in store
            success, message = settings_store.set_filter_bypass(checksum, address, offset, bypassed)
            
            if not success:
                return jsonify({"error": message}), 400 if "not found" in message.lower() else 500
            
            # Apply the change to the DSP
            try:
                success = apply_filter_bypass_to_dsp(checksum, address, offset, bypassed)
                if not success:
                    return jsonify({"error": "Failed to apply bypass state to DSP"}), 500
            except Exception as e:
                logging.error(f"Error applying bypass to DSP: {str(e)}")
                return jsonify({"error": f"Failed to apply bypass to DSP: {str(e)}"}), 500
            
            return jsonify({
                "status": "success",
                "message": message,
                "checksum": checksum,
                "address": address,
                "offset": offset,
                "bank_mode": False,
                "bypassed": bypassed
            })
        
    except Exception as e:
        logging.error(f"Error setting filter bypass: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/filters/bypass', methods=['PUT'])
def toggle_filter_bypass():
    """
    API endpoint to toggle bypass state of filters
    
    Request body for single filter:
    {
        "checksum": "profile_checksum",  // Optional, uses current if not provided
        "address": "eq1_band1",         // Memory address or metadata key
        "offset": 0                     // Optional, default 0
    }
    
    Request body for entire filter bank:
    {
        "checksum": "profile_checksum",  // Optional, uses current if not provided
        "address": "eq1_band1",         // Memory address or metadata key
        "bank": true                    // Set to true to toggle entire bank
    }
    """
    try:
        data = request.json
        if not data:
            return jsonify({"error": "JSON body required"}), 400
        
        address = data.get('address')
        offset = data.get('offset', 0)
        checksum = data.get('checksum')
        bank_mode = data.get('bank', False)
        
        if not address:
            return jsonify({"error": "Address is required"}), 400
        
        if not checksum:
            checksum = get_current_program_checksum_sha1()
            if not checksum:
                return jsonify({"error": "No active DSP profile found and no checksum provided"}), 404
        
        if bank_mode:
            # Toggle bypass state for entire filter bank
            filters = settings_store.get_filters(checksum)
            bank_filters = []
            
            # Find all filters with the same address
            for filter_key, filter_data in filters.items():
                if filter_data.get("address") == address:
                    bank_filters.append({
                        "offset": filter_data.get("offset", 0),
                        "current_bypass": filter_data.get("bypassed", False),
                        "filter_key": filter_key
                    })
            
            if not bank_filters:
                return jsonify({"error": f"No filters found for address '{address}'"}), 404
            
            # Determine new state - if any filter is not bypassed, bypass all; otherwise enable all
            any_enabled = any(not f["current_bypass"] for f in bank_filters)
            new_state = any_enabled  # If any are enabled, bypass all; if all are bypassed, enable all
            
            # Apply new bypass state to all filters in the bank
            success_count = 0
            failed_filters = []
            
            for filter_info in bank_filters:
                filter_offset = filter_info["offset"]
                
                # Update bypass state in store
                success, message = settings_store.set_filter_bypass(checksum, address, filter_offset, new_state)
                
                if success:
                    # Apply the change to the DSP
                    try:
                        dsp_success = apply_filter_bypass_to_dsp(checksum, address, filter_offset, new_state)
                        if dsp_success:
                            success_count += 1
                        else:
                            failed_filters.append(f"offset {filter_offset} (DSP write failed)")
                    except Exception as e:
                        logging.error(f"Error applying bypass to DSP for offset {filter_offset}: {str(e)}")
                        failed_filters.append(f"offset {filter_offset} ({str(e)})")
                else:
                    failed_filters.append(f"offset {filter_offset} (store update failed)")
            
            result = {
                "status": "success" if success_count > 0 else "error",
                "checksum": checksum,
                "address": address,
                "bank_mode": True,
                "bypassed": new_state,
                "total_filters": len(bank_filters),
                "successful": success_count
            }
            
            if failed_filters:
                result["failed_filters"] = failed_filters
                result["message"] = f"Successfully toggled {success_count}/{len(bank_filters)} filters to {'bypassed' if new_state else 'enabled'}"
            else:
                state = "bypassed" if new_state else "enabled"
                result["message"] = f"All {success_count} filters in bank toggled to {state}"
            
            return jsonify(result)
        
        else:
            # Toggle bypass state for single filter
            success, new_state, message = settings_store.toggle_filter_bypass(checksum, address, offset)
            
            if not success:
                return jsonify({"error": message}), 400 if "not found" in message.lower() else 500
            
            # Apply the change to the DSP
            try:
                success = apply_filter_bypass_to_dsp(checksum, address, offset, new_state)
                if not success:
                    return jsonify({"error": "Failed to apply bypass state to DSP"}), 500
            except Exception as e:
                logging.error(f"Error applying bypass to DSP: {str(e)}")
                return jsonify({"error": f"Failed to apply bypass to DSP: {str(e)}"}), 500
            
            return jsonify({
                "status": "success",
                "message": message,
                "checksum": checksum,
                "address": address,
                "offset": offset,
                "bank_mode": False,
                "bypassed": new_state
            })
        
    except Exception as e:
        logging.error(f"Error toggling filter bypass: {str(e)}")
        return jsonify({"error": str(e)}), 500


def apply_filter_bypass_to_dsp(checksum, address, offset, bypassed):
    """
    Apply filter bypass state to the DSP hardware
    
    Args:
        checksum (str): Profile checksum
        address (str): Memory address or metadata key
        offset (int): Offset value
        bypassed (bool): True to write bypass filter, False to write original filter
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get the stored filter data
        filters = settings_store.get_filters(checksum)
        filter_key = f"{address}_{offset}"
        
        if filter_key not in filters:
            logging.error(f"Filter {filter_key} not found in store")
            return False
        
        filter_data = filters[filter_key]
        
        # Resolve the actual memory address
        base_address = None
        if isinstance(address, str) and not address.startswith('0x') and not address.isdigit():
            # Try to resolve from metadata
            metadata = get_profile_metadata()  # Use get_profile_metadata() instead of get_metadata()
            metadata_value = metadata.get(address)
            if metadata_value and '/' in str(metadata_value):
                # Parse biquad format like "addr/offset"
                parts = str(metadata_value).split('/')
                try:
                    base_address = int(parts[0])
                except ValueError:
                    logging.error(f"Could not parse address from metadata key {address}: {metadata_value}")
                    return False
            else:
                logging.error(f"Could not resolve address from metadata key {address}")
                return False
        else:
            # Direct address
            try:
                base_address = int(address, 0)  # Supports hex and decimal
            except ValueError:
                logging.error(f"Could not parse direct address {address}")
                return False
        
        # Calculate actual address with offset
        actual_address = base_address + (offset * 5)
        
        # Check if address is valid
        if not Adau145x.is_valid_memory_address(actual_address) or \
           not Adau145x.is_valid_memory_address(actual_address + 4):
            logging.error(f"Invalid memory address range {hex(actual_address)}")
            return False
        
        if bypassed:
            # Write bypass filter (unity coefficients)
            from hifiberrydsp.api.filters import Bypass
            bypass_filter = Bypass()
            coeffs = bypass_filter.biquadCoefficients(48000)  # Sample rate doesn't matter for bypass
            b0, b1, b2, a0, a1, a2 = coeffs
            
            # Create bypass biquad and write to DSP
            bq = Biquad(a0, a1, a2, b0, b1, b2, "Bypass filter")
            Adau145x.write_biquad(actual_address, bq)
            
            logging.info(f"Applied bypass filter at address {hex(actual_address)}")
        else:
            # Write original filter
            filter_spec = filter_data.get("filter", {})
            
            if all(k in filter_spec for k in ['a0', 'a1', 'a2', 'b0', 'b1', 'b2']):
                # Direct coefficients
                a0 = float(filter_spec['a0'])
                a1 = float(filter_spec['a1']) 
                a2 = float(filter_spec['a2'])
                b0 = float(filter_spec['b0'])
                b1 = float(filter_spec['b1'])
                b2 = float(filter_spec['b2'])
                
                # Create and write biquad
                bq = Biquad(a0, a1, a2, b0, b1, b2, "Restored filter")
                Adau145x.write_biquad(actual_address, bq)
            
            elif 'type' in filter_spec:
                # Filter specification - calculate coefficients
                sample_rate = get_or_guess_samplerate()
                
                # Create filter object
                filter_json = json.dumps(filter_spec)
                filter_obj = Filter.fromJSON(filter_json)
                
                # Calculate coefficients
                coeffs = filter_obj.biquadCoefficients(sample_rate)
                if not coeffs or len(coeffs) != 6:
                    logging.error("Invalid coefficients returned from filter")
                    return False
                
                # Extract coefficients (Filter returns b0,b1,b2,a0,a1,a2)
                b0, b1, b2, a0, a1, a2 = coeffs
                
                # Create and write biquad
                description = f"{filter_spec.get('type', 'Filter')} at {filter_spec.get('f', '')}Hz"
                bq = Biquad(a0, a1, a2, b0, b1, b2, description)
                Adau145x.write_biquad(actual_address, bq)
            else:
                logging.error("Invalid filter format in stored data")
                return False
            
            logging.info(f"Restored original filter at address {hex(actual_address)}")
        
        return True
        
    except Exception as e:
        logging.error(f"Error applying filter bypass to DSP: {str(e)}")
        return False


def run_api(host=DEFAULT_HOST, port=DEFAULT_PORT):
    """
    Run the metadata API server
    
    Args:
        host: Host to bind to (default: localhost)
        port: Port to bind to (default: 13141)
    """
    logging.info(f"Starting REST API on {host}:{port} using Waitress")
    serve(app, host=host, port=port)  # Use Waitress to serve the app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_api()
