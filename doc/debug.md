# HiFiBerry DSP Debug Configuration

## Enabling Debug Mode

To enable debug logging of all DSP memory writes (including REST API and SigmaStudio TCP server):

1. Edit the configuration file:
   ```bash
   sudo systemctl edit sigmatcpserver
   ```

2. Add these lines on top:
   ```ini
   [Service]
   ExecStart=
   ExecStart=sigmatcpserver --localhost --enable-rest --alsa --disable-tcp --debug

   ```

3. Restart the service:
   ```bash
   sudo systemctl restart sigmatcpserver
   ```

## Viewing Debug Logs

To view the debug output:
```bash
sudo journalctl -u sigmatcpserver -f
```

## Debug Output Format

When debug mode is enabled, you'll see log entries for all memory writes including:
- Direct memory writes via REST API (`/memory` endpoint)
- Biquad filter writes via REST API (`/biquad` endpoint) 
- Register writes via REST API (`/register` endpoint)
- Memory writes from SigmaStudio via TCP server

Example debug output:
```
DEBUG: Memory write to address 0x1234 (4660), length: 20 bytes
DEBUG: Write data: 01 00 00 00 FF FE 12 34 ...
```

## Coverage

Debug logging captures all DSP memory writes regardless of the source:
- **REST API**: All endpoints that write to DSP memory (`/memory`, `/biquad`, `/register`)
- **TCP Server**: All writes from SigmaStudio or other TCP clients
- **Internal Operations**: Profile loading, filter application, etc.

## Available Options

You can also add other options:

- `--debug` - Log all DSP memory writes
- `--verbose` - Enable verbose logging  
- `--alsa` - Enable ALSA volume control
- `--lgsoundsync` - Enable LG Sound Sync
- `--no-autoload-filters` - Disable filter autoloading

## Disabling Debug Mode

To disable debug logging:

1. Remove the override:
   ```bash
   sudo rm /etc/systemd/system/sigmatcpserver.service.d/override.conf
   ```
2. Reload the unit:
   ```bash
   sudo systemctl daemon-reload
   ```
3. Restart the service:
   ```bash
   sudo systemctl restart sigmatcpserver
   ```
