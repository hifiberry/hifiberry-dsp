# HiFiBerry DSP REST API Documentation

This document describes the REST API provided by the HiFiBerry DSP service for interacting with DSP profiles and memory.

## Base URL

The API server runs by default on:
```
http://localhost:13141
```

## Endpoints

### Version API

#### Get Version Information

Retrieves version information about the HiFiBerry DSP toolkit.

```
GET /version
```

**Example Request:**
```bash
curl -X GET http://localhost:13141/version
```

**Example Response:**
```json
{
  "version": "1.3.2",
  "name": "hifiberry-dsp",
  "description": "HiFiBerry DSP toolkit"
}
```

**Response Properties:**

- `version`: The version string of the HiFiBerry DSP toolkit
- `name`: The package name
- `description`: Brief description of the toolkit

### Hardware Detection API

#### Get Detected DSP Hardware

Retrieves information about the DSP hardware detected by the sigmatcpserver. This endpoint provides the same information as the `dsptoolkit get-meta detected_dsp` command.

```
GET /hardware/dsp
```

**Example Request:**
```bash
curl -X GET http://localhost:13141/hardware/dsp
```

**Example Response (DSP Detected):**
```json
{
  "detected_dsp": "ADAU14xx",
  "status": "detected"
}
```

**Example Response (No DSP Detected):**
```json
{
  "detected_dsp": "",
  "status": "not_detected"
}
```

**Response Properties:**

- `detected_dsp`: String identifying the detected DSP chip (e.g., "ADAU14xx"), or empty string if no DSP detected
- `status`: Either "detected" or "not_detected" indicating whether a DSP was successfully detected

### DSP Profiles API

#### List Available DSP Profiles

Retrieves a list of all available DSP profile files from the profiles directory.

```
GET /profiles
```

**Example Request:**
```bash
curl -X GET http://localhost:13141/profiles
```

**Example Response:**
```json
{
  "profiles": [
    "beocreate-universal-11.xml",
    "dacdsp-15.xml",
    "dsp-addon-96-14.xml"
  ],
  "count": 3,
  "directory": "/usr/share/hifiberry/dspprofiles"
}
```

**Response Properties:**

- `profiles`: Array of XML profile filenames
- `count`: Number of available profiles
- `directory`: Path to the profiles directory

#### Get All Profiles Metadata

Retrieves metadata for all available DSP profiles.

```
GET /profiles/metadata
```

**Example Request:**
```bash
curl -X GET http://localhost:13141/profiles/metadata
```

**Example Response:**
```json
{
  "profiles": {
    "beocreate-universal-11.xml": {
      "checksum": "A1B2C3D4E5F6...",
      "profileName": "Beocreate Universal",
      "profileVersion": "11.0",
      "volumeControlRegister": "1234",
      "_system": {
        "profileName": "Beocreate Universal",
        "profileVersion": "11.0",
        "sampleRate": 48000,
        "filename": "beocreate-universal-11.xml",
        "filepath": "/usr/share/hifiberry/dspprofiles/beocreate-universal-11.xml"
      }
    },
    "dacdsp-15.xml": {
      "checksum": "F6E5D4C3B2A1...",
      "profileName": "DAC+ DSP",
      "profileVersion": "15.0",
      "_system": {
        "profileName": "DAC+ DSP",
        "profileVersion": "15.0",
        "sampleRate": 48000,
        "filename": "dacdsp-15.xml",
        "filepath": "/usr/share/hifiberry/dspprofiles/dacdsp-15.xml"
      }
    }
  },
  "count": 2,
  "directory": "/usr/share/hifiberry/dspprofiles"
}
```

**Response Properties:**

- `profiles`: Dictionary with filename as key and profile metadata as value
- `count`: Number of profiles processed
- `directory`: Path to the profiles directory

**Notes:**
- Profiles that cannot be parsed will include an `error` field in their metadata
- Each profile includes a `_system` section with filename, filepath, and parsed system information

### Metadata API

#### Get Profile Metadata

Retrieves metadata from the currently loaded DSP profile.

```
GET /metadata
```

**Query Parameters:**

- `start` (optional): Filter metadata keys that start with the specified string
- `filter` (optional): Filter metadata by type. Supported values:
  - `biquad`: Only return metadata entries that represent biquad filters (format: xxx/yy where yy is a multiple of 5)

**Example Requests:**

Get all metadata:
```
GET /metadata
```

```bash
curl -X GET http://localhost:13141/metadata
```

Get metadata with keys starting with "eq1_":
```
GET /metadata?start=eq1_
```

```bash
curl -X GET "http://localhost:13141/metadata?start=eq1_"
```

Get only biquad filter metadata:
```
GET /metadata?filter=biquad
```

```bash
curl -X GET "http://localhost:13141/metadata?filter=biquad"
```

Get biquad filters with keys starting with "eq1_":
```
GET /metadata?filter=biquad&start=eq1_
```

```bash
curl -X GET "http://localhost:13141/metadata?filter=biquad&start=eq1_"
```

**Example Response:**
```json
{
  "checksum": "12345abcde",
  "eq1_band1": "1234/5",
  "eq1_band2": "5678/10",
  "_system": {
    "profileName": "Example Profile",
    "profileVersion": "1.0",
    "sampleRate": 48000
  }
}
```

### Program Checksum API

#### Get Current DSP Program Checksum

Retrieves multiple checksums (MD5 and SHA-1) of the currently loaded DSP program in memory using both signature-based and length-based methods. These checksums can be used to verify program integrity and compare with profile checksums.

```
GET /checksum
```

**Example Request:**
```bash
curl -X GET http://localhost:13141/checksum
```

