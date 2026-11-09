# HiFiBerry DSP Debug Configuration

## Enabling Debug Mode

To enable debug logging of all DSP memory writes (including REST API and SigmaStudio TCP server):

1. Create `/etc/default/sigmatcpserver` with the extra option:
   ```bash
   echo 'SIGMATCP_OPTS="--debug"' | sudo tee /etc/default/sigmatcpserver
   ```

2. Restart the service:
   ```bash
   sudo systemctl restart sigmatcpserver
   ```

The service reads this file if it exists (`EnvironmentFile=-/etc/default/sigmatcpserver`
in the unit) and appends `$SIGMATCP_OPTS` to its built-in options, so the defaults,
including `--store --restore`, stay in effect. No such file is installed by the package.

For a one-off session you can also run the server in the foreground instead:
```bash
sudo systemctl stop sigmatcpserver
sudo sigmatcpserver --localhost --enable-rest --alsa --disable-tcp --store --restore --debug
```
Press Ctrl-C to stop it (this also stores the DSP memory), then
`sudo systemctl start sigmatcpserver`.

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

`SIGMATCP_OPTS` can hold any additional option, separated by spaces:

- `--debug` - Log all DSP memory writes
- `--verbose` - Enable verbose logging  
- `--alsa` - Enable ALSA volume control
- `--lgsoundsync` - Enable LG Sound Sync
- `--no-autoload-filters` - Disable filter autoloading

Options in `SIGMATCP_OPTS` are only added. To change or remove a built-in option, such as
`--disable-tcp` to allow SigmaStudio connections, override the whole command with
`sudo systemctl edit sigmatcpserver` (an empty `ExecStart=` line followed by the new one),
and keep `--store --restore` in it unless you want to lose the DSP memory across reboots.

## Disabling Debug Mode

To disable debug logging:

1. Remove the file, or remove `--debug` from `SIGMATCP_OPTS` in it:
   ```bash
   sudo rm /etc/default/sigmatcpserver
   ```
2. Restart the service:
   ```bash
   sudo systemctl restart sigmatcpserver
   ```
