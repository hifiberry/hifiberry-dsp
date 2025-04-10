# SigmaTCP Server Documentation

The `sigmatcpserver` is a daemon that provides a TCP interface for communication with HiFiBerry DSP boards. It implements the SigmaTCP protocol used by Analog Devices SigmaStudio to interact with DSP devices.

## Overview

The SigmaTCP server runs in the background and provides the following features:

- Compatible with SigmaStudio for DSP programming
- Provides a REST API for modern integration (optional)
- Supports ALSA volume control synchronization
- Supports LG Sound Sync
- Handles DSP program updates and parameter persistence

## Command-Line Options

```
sigmatcpserver [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--enable-rest` | Enable the REST API server (port 13141) |
| `--disable-tcp` | Disable the SigmaTCP server (only useful with --enable-rest) |
| `--alsa` | Enable ALSA volume control synchronization |
| `--lgsoundsync` | Enable LG Sound Sync functionality |
| `--restore` | Restore saved DSP parameters on startup |
| `--localhost` | Bind services to localhost only (more secure) |
| `-v, --verbose` | Enable verbose logging |

## Configuration

The server can be configured through a configuration file located at `/etc/sigmatcp.conf`.

Example configuration:

```ini
[server]
command_after_startup=/path/to/some/script.sh
notify_on_updates=http://localhost:8080/dsp-updated
```

### Configuration Options

- `command_after_startup`: A command to execute after the server has started
- `notify_on_updates`: A URL to send a POST request to when DSP program updates occur

## Usage Examples

### Basic Usage

Start the server with default options:

```bash
sigmatcpserver
```

### With REST API Enabled

Start the server with REST API enabled:

```bash
sigmatcpserver --enable-rest
```

### REST API Only Mode

Run only the REST API without the SigmaTCP server:

```bash
sigmatcpserver --enable-rest --disable-tcp
```

### Local-Only Mode

Run the server in local-only mode for better security:

```bash
sigmatcpserver --localhost
```

### With ALSA Volume Control

Enable ALSA volume control:

```bash
sigmatcpserver --alsa
```

### With All Features

Enable all available features:

```bash
sigmatcpserver --enable-rest --alsa --lgsoundsync --restore
```

## Systemd Integration

The server is typically run as a systemd service. You can control the service with the following commands:

```bash
# Start the service
sudo systemctl start sigmatcpserver

# Stop the service
sudo systemctl stop sigmatcpserver

# Enable at boot
sudo systemctl enable sigmatcpserver

# Disable at boot
sudo systemctl disable sigmatcpserver

# Check status
sudo systemctl status sigmatcpserver
```

## SigmaStudio Integration

The SigmaTCP server allows direct deployment of DSP programs from SigmaStudio. To connect SigmaStudio to the server:

1. Open SigmaStudio and your DSP project
2. Go to "Hardware Configuration"
3. Under "TCP/IP Settings", enter the IP address of your device
4. Use port 8089 (the default SigmaTCP port)
5. Click "Connect"

Once connected, you can download programs to the DSP and adjust parameters in real-time using SigmaStudio's interface.

## REST API Integration

When enabled with the `--enable-rest` option, the server also provides a RESTful API for interacting with the DSP. This API runs on port 13141 by default.

See [restapi.md](restapi.md) for detailed documentation on the REST API.