**Example Response:**
```json
{
  "checksum": "97C9C5A88582888D111259BF70D6D79E",
  "format": "checksums",
  "signature": {
    "md5": "97C9C5A88582888D111259BF70D6D79E",
    "sha1": "A1B2C3D4E5F67890ABCDEF1234567890FEDCBA09"
  },
  "length": {
    "md5": "1234567890ABCDEF1234567890ABCDEF",
    "sha1": "FEDCBA0987654321ABCDEF1234567890A1B2C3D4"
  }
}
```

**Response Properties:**

- `checksum`: MD5 checksum using signature-based detection (for backward compatibility)
- `format`: Always "checksums" indicating multiple checksum algorithms are provided
- `signature`: Object containing signature-based checksums
  - `md5`: MD5 checksum using program end signature detection
  - `sha1`: SHA-1 checksum using program end signature detection
- `length`: Object containing length-based checksums
  - `md5`: MD5 checksum using program length registers
  - `sha1`: SHA-1 checksum using program length registers

**Notes:**
- **Signature checksums**: Use program end signature detection (matches XML profile checksums)
- **Length checksums**: Use program length registers to determine program boundaries
- **Efficient caching**: Memory is read only once per mode, and all checksums are calculated and cached
- **Multiple algorithms**: Both MD5 and SHA-1 checksums are provided for enhanced security
- The `checksum` field maintains backward compatibility and contains the signature-based MD5
- **Smart caching**: Checksums are cached per mode and algorithm to avoid recalculation
- Cache is automatically cleared when a new DSP program is installed
- Different methods may produce different checksums for the same program due to different end detection
- Signature-based checksums are compatible with existing XML profile checksums
- XML profiles can include both `checksum` (MD5) and `checksum_sha1` (SHA-1) attributes
- Profile validation prioritizes SHA-1 over MD5 when both are available
- Length-based checksums provide precise register-based program verification
- If one method fails, the other may still succeed (failed checksums return `null`)
- Useful for debugging profile loading issues and ensuring program integrity

#### Get Comprehensive Program Information

Retrieves comprehensive information about the currently loaded DSP program, including checksums calculated with different methods and program length.

```
GET /program-info
```

**Example Request:**

```bash
curl http://localhost:8080/api/program-info
```

**Response Format:**

```json
{
  "program_length": 1536,
  "checksums": {
    "signature": {
      "md5": "A1B2C3D4E5F6789012345678901234EF",
      "sha1": "FEDCBA0987654321ABCDEF1234567890A1B2C3D4"
    },
    "length": {
      "md5": "1234567890ABCDEF1234567890ABCDEF",
      "sha1": "ABCDEF1234567890FEDCBA0987654321A1B2C3D4"
    }
  }
}
```

**Response Properties:**

- `program_length`: Length of the current DSP program in words (from length registers)
- `checksums`: Object containing checksums calculated with different detection methods
  - `signature`: Checksums using program end signature detection
    - `md5`: MD5 checksum (compatible with XML profile `checksum` attribute)
    - `sha1`: SHA-1 checksum
  - `length`: Checksums using program length registers
    - `md5`: MD5 checksum using precise length detection
    - `sha1`: SHA-1 checksum (compatible with XML profile `checksum_sha1` attribute)

**Notes:**
- Provides all checksum variants in a single API call for comprehensive program verification
- Signature-based checksums match those stored in XML profiles for validation
- Length-based checksums provide more precise program boundary detection
- Useful for debugging, profile validation, and program integrity verification
- All checksums are cached for performance

#### Get Current DSP Program Length

Retrieves the length of the currently loaded DSP program in memory. This information is read from the DSP's program length registers.

```
GET /program-length[?max={true|false}]
```

**Query Parameters:**

- `max` (optional, default: `false`): If `true`, returns the maximum program length instead of current length

**Example Request (Current Length):**
```bash
curl -X GET http://localhost:13141/program-length
```

**Example Request (Maximum Length):**
```bash
curl -X GET "http://localhost:13141/program-length?max=true"
```

**Example Response (Current Length):**
```json
{
  "length": 2048,
  "unit": "words",
  "bytes": 8192,
  "type": "current"
}
```

**Example Response (Maximum Length):**
```json
{
  "length": 8192,
  "unit": "words", 
  "bytes": 32768,
  "type": "maximum"
}
```

**Response Properties:**

- `length`: Length of the DSP program in words
- `unit`: Always "words" indicating the unit of measurement
- `bytes`: Length converted to bytes (length × 4)
- `type`: Either "current" or "maximum" depending on the `max` parameter

**Notes:**
- Current length is read from DSP registers 0xf463 and 0xf464
- Maximum length is read from DSP registers 0xf465 and 0xf466
- Current length shows how much program memory is currently in use
- Maximum length shows the total available program memory space
- Useful for debugging and monitoring DSP program size and available space
- Returns null/error if the DSP is not accessible or the registers cannot be read

#### Get Current DSP Program Memory

Retrieves the complete program memory content from the DSP. This endpoint provides access to the actual program code running on the DSP with different end detection modes.

```
GET /program-memory[?format={hex|raw|base64}&end={signature|full|len}]
```

**Query Parameters:**

- `format` (optional, default: `hex`): Output format for the program memory data. Supported values:
  - `hex`: Return data as hexadecimal string (uppercase)
  - `raw`: Return data as array of integers (0-255)
  - `base64`: Return data as base64-encoded string

- `end` (optional, default: `signature`): End detection mode for program memory. Supported values:
  - `signature`: Find program end signature (default, stops at program end marker)
  - `full`: Dump full program memory space (entire allocated memory region)
  - `len`: Use program length registers to determine end (stops at current program length)

