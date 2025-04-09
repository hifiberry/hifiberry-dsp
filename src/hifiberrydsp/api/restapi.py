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
from hifiberrydsp.datatools import parse_int_length
from waitress import serve

DEFAULT_PORT = 31415
DEFAULT_HOST = "localhost"

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

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
        
        # Get XML profile through metadata request
        xml_data = client.request_metadata("xml")
        if xml_data:
            xml_profile = XmlProfile(xmldata=xml_data)
            
            # Extract all metadata from beometa section
            for meta in xml_profile.doc["ROM"]["beometa"]["metadata"]:
                attr_type = meta["@type"]
                attr_value = meta["#text"]
                
                # Process additional attributes
                attrs = {}
                for key, value in meta.items():
                    if key not in ["@type", "#text"]:
                        attrs[key.replace("@", "")] = value
                
                # Add to metadata dictionary
                if attrs:
                    metadata[attr_type] = {
                        "value": attr_value,
                        "attributes": attrs
                    }
                else:
                    metadata[attr_type] = attr_value
                    
                # Process register addresses with lengths
                if attr_type in xml_profile.REGISTER_ATTRIBUTES:
                    try:
                        addr, length = parse_int_length(attr_value)
                        if length > 1:
                            if attr_type in metadata:
                                if isinstance(metadata[attr_type], dict):
                                    metadata[attr_type]["address"] = addr
                                    metadata[attr_type]["length"] = length
                                else:
                                    metadata[attr_type] = {
                                        "value": attr_value,
                                        "address": addr,
                                        "length": length
                                    }
                    except Exception as e:
                        logging.debug(f"Could not parse address/length for {attr_type}: {str(e)}")
                    
            # Add some system metadata
            metadata["_system"] = {
                "profileName": xml_profile.get_meta("profileName") or "Unknown Profile",
                "profileVersion": xml_profile.get_meta("profileVersion") or "Unknown Version",
                "sampleRate": xml_profile.samplerate()
            }
            
            return metadata
            
        return {"error": "Could not retrieve profile metadata"}
        
    except Exception as e:
        logging.error(f"Error getting metadata: {str(e)}")
        return {"error": str(e)}

@app.route('/metadata', methods=['GET'])
def get_metadata():
    """API endpoint to retrieve metadata from the current DSP profile"""
    return jsonify(get_profile_metadata())

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
