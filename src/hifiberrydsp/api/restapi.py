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
from flask import Flask, jsonify, request
from hifiberrydsp.parser.xmlprofile import XmlProfile, get_default_dspprofile_path
from hifiberrydsp.api.filters import Filter
from waitress import serve
import numpy as np
from hifiberrydsp.hardware.adau145x import Adau145x


DEFAULT_PORT = 13141
DEFAULT_HOST = "localhost"

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Cache for XML profile
_xml_profile_cache = {
    "profile": None,
    "path": None,
    "timestamp": 0,
    "metadata": None,
    "cache_timeout": 3600  # Cache valid for one hour
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
    Get the cached XML profile or read from disk if needed
    
    Returns:
        XmlProfile: The cached or newly read XML profile
    """
    global _xml_profile_cache
    
    profile_path = get_default_dspprofile_path()
    
    # Check if file exists
    if not os.path.exists(profile_path):
        return None
    
    current_time = time.time()
    file_mtime = os.path.getmtime(profile_path)
    
    # Check if we need to refresh the cache
    cache_valid = (
        _xml_profile_cache["profile"] is not None and
        _xml_profile_cache["path"] == profile_path and
        current_time - _xml_profile_cache["timestamp"] < _xml_profile_cache["cache_timeout"] and
        file_mtime <= _xml_profile_cache["timestamp"]
    )
    
    if not cache_valid:
        logging.debug("XML profile cache miss - reading from disk")
        try:
            xml_profile = XmlProfile(profile_path)
            
            # Update the cache
            _xml_profile_cache["profile"] = xml_profile
            _xml_profile_cache["path"] = profile_path
            _xml_profile_cache["timestamp"] = current_time
            _xml_profile_cache["metadata"] = None  # Reset metadata cache
            
            return xml_profile
        except Exception as e:
            logging.error(f"Error reading XML profile: {str(e)}")
            return None
    else:
        logging.debug("XML profile cache hit")
        return _xml_profile_cache["profile"]


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
    Invalidate the XML profile cache
    """
    global _xml_profile_cache
    _xml_profile_cache["profile"] = None
    _xml_profile_cache["metadata"] = None
    _xml_profile_cache["timestamp"] = 0


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

            try:
                address = int(data['address'], 16)
                
                # Check if address is valid memory address
                if not Adau145x.is_valid_memory_address(address):
                    return jsonify({"error": f"Invalid memory address: {hex(address)}. Valid range is {hex(Adau145x.MIN_MEMORY)} to {hex(Adau145x.MAX_MEMORY)}"}), 400
                
                values = data['value']

                if not isinstance(values, list):
                    values = [values]  # Convert single value to list

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

                # Invalidate cache after memory write
                invalidate_cache()
                
                return jsonify({"address": hex(address), "values": [hex(v) if isinstance(v, int) else v for v in values], "status": "success"})
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
            
            # Invalidate cache after register write
            invalidate_cache()

            return jsonify({"address": hex(address), "value": hex(value), "status": "success"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    except Exception as e:
        logging.error(f"Error in register_write: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/checksum', methods=['GET'])
def get_program_checksum():
    """API endpoint to get the checksum of the current DSP program"""
    try:
        # Use Adau145x directly for checksum calculation
        checksum_bytes = Adau145x.calculate_program_checksum(cached=False)
        
        if checksum_bytes:
            # Convert bytes to hex representation
            checksum_hex = binascii.hexlify(checksum_bytes).decode('utf-8')
            return jsonify({
                "checksum": checksum_hex,
                "format": "md5"
            })
        else:
            return jsonify({"error": "Failed to retrieve checksum"}), 500
            
    except Exception as e:
        logging.error(f"Error getting program checksum: {str(e)}")
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
                
        # Get sample rate from profile or use default
        sample_rate = 48000  # Default value
        try:
            metadata = get_profile_metadata()
            if "_system" in metadata and "sampleRate" in metadata["_system"]:
                sample_rate = metadata["_system"]["sampleRate"]
        except Exception as e:
            logging.warning(f"Could not get sample rate from profile, using default: {str(e)}")
            
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


@app.route('/dspprofile', methods=['GET'])
def get_xml_profile_data():
    """API endpoint to get the full XML profile data"""
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
        
        try:
            if isinstance(filter_data, dict) and all(k in filter_data for k in ['a0', 'a1', 'a2', 'b0', 'b1', 'b2']):
                # Direct coefficients provided
                a0 = float(filter_data['a0'])
                a1 = float(filter_data['a1'])
                a2 = float(filter_data['a2'])
                b0 = float(filter_data['b0'])
                b1 = float(filter_data['b1'])
                b2 = float(filter_data['b2'])
                
                # Use the static method to write biquad
                try:
                    from hifiberrydsp.filtering.biquad import Biquad
                    # Create a Biquad object and write it to DSP memory
                    bq = Biquad.from_parameters(a0, a1, a2, b0, b1, b2)
                    Adau145x.write_biquad(actual_address, bq)
                    
                    return jsonify({
                        "status": "success", 
                        "address": hex(actual_address),
                        "coefficients": {
                            "a0": a0, "a1": a1, "a2": a2,
                            "b0": b0, "b1": b1, "b2": b2
                        }
                    })
                except ImportError:
                    # If Biquad class is not available, use direct approach
                    from hifiberrydsp.hardware.adau145x import Adau145x
                    Adau145x.write_biquad_direct(actual_address, a0, a1, a2, b0, b1, b2)
                    
                    return jsonify({
                        "status": "success", 
                        "address": hex(actual_address),
                        "coefficients": {
                            "a0": a0, "a1": a1, "a2": a2,
                            "b0": b0, "b1": b1, "b2": b2
                        }
                    })
                    
            elif isinstance(filter_data, dict) and 'type' in filter_data:
                # This is a filter specification, create a Filter object
                filter_json = json.dumps(filter_data)
                from hifiberrydsp.api.filters import Filter
                filter_obj = Filter.fromJSON(filter_json)
                
                # Get sample rate from profile or use default
                sample_rate = 48000  # Default value
                try:
                    metadata = get_profile_metadata()
                    if "_system" in metadata and "sampleRate" in metadata["_system"]:
                        sample_rate = metadata["_system"]["sampleRate"]
                except Exception as e:
                    logging.warning(f"Could not get sample rate from profile, using default: {str(e)}")
                
                # Calculate biquad coefficients
                biquad = filter_obj.biquad(sample_rate)
                
                # Use the static method to write biquad
                Adau145x.write_biquad(actual_address, biquad)
                
                return jsonify({
                    "status": "success", 
                    "address": hex(actual_address),
                    "filter": filter_data,
                    "coefficients": {
                        "a0": biquad.a0, "a1": biquad.a1, "a2": biquad.a2,
                        "b0": biquad.b0, "b1": biquad.b1, "b2": biquad.b2
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
