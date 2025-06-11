# HiFiBerry DSP REST API Documentation

This document describes the REST API provided by the HiFiBerry DSP service for interacting with DSP profiles and memory.

## Base URL

The API server runs by default on:
```
http://localhost:13141
```

## Endpoints

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

**Example Response:**
```json
{
  "address": "0x100",
  "values": ["0x12345678", 1.23, -0.45],
  "status": "success"
}
```

**Note on Float Values:**
When using floating-point values, they must be within the valid range for the SigmaDSP fixed-point representation (approximately -256 to 256). Values will be automatically converted to the appropriate 32-bit fixed-point representation understood by the DSP.

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

Get information about the current cache status, including whether the XML profile and metadata are cached.

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
  }
}
```

#### Clear Cache

Clear the internal XML profile cache. This is useful if the DSP profile file has been updated externally.

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