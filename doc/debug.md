# HiFiBerry DSP Debug Configuration

## Enabling Debug Mode

To enable debug logging of all DSP memory writes:

1. Edit the configuration file:
   ```bash
   sudo nano /etc/default/sigmatcpserver
   ```

2. Uncomment the DEBUG_OPTIONS line:
   ```bash
   DEBUG_OPTIONS="--debug"
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

When debug mode is enabled, you'll see log entries like:
```
DEBUG: Memory write to address 0x1234 (4660), length: 20 bytes
DEBUG: Write data: 01 00 00 00 FF FE 12 34 ...
```

## Available Options

You can also add other options in `/etc/default/sigmatcpserver`:

- `--debug` - Log all DSP memory writes
- `--verbose` - Enable verbose logging  
- `--alsa` - Enable ALSA volume control
- `--lgsoundsync` - Enable LG Sound Sync
- `--no-autoload-filters` - Disable filter autoloading

## Disabling Debug Mode

To disable debug logging:

1. Edit `/etc/default/sigmatcpserver`
2. Comment out or remove the DEBUG_OPTIONS line:
   ```bash
   #DEBUG_OPTIONS="--debug"
   ```
3. Restart the service:
   ```bash
   sudo systemctl restart sigmatcpserver
   ```
