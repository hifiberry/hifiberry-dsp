# DSP Settings Store

The DSP settings store persists filter and memory configurations across reboots. It is managed by the DSP REST server (`sigmatcpserver`) and stored as a JSON file on disk.

## File Location

```
/var/lib/hifiberry/dspsettings.json
```

Previously named `filters.json` (renamed in 1.3.0).

## How It Works

1. When filters are set via the `/biquad` REST endpoint, they are automatically written to the settings store.
2. Memory settings written via `/memory` with `store=true` are also persisted.
3. On startup, the DSP server restores all stored settings for the currently active DSP profile.
4. Settings are organized by DSP profile checksum, so different profiles maintain independent filter/memory configurations.

## JSON Structure

```json
{
  "PROFILE_CHECKSUM": {
    "filters": {
      "filterKey_offset": {
        "address": "customFilterRegisterBankLeft",
        "offset": 0,
        "filter": {
          "type": "PeakingEq",
          "f": 1000,
          "db": -3.0,
          "q": 1.0
        },
        "timestamp": 1699564123.456,
        "bypassed": false
      }
    },
    "memory": {
      "memoryAddress": {
        "address": "4744",
        "values": [1.0, 0.5],
        "timestamp": 1699564567.89
      }
    }
  }
}
```

### Top-level keys

Each top-level key is a DSP profile checksum (uppercase hex string, e.g. `0A33FEBFD64AC92B1EED630B1499E8E29C06E598`). This allows multiple profile configurations to coexist in the same file.

### Filter entries

Each filter entry key follows the pattern `{address}_{offset}`, e.g. `customFilterRegisterBankLeft_3`.

| Field | Description |
|-------|-------------|
| `address` | DSP metadata register name (e.g. `customFilterRegisterBankLeft`, `eq1_band1`) |
| `offset` | Position within the filter bank (0-based index) |
| `filter` | Filter parameters — either named (type/f/db/q/gain/slope) or raw biquad coefficients (a0/a1/a2/b0/b1/b2) |
| `timestamp` | Unix timestamp of when the filter was last written |
| `bypassed` | Whether the filter is currently bypassed (original coefficients preserved, unity written to DSP) |

### Filter types

Named filters use a `type` field:

| Type | Parameters |
|------|-----------|
| `PeakingEq` | `f`, `db`, `q` |
| `HighShelf` | `f`, `db`/`gain`, `slope` |
| `LowShelf` | `f`, `db`/`gain`, `slope` |
| `Highpass` | `f`, `q` |
| `Lowpass` | `f`, `q` |

Unity/passthrough filters are stored as raw biquad coefficients with `b0=1, b1=0, b2=0, a0=1, a1=0, a2=0`.

### Memory entries

Memory entries store raw DSP memory values at specific addresses. These are used for non-filter settings like volume limits or custom DSP parameters.

## Filter Bank Addresses

Common filter bank addresses defined in DSP profile metadata:

| Address | Description |
|---------|-------------|
| `customFilterRegisterBankLeft` | Left channel custom EQ filters |
| `customFilterRegisterBankRight` | Right channel custom EQ filters |
| `eq1_band1` ... `eq1_bandN` | Individual EQ band registers |

The exact addresses depend on the DSP profile loaded on the device.

## Data Integrity

The settings store includes corruption recovery:

- Corrupted files are backed up with a `.corrupted.{timestamp}` suffix before being repaired
- Common JSON corruption (truncation, encoding issues) is auto-fixed on load
- Checksum keys are normalized to uppercase to prevent duplicates
- Legacy filter-only format (pre-memory support) is auto-migrated

## Related API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /filters?current=true` | Get stored filters for the active DSP profile |
| `GET /filters?checksum=...` | Get stored filters for a specific profile |
| `POST /filters` | Manually store filters without applying to DSP |
| `DELETE /filters?checksum=...` | Delete stored filters |
| `DELETE /filters?all=true` | Delete all stored filters |

See [restapi.md](restapi.md) for full API documentation.

## Implementation

The settings store is implemented in `SettingsStore` class at:
```
src/hifiberrydsp/api/settings_store.py
```