**Example Request (Default - Signature End):**
```bash
curl -X GET http://localhost:13141/program-memory
```

**Example Request (Full Memory Dump):**
```bash
curl -X GET "http://localhost:13141/program-memory?end=full"
```

**Example Request (Length-based with Base64 Format):**
```bash
curl -X GET "http://localhost:13141/program-memory?end=len&format=base64"
```

**Example Response (Hex Format - Signature End):**
```json
{
  "memory": "02C20000000000000000000000000000A1B2C3D4...",
  "length": 8192,
  "format": "hex",
  "end_mode": "signature"
}
```

**Example Response (Base64 Format - Full Memory):**
```json
{
  "memory": "AsIAAAAAAAAAAAAAAAAAobLD1A==...",
  "length": 32768,
  "format": "base64",
  "end_mode": "full"
}
```

**Example Response (Raw Format - Length-based):**
```json
{
  "memory": [2, 194, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 161, 178, 195, 212, ...],
  "length": 8192,
  "format": "raw",
  "end_mode": "len"
}
```

**Response Properties:**

- `memory`: Program memory content in the requested format
- `length`: Length of the program memory in bytes
- `format`: Format of the returned data
- `end_mode`: End detection mode used ("signature", "full", or "len")

**Notes:**
- The DSP core is temporarily stopped during memory read and automatically restarted
- **Signature mode**: Stops at program end signature marker (default, most efficient)
- **Full mode**: Dumps entire program memory space (largest output, includes unused memory)
- **Length mode**: Uses program length registers to determine end (precise, based on DSP registers)
- Large program memory may result in substantial response sizes, especially with `raw` format and `full` mode
- Use `base64` format for efficient binary data transfer
- Use `hex` format for human-readable debugging
- Use `signature` mode for normal program analysis and backup
- Use `full` mode for complete memory forensics or debugging
- Use `len` mode for precise program content based on DSP registers
- Useful for program backup, analysis, and verification

### Memory Access API

#### Read Memory

Read 32-bit memory cells from the DSP.

```
GET /memory/{address}[/{length}]
```

**Path Parameters:**

- `address`: Memory address in decimal or hexadecimal (with 0x prefix)
- `length` (optional, default: 1): Number of 32-bit memory cells to read

**Query Parameters:**

- `format` (optional, default: `hex`): Output format for the memory values. Supported values:
  - `hex`: Return values as hexadecimal strings (e.g., "0x12345678")
  - `int`: Return values as integers
  - `float`: Return values as floating-point numbers (converted from 32-bit fixed-point representation)

**Example Requests:**

Read 4 memory cells starting at address 0x100 in hexadecimal format:
```
GET /memory/0x100/4
```

```bash
curl -X GET http://localhost:13141/memory/0x100/4
```

Read 2 memory cells starting at address 0x200 in integer format:
```
GET /memory/0x200/2?format=int
```

```bash
curl -X GET "http://localhost:13141/memory/0x200/2?format=int"
```

Read 1 memory cell at address 0x300 in floating-point format:
```
GET /memory/0x300?format=float
```

```bash
curl -X GET "http://localhost:13141/memory/0x300?format=float"
```

**Example Response (Hexadecimal Format):**
```json
{
  "address": "0x100",
  "values": ["0x12345678", "0xabcdef01", "0x87654321", "0x10abcdef"]
}
```

**Example Response (Integer Format):**
```json
{
  "address": "0x200",
  "values": [305419896, 2882400001]
}
```

**Example Response (Float Format):**
```json
{
  "address": "0x300",
  "values": [1.23, -0.45, 0.0078125]
}
```

#### Write Memory

Write 32-bit memory cells to the DSP.

```
POST /memory
```

**Request Body:**

You can write values in different formats:

1. Hexadecimal strings:
```json
{
  "address": "0x100",
  "value": ["0x12345678", "0xabcdef01"]
}
```

```bash
curl -X POST http://localhost:13141/memory \
  -H "Content-Type: application/json" \
  -d '{"address": "0x100", "value": ["0x12345678", "0xabcdef01"]}'
```

2. Floating-point values (automatically converted to DSP fixed-point format):
```json
{
  "address": "0x100",
  "value": [1.23, -0.45, 0.0078125]
}
```

```bash
curl -X POST http://localhost:13141/memory \
  -H "Content-Type: application/json" \
  -d '{"address": "0x100", "value": [1.23, -0.45, 0.0078125]}'
```

3. Mix of formats:
```json
{
  "address": "0x100",
  "value": ["0x12345678", 1.23, -0.45]
}
```

```bash
curl -X POST http://localhost:13141/memory \
  -H "Content-Type: application/json" \
  -d '{"address": "0x100", "value": ["0x12345678", 1.23, -0.45]}'
```

4. Single value:
```json
{
  "address": "0x100",
  "value": "0x12345678"
}
```

```bash
curl -X POST http://localhost:13141/memory \
  -H "Content-Type: application/json" \
  -d '{"address": "0x100", "value": "0x12345678"}'
```

or

```json
{
  "address": "0x100",
  "value": 1.23
}
```

```bash
curl -X POST http://localhost:13141/memory \
  -H "Content-Type: application/json" \
  -d '{"address": "0x100", "value": 1.23}'
```

5. Store memory setting for auto-loading:
```json
{
  "address": "4744",
  "value": [1.0, 0.5],
  "store": true
}
```

```bash
curl -X POST http://localhost:13141/memory \
  -H "Content-Type: application/json" \
  -d '{"address": "4744", "value": [1.0, 0.5], "store": true}'
```

**Parameters:**

