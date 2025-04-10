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
from flask import Flask, jsonify, request
from hifiberrydsp.parser.xmlprofile import XmlProfile
from hifiberrydsp.client.sigmatcp import SigmaTCPClient
from hifiberrydsp.server.constants import COMMAND_XML, COMMAND_XML_RESPONSE
from hifiberrydsp.datatools import parse_int_length
from hifiberrydsp.api.filters import Filter
from waitress import serve
import numpy as np


DEFAULT_PORT = 31415
DEFAULT_HOST = "localhost"

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False


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

def get_profile_metadata(client=None):
    """
    Retrieve metadata from the active DSP profile.

    Args:
        client: Optional SigmaTCPClient instance. If not provided, a new one will be created.

    Returns:
        Dictionary containing metadata from the DSP profile
    """
    try:
        if client is None:
            client = SigmaTCPClient(None, "localhost", autoconnect=True)

        metadata = {}
        checksum = None

        # Try to get checksum to verify profile
        try:
            checksum = client.request_metadata("checksum")
            metadata["checksum"] = checksum
        except Exception as e:
            logging.warning(f"Could not get checksum: {str(e)}")

        # Get XML profile through cmd_get_xml
        try:
            xml_data = client.request_generic(COMMAND_XML,COMMAND_XML_RESPONSE)
            
            logging.debug("XML profile retrieved successfully")
            xml_profile = XmlProfile()
            xml_profile.read_from_text(xml_data.decode("utf-8", errors="replace"))
            logging.debug("XML profile parsed successfully")

            for k in xml_profile.get_meta_keys():
                logging.debug("Meta key: %s", k)
                metadata[k] = xml_profile.get_meta(k)
            

            # Add some system metadata
            metadata["_system"] = {
                "profileName": xml_profile.get_meta("profileName") or "Unknown Profile",
                "profileVersion": xml_profile.get_meta("profileVersion") or "Unknown Version",
                "sampleRate": xml_profile.samplerate()
            }

            return metadata

        except Exception as e:
            logging.error(f"Error retrieving XML profile: {str(e)}")
            return {"error": "Could not retrieve XML profile"}

    except Exception as e:
        logging.error(f"Error getting metadata: {str(e)}")
        return {"error": str(e)}

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
    """API endpoint to write 32-bit memory cells in hex notation"""
    try:
        client = SigmaTCPClient(None, "localhost", autoconnect=True)

        if request.method == 'POST':
            # Write memory cells
            data = request.json
            if not data or 'address' not in data or 'value' not in data:
                return jsonify({"error": "Address and value are required in the request body"}), 400

            try:
                address = int(data['address'], 16)
                values = data['value']

                if not isinstance(values, list):
                    values = [values]  # Convert single value to list

                for i, value in enumerate(values):
                    value = int(value, 16)

                    # Use split_to_bytes to split 32-bit value into 4 bytes
                    byte_data = split_to_bytes(value, 4)
                    client.write_memory(address + i, byte_data)

                return jsonify({"address": hex(address), "values": [hex(int(v, 16)) for v in values], "status": "success"})
            except Exception as e:
                return jsonify({"error": str(e)}), 500

    except Exception as e:
        logging.error(f"Error in memory_access: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/memory/<address>', defaults={'length': 1}, methods=['GET'])
@app.route('/memory/<address>/<int:length>', methods=['GET'])
def memory_read(address, length):
    """API endpoint to read memory cells in hex notation (32-bit)"""
    try:
        client = SigmaTCPClient(None, "localhost", autoconnect=True)

        if length < 1:
            return jsonify({"error": "Length must be at least 1"}), 400

        try:
            # Support hex or decimal address
            address = int(address, 0)  # Automatically handles 0x... or decimal

            # Read bytes from memory
            byte_count = length * 4  # 4 bytes per 32-bit memory cell
            bytes_data = client.read_memory(address, byte_count)  # address is absolute independent of mememory cell length

            # Concatenate 4 bytes to form 32-bit values
            values_32bit = []
            for i in range(0, len(bytes_data), 4):
                value = (bytes_data[i] << 24) | (bytes_data[i + 1] << 16) | (bytes_data[i + 2] << 8) | bytes_data[i + 3]
                values_32bit.append(value & 0xFFFFFFFF)

            return jsonify({"address": hex(address), "values": [hex(value) for value in values_32bit]})
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
        client = SigmaTCPClient(None, "localhost", autoconnect=True)

        if length < 1:
            return jsonify({"error": "Length must be at least 1"}), 400

        try:
            # Support hex or decimal address
            address = int(address, 0)  # Automatically handles 0x... or decimal

            # Read bytes from registers
            byte_count = length * 2  # 2 bytes per 16-bit register
            bytes_data = client.read_memory(address, byte_count)  # address is absolute independent of mememory cell length

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
        client = SigmaTCPClient(None, "localhost", autoconnect=True)

        data = request.json
        if not data or 'address' not in data or 'value' not in data:
            return jsonify({"error": "Address and value are required in the request body"}), 400

        try:
            address = int(data['address'], 16)
            value = int(data['value'], 16)

            # Use split_to_bytes to split 16-bit value into 2 bytes
            byte_data = split_to_bytes(value, 2)
            client.write_memory(address * 2, byte_data)

            return jsonify({"address": hex(address), "value": hex(value), "status": "success"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    except Exception as e:
        logging.error(f"Error in register_write: {str(e)}")
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

def run_api(host=DEFAULT_HOST, port=DEFAULT_PORT):
    """
    Run the metadata API server
    
    Args:
        host: Host to bind to (default: localhost)
        port: Port to bind to (default: 31415)
    """
    logging.info(f"Starting REST API on {host}:{port} using Waitress")
    serve(app, host=host, port=port)  # Use Waitress to serve the app

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_api()
