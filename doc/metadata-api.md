# DSP REST API

This document describes the REST API for retrieving metadata from the HiFiBerry DSP.

## Overview

The REST API provides access to the metadata from the currently loaded DSP profile through HTTP. It runs on localhost port 31415 by default.

## Starting the Server

You can start the REST API server in two ways:

### As a standalone server

```bash
dsp-metadata-server
```

By default, it will listen on localhost port 31415. You can change these settings with command line options:

```bash
dsp-metadata-server --host 0.0.0.0 --port 8000
```

Use `--debug` to enable more verbose logging:

```bash
dsp-metadata-server --debug
```

### Integrated with sigmatcpserver

You can also run the REST API alongside the SigmaTCP server:

```bash
sigmatcpserver --enable-rest
```

By default, it will use localhost:31415 for the REST API. You can customize this:

```bash
sigmatcpserver --enable-rest --rest-host 0.0.0.0 --rest-port 8000
```

## API Endpoints

### GET /metadata

Returns a JSON object containing all metadata from the currently active DSP profile.

**Response:**

```json
{
  "sampleRate": "48000",
  "profileName": "Beocreate Universal",
  "profileVersion": "10",
  "checksum": "40FB6C92F57ABB70177CE053C73F54DC",
  "balanceRegister": {
    "value": "799",
    "attributes": {
      "storable": "yes"
    }
  },
  "volumeControlRegister": {
    "value": "106",
    "attributes": {
      "storable": "yes"
    }
  },
  "IIR_A": {
    "value": "691/80",
    "attributes": {
      "storable": "yes"
    },
    "address": 691,
    "length": 80
  },
  "IIR_B": {
    "value": "611/80",
    "attributes": {
      "storable": "yes"
    },
    "address": 611,
    "length": 80
  },
  "_system": {
    "profileName": "Beocreate Universal",
    "profileVersion": "10",
    "sampleRate": 48000
  }
  // ... other metadata
}
```

## Usage from Python

You can use this API in your own Python code:

```python
import requests

response = requests.get('http://localhost:31415/metadata')
if response.status_code == 200:
    metadata = response.json()
    print(f"Profile name: {metadata.get('_system', {}).get('profileName')}")
    print(f"Volume control register: {metadata.get('volumeControlRegister')}")
```

## Error Handling

If there's an error retrieving the metadata, the API will return a JSON object with an "error" key:

```json
{
  "error": "Error message details"
}
```