- `address` (required): Memory address in decimal or hexadecimal format
- `value` (required): Single value or array of values to write
- `store` (optional, default: false): If true, store this memory setting in the filter store for automatic loading on startup

**Example Response:**
```json
{
  "address": "0x100",
  "values": ["0x12345678", 1.23, -0.45],
  "status": "success"
}
```

**Example Response (with store=true):**
```json
{
  "address": "0x1288", 
  "values": [1.0, 0.5],
  "status": "success",
  "stored": true
}
```

**Note on Float Values:**
When using floating-point values, they must be within the valid range for the SigmaDSP fixed-point representation (approximately -256 to 256). Values will be automatically converted to the appropriate 32-bit fixed-point representation understood by the DSP.

**Note on Stored Memory Settings:**
When `store` is set to true, the memory setting will be saved in the filter store organized by the current DSP profile checksum. These settings will be automatically restored when the DSP profile is loaded on system startup, similar to how stored filters work.

### Biquad Filter API

#### Set Biquad Filter

Write biquad filter coefficients to DSP memory.

```
POST /biquad
```

**Request Body:**

You can specify biquad filters in different ways:

1. Direct coefficients:
```json
{
  "address": "0x100",
  "offset": 0,
  "sampleRate": 96000,
  "filter": {
    "a0": 1.0,
    "a1": -1.8,
    "a2": 0.81,
    "b0": 0.5,
    "b1": 0.0,
    "b2": -0.5
  }
}
```

```bash
curl -X POST http://localhost:13141/biquad \
  -H "Content-Type: application/json" \
  -d '{
  "address": "0x100",
  "offset": 0,
  "sampleRate": 96000,
  "filter": {
    "a0": 1.0,
    "a1": -1.8,
    "a2": 0.81,
    "b0": 0.5,
    "b1": 0.0,
    "b2": -0.5
  }
}'
```

2. Using filter specification:
```json
{
  "address": "0x100",
  "offset": 1,
  "sampleRate": 48000,
  "filter": {
    "type": "PeakingEq",
    "f": 1000,
    "db": -3.0,
    "q": 1.0
  }
}
```

```bash
curl -X POST http://localhost:13141/biquad \
  -H "Content-Type: application/json" \
  -d '{
  "address": "0x100",
  "offset": 1,
  "sampleRate": 48000,
  "filter": {
    "type": "PeakingEq",
    "f": 1000,
    "db": -3.0,
    "q": 1.0
  }
}'
```

3. Using a metadata key as address:
```json
{
  "address": "eq1_band1",
  "offset": 0,
  "filter": {
    "type": "LowShelf",
    "f": 100,
    "db": 3.0,
    "slope": 1.0
  }
}
```

```bash
curl -X POST http://localhost:13141/biquad \
  -H "Content-Type: application/json" \
  -d '{
  "address": "eq1_band1",
  "offset": 0,
  "filter": {
    "type": "LowShelf",
    "f": 100,
    "db": 3.0,
    "slope": 1.0
  }
}'
```

**Parameters:**

- `address`: Memory address (hexadecimal or decimal), or a metadata key that resolves to a memory address
- `offset` (optional, default: 0): Offset from the base address, will be multiplied by 5 (as each biquad filter requires 5 memory cells)
- `sampleRate` (optional): Override the sample rate used for filter calculations. If not provided, the system will use the sample rate from the profile metadata or try to guess it.
- `filter`: Either direct biquad coefficients or a filter specification object

**Example Response (Direct Coefficients):**
```json
{
  "status": "success",
  "address": "0x100",
  "sampleRate": 48000,
  "coefficients": {
    "a0": 1.0,
    "a1": -1.8,
    "a2": 0.81,
    "b0": 0.5,
    "b1": 0.0,
    "b2": -0.5
  }
}
```

**Example Response (Filter Specification):**
```json
{
  "status": "success",
  "address": "0x100",
  "sampleRate": 96000,
  "filter": {
    "type": "PeakingEq",
    "f": 1000,
    "db": -3.0,
    "q": 1.0
  },
  "coefficients": {
    "a0": 1.0,
    "a1": -1.8969,
    "a2": 0.9025,
    "b0": 0.9513,
    "b1": -1.8969,
    "b2": 0.8538
  }
}
```

**Notes:**

1. When using a metadata key as the address, the system will look up the key in the metadata and extract the base address from it.
2. The offset parameter is useful when you have multiple filters starting at a base address. For example, with offset=1, the filter will be written 5 memory cells after the base address.
3. Filter coefficients are automatically normalized to ensure a0 = 1.0 before being written to the DSP.
4. The sample rate is important for calculating the correct filter coefficients. Specify it explicitly when you know your system is running at a non-standard rate.
5. Filters set via the `/biquad` endpoint are automatically stored in the filter store using the current DSP profile checksum.

### Filter Store API

The filter store allows you to save and retrieve filter configurations for different DSP profiles. Filters are automatically stored when set via the `/biquad` endpoint and are organized by profile checksum.

#### Get Stored Filters

Retrieve stored filters from the filter store.

```
GET /filters
```

**Query Parameters:**

- `checksum` (optional): DSP profile checksum to get filters for. If not specified, returns filters for all profiles.
- `current` (optional): Set to `true` to get filters for the currently active DSP profile. This automatically determines the current checksum and returns filters for that profile.

**Example Requests:**

Get all stored filters:
```bash
curl -X GET http://localhost:13141/filters
```

Get filters for a specific profile by checksum:
```bash
curl -X GET "http://localhost:13141/filters?checksum=8B924F2C2210B903CB4226C12C56EE44"
```

Get filters for the currently active profile:
```bash
curl -X GET "http://localhost:13141/filters?current=true"
```

