# HiFiBerry DSP REST API Documentation

This document describes the REST API provided by the HiFiBerry DSP service for interacting with DSP profiles and memory.

## Base URL

The API server runs by default on:
```
http://localhost:31415
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

Get metadata with keys starting with "eq1_":
```
GET /metadata?start=eq1_
```

Get only biquad filter metadata:
```
GET /metadata?filter=biquad
```

Get biquad filters with keys starting with "eq1_":
```
GET /metadata?filter=biquad&start=eq1_
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

Read 2 memory cells starting at address 0x200 in integer format:
```
GET /memory/0x200/2?format=int
```

Read 1 memory cell at address 0x300 in floating-point format:
```
GET /memory/0x300?format=float
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

2. Floating-point values (automatically converted to DSP fixed-point format):
```json
{
  "address": "0x100",
  "value": [1.23, -0.45, 0.0078125]
}
```

3. Mix of formats:
```json
{
  "address": "0x100",
  "value": ["0x12345678", 1.23, -0.45]
}
```

4. Single value:
```json
{
  "address": "0x100",
  "value": "0x12345678"
}
```

or

```json
{
  "address": "0x100",
  "value": 1.23
}
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