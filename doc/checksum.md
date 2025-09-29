# DSP Program Checksums

## Overview

The HiFiBerry DSP toolkit provides checksum functionality to verify the integrity of DSP programs loaded into the ADAU145x processor. Checksums are essential for:

- **Program Verification**: Ensuring the DSP program has been loaded correctly without corruption
- **Change Detection**: Detecting when a different program has been loaded
- **Debugging**: Identifying communication issues or memory corruption
- **Quality Assurance**: Validating program integrity in production environments

## Checksum Algorithms

The system supports two cryptographic hash algorithms:

- **MD5**: Fast 128-bit hash, suitable for basic integrity checking
- **SHA-1**: More secure 160-bit hash, recommended for production use

## Program Memory Detection Methods

The DSP toolkit uses two different approaches to determine the extent of the program memory to checksum:

### 1. Signature-Based Detection

This is the traditional method that searches for a specific end-of-program signature in memory.

**How it works:**
- Reads the entire program memory space (0xC000-0xDFFF)
- Searches for the program end signature: `0x02 0xC2 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00`
- Includes the signature itself in the checksum
- If no signature is found but memory contains data, uses the full program space

**Advantages:**
- Works with any DSP program regardless of register configuration
- Historical compatibility with existing programs
- Fallback to full memory if signature is missing

**Disadvantages:**
- Must read entire program memory space
- Slower for large programs
- Includes potentially unused memory areas, enf of program signature could be missing sometimes

### 2. Length-Based Detection

This newer method uses the DSP's program length registers to determine the exact program size.

**How it works:**
- Reads program length from DSP registers (0xF463/0xF464)
- Only reads the exact amount of memory specified by the length registers
- More efficient as it avoids reading unused memory
- Does not depend on detecting an signature at the end of the program (that might be missing)

**Advantages:**
- More precise (exact program boundary)
- Consistent results regardless of memory padding

**Disadvantages:**
- Incompatible with old signature-based approach

## Checksum Types and Defaults

The system automatically determines which detection method to use based on the checksum algorithm:

### MD5 Checksums (Legacy)
- **Default Detection**: Signature-based
- **Rationale**: Maintains compatibility with existing systems and programs
- **Use Case**: Legacy applications, backward compatibility

### SHA-1 Checksums (Recommended)
- **Default Detection**: Length-based
- **Rationale**: More efficient and precise for modern DSP programs
- **Use Case**: New applications, production systems

## Priority System

When multiple checksums are available for a DSP profile, the system uses this priority order:

1. **SHA-1 (length-based)** - Highest priority
2. **MD5 (signature-based)** - Fallback option

This ensures that modern, efficient checksums are preferred while maintaining backward compatibility.

## XML Profile Integration

DSP profiles stored in XML format can include checksum attributes for validation:

### Checksum Attributes

- **`checksum`**: MD5 checksum (legacy, signature-based detection)
- **`checksum_sha1`**: SHA-1 checksum (modern, length-based detection)

### XML Profile Example

```xml
<ROM>
  <page>
    <!-- DSP program data -->
  </page>
  <metadata type="checksum">A1B2C3D4E5F6789012345678901234EF</metadata>
  <metadata type="checksum_sha1">FEDCBA0987654321ABCDEF1234567890A1B2C3D4</metadata>
  <metadata type="profileName">My DSP Profile</metadata>
</ROM>
```

### Profile Matching Priority

When the system searches for matching DSP profiles (e.g., during startup), it uses this priority:

1. **SHA-1 checksum match** (`checksum_sha1` attribute)
2. **MD5 checksum match** (`checksum` attribute)

This ensures that profiles with modern SHA-1 checksums are preferred while maintaining compatibility with legacy MD5-only profiles.

## API Usage

### Getting Checksums

```bash
# Get both MD5 and SHA-1 checksums (default modes)
curl http://localhost:8080/api/checksum

# Get specific algorithm with custom mode
curl "http://localhost:8080/api/checksum?algorithm=sha1&mode=signature"

# Get multiple algorithms
curl "http://localhost:8080/api/checksum?algorithm=md5,sha1"
```

### Response Format

```json
{
    "checksums": {
        "md5": {
            "digest": "A1B2C3D4E5F6789012345678901234EF",
            "mode": "signature",
            "length": 8192
        },
        "sha1": {
            "digest": "A1B2C3D4E5F6789012345678901234567890ABCDEF",
            "mode": "length", 
            "length": 6144
        }
    },
    "status": "success"
}
```

## Performance Considerations

### Caching

The system implements intelligent caching to minimize DSP memory access:

- **Memory Caching**: Program memory is cached per detection mode
- **Checksum Caching**: Calculated checksums are cached per algorithm and mode
- **Cache Invalidation**: Cache is cleared when new programs are loaded

### Efficiency Tips

1. **Use SHA-1 for new projects**: More efficient length-based detection
2. **Cache Results**: The API automatically caches results for repeated requests
3. **Batch Requests**: Request multiple algorithms in one API call when possible
4. **Avoid Full Memory**: Use length-based detection when registers are properly configured

## Troubleshooting

### Common Issues

**"No program memory found"**
- Ensure DSP is properly initialized
- Check SPI communication
- Verify DSP program is loaded

**"Length registers not set"**
- DSP program may not configure length registers
- Fall back to signature-based detection
- Use MD5 checksum which defaults to signature mode

**"Checksum mismatch"**
- Program may have been corrupted during loading
- Different detection modes may yield different results (this is normal)
- Ensure consistent checksum algorithm and mode for comparisons

### Debug Information

Enable debug logging to see detailed checksum calculation information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

This will show:
- Memory reading operations
- Cache hits/misses
- Detection mode selection
- Checksum calculation details

## Best Practices

1. **Choose Appropriate Algorithm**: Use SHA-1 for new projects, MD5 for legacy compatibility
2. **Consistent Comparison**: Always compare checksums using the same algorithm and detection mode
3. **Store Checksums**: Save checksums with DSP profiles for later verification
4. **Monitor Performance**: Use caching effectively to minimize DSP access
5. **Handle Errors**: Implement proper error handling for checksum calculation failures

## Example Use Cases

### Program Verification After Loading
```bash
# Load program
curl -X POST http://localhost:8080/api/program -d @program.xml

# Verify with checksum
CHECKSUM=$(curl -s http://localhost:8080/api/checksum | jq -r '.checksums.sha1.digest')
echo "Program loaded with SHA-1: $CHECKSUM"
```

### Comparing Different Programs
```bash
# Get checksum of current program
CHECKSUM1=$(curl -s http://localhost:8080/api/checksum?algorithm=sha1)

# Load different program
curl -X POST http://localhost:8080/api/program -d @other_program.xml

# Compare checksums
CHECKSUM2=$(curl -s http://localhost:8080/api/checksum?algorithm=sha1)
```

### Legacy Compatibility Check
```bash
# Get MD5 checksum (signature-based) for compatibility
curl "http://localhost:8080/api/checksum?algorithm=md5&mode=signature"
```