**Example Response (All Profiles):**
```json
{
  "profiles": {
    "8B924F2C2210B903CB4226C12C56EE44": {
      "eq1_band1_0": {
        "address": "eq1_band1",
        "offset": 0,
        "filter": {
          "type": "PeakingEq",
          "f": 1000,
          "db": -3.0,
          "q": 1.0
        },
        "timestamp": 1699564123.456
      },
      "0x100_1": {
        "address": "0x100",
        "offset": 1,
        "filter": {
          "a0": 1.0,
          "a1": -1.8,
          "a2": 0.81,
          "b0": 0.5,
          "b1": 0.0,
          "b2": -0.5
        },
        "timestamp": 1699564156.789
      }
    },
    "A1B2C3D4E5F6789012345678ABCDEF01": {
      ...
    }
  }
}
```

**Example Response (Single Profile by Checksum):**
```json
{
  "checksum": "8B924F2C2210B903CB4226C12C56EE44",
  "filters": {
    "eq1_band1_0": {
      "address": "eq1_band1",
      "offset": 0,
      "filter": {
        "type": "PeakingEq",
        "f": 1000,
        "db": -3.0,
        "q": 1.0
      },
      "timestamp": 1699564123.456
    }
  }
}
```

**Example Response (Current Profile):**
```json
{
  "checksum": "8B924F2C2210B903CB4226C12C56EE44",
  "current": true,
  "filters": {
    "customFilterRegisterBankLeft": {
      "address": "customFilterRegisterBankLeft",
      "offset": 0,
      "filter": {
        "type": "PeakingEq",
        "f": 1000,
        "db": 10.0,
        "q": 1.0
      },
      "timestamp": 1699564789.123
    }
  }
}
  }
}
```

#### Store Filters Manually

Manually store filters in the filter store without applying them to the DSP.

```
POST /filters
```

**Request Body:**

```json
{
  "checksum": "8B924F2C2210B903CB4226C12C56EE44",
  "filters": [
    {
      "address": "eq1_band1",
      "offset": 0,
      "filter": {
        "type": "PeakingEq",
        "f": 1000,
        "db": -3.0,
        "q": 1.0
      }
    },
    {
      "address": "0x200",
      "offset": 2,
      "filter": {
        "a0": 1.0,
        "a1": -1.5,
        "a2": 0.5,
        "b0": 0.8,
        "b1": 0.0,
        "b2": -0.8
      }
    }
  ]
}
```

**Parameters:**

- `checksum` (optional): DSP profile checksum. If not provided, uses the current active profile checksum.
- `filters`: Array of filter objects to store.

Each filter object should contain:
- `address`: Memory address or metadata key
- `offset` (optional, default: 0): Offset value
- `filter`: Filter specification (same format as `/biquad` endpoint)

**Example Response:**
```json
{
  "status": "success",
  "checksum": "8B924F2C2210B903CB4226C12C56EE44",
  "stored": 2,
  "total": 2
}
```

#### Delete Stored Filters

Delete stored filters from the filter store.

```
DELETE /filters
```

**Query Parameters:**

- `checksum`: DSP profile checksum to delete filters for
- `address` (optional): Specific address to delete. If not provided, deletes all filters for the profile.
- `all` (optional): Set to `true` to delete all filters for all profiles

**Example Requests:**

Delete all filters for a specific profile by checksum:
```bash
curl -X DELETE "http://localhost:13141/filters?checksum=8B924F2C2210B903CB4226C12C56EE44"
```

Delete a specific filter:
```bash
curl -X DELETE "http://localhost:13141/filters?checksum=8B924F2C2210B903CB4226C12C56EE44&address=eq1_band1"
```

Delete all filters for all profiles:
```bash
curl -X DELETE "http://localhost:13141/filters?all=true"
```

**Example Response:**
```json
{
  "status": "success",
  "message": "All filters deleted for profile checksum '8B924F2C2210B903CB4226C12C56EE44'"
}
```

**Notes:**

1. The filter store is saved as `filters.json` at `/var/lib/hifiberry/filters.json`.
2. Filters are automatically stored when set via the `/biquad` endpoint using the current profile checksum.
3. Filter keys are generated as `{address}_{offset}` or just `{address}` if offset is 0.
4. Each stored filter includes a timestamp indicating when it was last modified.
5. The filter store persists across system restarts and profile changes.
6. Profiles are organized by their MD5 checksum for better reliability and uniqueness.
7. Profile names are stored for display purposes but checksums are used as the primary identifier.
8. Legacy support is provided for accessing filters by profile name, but checksum-based access is recommended.
9. Each filter can be individually bypassed without losing its configuration using the bypass API endpoints.

### Filter Bypass API

The filter bypass API allows you to temporarily disable filters without losing their configuration. When a filter is bypassed, its original coefficients are preserved in the filter store, but a bypass filter (unity coefficients) is written to the DSP instead.

The bypass API supports both **individual filter** operations and **filter bank** operations (all filters sharing the same base address).

#### Get Filter Bypass State

Retrieve the bypass state of a specific filter or entire filter bank.

```
GET /filters/bypass?address={address}&offset={offset}&checksum={checksum}&bank={bank}
```

**Query Parameters:**

- `address` (required): Memory address or metadata key
- `offset` (optional): Offset value. Omit or set `bank=true` for entire bank operations
- `checksum` (optional): DSP profile checksum. If not provided, uses the current active profile
- `bank` (optional): Set to `true` to get bypass state of entire filter bank

**Example Requests:**

Get bypass state for a single filter:
```bash
curl -X GET "http://localhost:13141/filters/bypass?address=eq1_band1&offset=0"
```

Get bypass state for entire filter bank:
```bash
curl -X GET "http://localhost:13141/filters/bypass?address=eq1_band1&bank=true"
```

**Example Response (Single Filter):**
```json
{
  "checksum": "8B924F2C2210B903CB4226C12C56EE44",
  "address": "eq1_band1",
  "offset": 0,
  "bank_mode": false,
  "bypassed": false
}
```

**Example Response (Filter Bank):**
```json
{
  "checksum": "8B924F2C2210B903CB4226C12C56EE44",
  "address": "eq1_band1",
  "bank_mode": true,
  "total_filters": 5,
  "filters": [
    {
      "offset": 0,
      "bypassed": false,
      "filter_key": "eq1_band1_0"
    },
    {
      "offset": 1,
      "bypassed": true,
      "filter_key": "eq1_band1_1"
    }
  ]
}
```

#### Set Filter Bypass State

Set the bypass state of a filter or entire filter bank and apply the change to the DSP immediately.

```
POST /filters/bypass
```

**Request Body (Single Filter):**
```json
{
  "address": "eq1_band1",
  "offset": 0,
  "bypassed": true,
  "checksum": "8B924F2C2210B903CB4226C12C56EE44"
}
```

**Request Body (Filter Bank):**
```json
{
  "address": "eq1_band1",
  "bank": true,
  "bypassed": true,
  "checksum": "8B924F2C2210B903CB4226C12C56EE44"
}
```

**Parameters:**

- `address` (required): Memory address or metadata key
- `bypassed` (required): `true` to bypass the filter(s), `false` to enable them
- `offset` (optional, default: 0): Offset value for single filter operations
- `bank` (optional, default: false): Set to `true` to operate on entire filter bank
- `checksum` (optional): DSP profile checksum. If not provided, uses the current active profile

**Example Requests:**

Bypass a single filter:
```bash
curl -X POST http://localhost:13141/filters/bypass \
  -H "Content-Type: application/json" \
  -d '{
    "address": "eq1_band1",
    "offset": 0,
    "bypassed": true
  }'
```

Bypass entire filter bank:
```bash
curl -X POST http://localhost:13141/filters/bypass \
  -H "Content-Type: application/json" \
  -d '{
    "address": "eq1_band1",
    "bank": true,
    "bypassed": true
  }'
```

Enable entire filter bank:
```bash
curl -X POST http://localhost:13141/filters/bypass \
  -H "Content-Type: application/json" \
  -d '{
    "address": "eq1_band1",
    "bank": true,
    "bypassed": false
  }'
```

**Example Response (Single Filter):**
```json
{
  "status": "success",
  "message": "Filter at eq1_band1+0 bypassed",
  "checksum": "8B924F2C2210B903CB4226C12C56EE44",
  "address": "eq1_band1",
  "offset": 0,
  "bank_mode": false,
  "bypassed": true
}
```

**Example Response (Filter Bank):**
```json
{
  "status": "success",
  "message": "All 5 filters in bank bypassed",
  "checksum": "8B924F2C2210B903CB4226C12C56EE44",
  "address": "eq1_band1",
  "bank_mode": true,
  "bypassed": true,
  "total_filters": 5,
  "successful": 5
}
```

#### Toggle Filter Bypass State

Toggle the bypass state of a filter or entire filter bank between enabled and bypassed.

```
PUT /filters/bypass
```

**Request Body (Single Filter):**
```json
{
  "address": "eq1_band1",
  "offset": 0,
  "checksum": "8B924F2C2210B903CB4226C12C56EE44"
}
```

**Request Body (Filter Bank):**
```json
{
  "address": "eq1_band1",
  "bank": true,
  "checksum": "8B924F2C2210B903CB4226C12C56EE44"
}
```

**Parameters:**

- `address` (required): Memory address or metadata key
- `offset` (optional, default: 0): Offset value for single filter operations
- `bank` (optional, default: false): Set to `true` to toggle entire filter bank
- `checksum` (optional): DSP profile checksum. If not provided, uses the current active profile

**Toggle Logic:**

- **Single Filter**: Toggles the current bypass state (enabled ↔ bypassed)
- **Filter Bank**: If any filter in the bank is enabled, all filters are bypassed. If all filters are bypassed, all filters are enabled.

**Example Requests:**

Toggle single filter:
```bash
curl -X PUT http://localhost:13141/filters/bypass \
  -H "Content-Type: application/json" \
  -d '{
    "address": "eq1_band1",
    "offset": 0
  }'
```

Toggle entire filter bank:
```bash
curl -X PUT http://localhost:13141/filters/bypass \
  -H "Content-Type: application/json" \
  -d '{
    "address": "eq1_band1",
    "bank": true
  }'
```

**Example Response (Single Filter):**
```json
{
  "status": "success", 
  "message": "Filter at eq1_band1+0 enabled",
  "checksum": "8B924F2C2210B903CB4226C12C56EE44",
  "address": "eq1_band1",
  "offset": 0,
  "bank_mode": false,
  "bypassed": false
}
```

**Example Response (Filter Bank):**
```json
{
  "status": "success",
  "message": "All 5 filters in bank toggled to enabled",
  "checksum": "8B924F2C2210B903CB4226C12C56EE44",
  "address": "eq1_band1",
  "bank_mode": true,
  "bypassed": false,
  "total_filters": 5,
  "successful": 5
}
```

**Bypass API Notes:**

1. **Immediate DSP Application**: All bypass operations immediately update the DSP hardware
2. **Coefficient Preservation**: Original filter coefficients are always preserved in the filter store
3. **Bypass Implementation**: Bypassed filters use unity coefficients (b0=1, b1=0, b2=0, a0=1, a1=0, a2=0)
4. **Automatic Loading**: Bypass states are preserved and restored during DSP profile changes
5. **Address Resolution**: Both direct memory addresses and metadata keys are supported
6. **Error Handling**: Invalid addresses or missing filters return appropriate error responses
7. **Filter Bank Operations**: Operate on all filters sharing the same base address
8. **Partial Failures**: For bank operations, individual filter failures are reported in the response
9. **Smart Toggle Logic**: Bank toggle considers the state of all filters to determine the new state
10. **Performance**: Bank operations are atomic and efficient for managing multiple related filters

### Register Access API

#### Read Register

Read 16-bit registers from the DSP.

```
GET /register/{address}[/{length}]
```

**Path Parameters:**

- `address`: Register address in decimal or hexadecimal (with 0x prefix)
- `length` (optional, default: 1): Number of 16-bit registers to read

**Example Request:**
```
GET /register/0x200/2
```

```bash
curl -X GET http://localhost:13141/register/0x200/2
```

**Example Response:**
```json
{
  "address": "0x200",
  "values": ["0x1234", "0x5678"]
}
```

#### Write Register

Write a 16-bit register to the DSP.

```
POST /register
```

**Request Body:**
```json
{
  "address": "0x200",
  "value": "0x1234"
}
```

```bash
curl -X POST http://localhost:13141/register \
  -H "Content-Type: application/json" \
  -d '{"address": "0x200", "value": "0x1234"}'
```

**Example Response:**
```json
{
  "address": "0x200",
  "value": "0x1234",
  "status": "success"
}
```

### Frequency Response API

#### Calculate Frequency Response

Calculate the frequency response of one or more filters.

```
POST /frequency-response
```

**Request Body:**

```json
{
  "filters": [
    {
      "type": "PeakingEq",
      "f": 1000,
      "db": -3.0,
      "q": 1.0
    },
    {
      "type": "HighPass",
      "f": 80,
      "db": 0.0,
      "q": 0.707
    }
  ],
  "frequencies": [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
  "pointsPerOctave": 8
}
```

```bash
curl -X POST http://localhost:13141/frequency-response \
  -H "Content-Type: application/json" \
  -d '{
  "filters": [
    {
      "type": "PeakingEq",
      "f": 1000,
      "db": -3.0,
      "q": 1.0
    },
    {
      "type": "HighPass",
      "f": 80,
      "db": 0.0,
      "q": 0.707
    }
  ],
  "frequencies": [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
  "pointsPerOctave": 8
}'
```

**Parameters:**

- `filters`: An array of filter objects (required)
- `frequencies`: Optional array of specific frequencies (in Hz) to calculate the response at
- `pointsPerOctave`: Optional number of points per octave for automatically generated frequencies (default: 8)

If `frequencies` is not provided, the response will be calculated using a logarithmic scale from 20Hz to 20kHz with the specified number of points per octave.

**Example Response:**

```json
{
  "frequencies": [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
  "response": [-18.06, -12.04, -6.02, -1.87, 0.0, -3.01, -0.97, 0.0, 0.0, 0.0]
}
```

**Response Properties:**

- `frequencies`: Array of frequencies (in Hz) at which the response was calculated
- `response`: Array of corresponding gain values (in dB)

### Cache Management API

#### Get Cache Status

Get information about the current cache status, including whether the XML profile, metadata, and program checksum are cached.

```
GET /cache
```

```bash
curl -X GET http://localhost:13141/cache
```

**Example Response:**
```json
{
  "profile": {
    "cached": true,
    "path": "/etc/hifiberry/dspprofile.xml",
    "name": "4-Way IIR Crossover"
  },
  "metadata": {
    "cached": true,
    "keyCount": 24,
    "system": {
      "profileName": "4-Way IIR Crossover",
      "profileVersion": "1.0",
      "sampleRate": 48000
    }
  },
  "checksum": {
    "cached": true,
    "value": "8B924F2C2210B903CB4226C12C56EE44"
  }
}
}
```

#### Clear Cache

Clear the internal XML profile cache and program checksum cache. This is useful if the DSP profile file has been updated externally. Note that the checksum cache is automatically cleared when a new DSP program is installed via the API.

```
POST /cache/clear
```

```bash
curl -X POST http://localhost:13141/cache/clear
```

#### Get DSP Profile

Retrieve the full DSP profile configuration in XML format.

```
GET /dspprofile
```

```bash
curl -X GET http://localhost:13141/dspprofile
```

#### Update DSP Profile

Upload a new DSP profile to the device. The profile can be provided in one of three ways:
- Direct XML content in the request body
- A path to a local file on the server
- A URL pointing to a remote XML profile

The new profile will be written to the DSP's EEPROM and also cached in the standard location.

```
POST /dspprofile
```

**Request Body Options:**

1. Direct XML content:
```json
{
  "xml": "<XML content of DSP profile>"
}
```

```bash
curl -X POST http://localhost:13141/dspprofile \
  -H "Content-Type: application/json" \
  -d '{"xml": "<XML content of DSP profile>"}'
```

2. Local file path on the server:
```json
{
  "file": "/path/to/dspprofile.xml"
}
```

```bash
curl -X POST http://localhost:13141/dspprofile \
  -H "Content-Type: application/json" \
  -d '{"file": "/path/to/dspprofile.xml"}'
```

3. URL to a remote file:
```json
{
  "url": "https://example.com/profiles/dspprofile.xml"
}
```

```bash
curl -X POST http://localhost:13141/dspprofile \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/profiles/dspprofile.xml"}'
```

4. Direct file upload (multipart/form-data):
```bash
curl -X POST http://localhost:13141/dspprofile \
  -F "file=@/path/to/local/dspprofile.xml"
```

**Response:**

```json
{
  "status": "success",
  "message": "Profile from direct successfully written to EEPROM",
  "checksum": {
    "memory": "1a2b3c4d5e6f7890...",
    "profile": "1a2b3c4d5e6f7890...",
    "match": true
  }
}
```

**Notes:**
1. After writing the DSP profile, the system will verify if the checksum in memory matches the one in the profile.
2. The profile will be saved to the standard location and the cache will be updated.
3. The API requires sufficient permissions to write to the DSP EEPROM.
4. For security reasons, when using the `file` option, the file must be accessible on the server running the REST API.

## Filter Operations

### Filter JSON Syntax

Filters are defined using JSON format. Each filter has a specific type and parameters depending on the filter type.

#### Common Filter Parameters

All filters share these common parameters:

- `type`: The type of filter (required)
- Additional parameters specific to each filter type

#### Supported Filter Types

##### PeakingEq Filter

Used for creating peaking equalization filters.

```json
{
  "type": "PeakingEq",
  "f": 1000,
  "db": -3.0,
  "q": 1.0
}
```

**Parameters:**
- `f`: Center frequency in Hz
- `db`: Gain in decibels
- `q`: Q factor (bandwidth)

##### GenericBiquad Filter

Used for creating custom biquad filters with direct coefficient specification. This is useful for advanced filter design or when importing filter coefficients from external applications.

```json
{
  "type": "GenericBiquad",
  "a0": 1.0,
  "a1": -1.8,
  "a2": 0.81,
  "b0": 0.5,
  "b1": 0.0,
  "b2": -0.5
}
```

**Parameters:**
- `a0`: Denominator coefficient (typically normalized to 1.0)
- `a1`: Denominator coefficient
- `a2`: Denominator coefficient
- `b0`: Numerator coefficient
- `b1`: Numerator coefficient
- `b2`: Numerator coefficient

All coefficients default to neutral values (a0=1.0, b0=1.0, others=0.0) if not specified.

##### LowPass Filter

Used for creating low pass filters that attenuate high frequencies.

```json
{
  "type": "LowPass",
  "f": 5000,
  "db": 0.0,
  "q": 0.707
}
```

**Parameters:**
- `f`: Cutoff frequency in Hz
- `db`: Gain in decibels
- `q`: Q factor (determines steepness of roll-off)

##### HighPass Filter

Used for creating high pass filters that attenuate low frequencies.

```json
{
  "type": "HighPass",
  "f": 100,
  "db": 0.0,
  "q": 0.707
}
```

**Parameters:**
- `f`: Cutoff frequency in Hz
- `db`: Gain in decibels
- `q`: Q factor (determines steepness of roll-off)

##### LowShelf Filter

Used for boosting or cutting frequencies below a specified frequency.

```json
{
  "type": "LowShelf",
  "f": 300,
  "db": 6.0,
  "slope": 1.0,
  "gain": 6.0
}
```

**Parameters:**
- `f`: Cutoff frequency in Hz
- `db`: Gain in decibels
- `slope`: Shelf slope parameter
- `gain`: Shelf gain in decibels

##### HighShelf Filter

Used for boosting or cutting frequencies above a specified frequency.

```json
{
  "type": "HighShelf",
  "f": 8000,
  "db": 4.0,
  "slope": 1.0,
  "gain": 4.0
}
```

**Parameters:**
- `f`: Cutoff frequency in Hz
- `db`: Gain in decibels
- `slope`: Shelf slope parameter
- `gain`: Shelf gain in decibels

##### Volume Filter

Used for controlling overall volume.

```json
{
  "type": "Volume",
  "db": -6.0
}
```

**Parameters:**
- `db`: Volume level in decibels

##### Bypass Filter

Used for creating a pass-through filter that does not modify the audio signal. This is useful for temporarily disabling a filter slot without removing the filter configuration, or for creating placeholder filters.

```json
{
  "type": "Bypass"
}
```

**Parameters:**
- No parameters required

**Alternative name:** You can also use `"type": "PassThrough"` which is equivalent to `"type": "Bypass"`.

**Technical details:** The Bypass filter creates a unity biquad filter with coefficients b0=1, b1=0, b2=0, a0=1, a1=0, a2=0, resulting in a transfer function H(z) = 1 (unity gain, no filtering).

### Frequency Response Calculation

The API can calculate the frequency response of a filter or chain of filters at specified frequencies. The response is calculated in decibels, where 0 dB represents unity gain (no change in amplitude).

For complex filter chains, the individual filter responses are added together to produce the combined response.

**Example Request:**
```json
{
  "filters": [
    {"type": "LowShelf", "f": 100, "db": 3.0, "slope": 1.0, "gain": 3.0},
    {"type": "HighShelf", "f": 10000, "db": -2.0, "slope": 1.0, "gain": -2.0}
  ]
}
```

This would calculate the combined frequency response of a low shelf filter at 100Hz with +3dB gain and a high shelf filter at 10kHz with -2dB gain.

## Error Responses

All endpoints can return the following error responses:

### 400 Bad Request

Returned when the request is invalid.

```json
{
  "error": "Error message explaining the issue"
}
```

### 500 Internal Server Error

Returned when there's a server-side error.

```json
{
  "error": "Error message explaining the issue"
}
```

## Utility Functions

### Biquad Filter Detection

The API can identify metadata entries that represent biquad filters. A biquad filter follows the format "xxx/yy" where:

- xxx is any integer
- yy is an integer that is a multiple of 5

Examples of valid biquad filter values:
- "100/5"
- "1234/10"
- "5000/15"

This format detection is used by the `filter=biquad` query parameter in the metadata endpoint.