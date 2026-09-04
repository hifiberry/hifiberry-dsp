![Python package](https://github.com/hifiberry/hifiberry-dsp/workflows/Python%20package/badge.svg)
[![PyPI version](https://badge.fury.io/py/hifiberrydsp.svg)](https://badge.fury.io/py/hifiberrydsp)
[![PyPI license](https://img.shields.io/pypi/l/ansicolortags.svg)](https://pypi.python.org/pypi/hifiberrydsp/)
[![PyPI download month](https://img.shields.io/pypi/dm/hifiberrydsp.svg)](https://pypi.python.org/pypi/hifiberrydsp/)
[![GitHub contributors](https://img.shields.io/github/contributors/hifiberry/hifiberry-dsp.svg)](https://gitHub.com/hifiberry/hifiberry-dsp/graphs/contributors/)

# HiFiberry DSP

Software for HiFiBerry boards equipped with DSP. This package can be 
used to read/write data to HiFiBerry DSP boards using the Beocreate TCP 
server.

The software comes "as-is". There is no individual support for this software. Feel free to post in the [HiFiBerry forum](https://support.hifiberry.com/hc/en-us/community/topics/115000377385-DSP-boards-and-Beocreate) for questions. 

## sigmatcpserver

This server runs in background and provides a TCP interface (port 8089) 
to access DSP functions. It is compatible with SigmaStudio. That means 
you can directly deploy DSP programs from SigmaStudio and change 
parameters online.

You can also enable the REST API with this server:

```bash
sigmatcpserver --enable-rest
```

## REST API (Recommended)

The DSP REST API provides a RESTful interface to access metadata, memory, registers, and more from the currently loaded DSP profile. It runs by default on localhost port 13141.

The REST API can be enabled with the sigmatcpserver:

```bash
sigmatcpserver --enable-rest
```

Read the detailed documentation in [doc/restapi.md](/doc/restapi.md).

**Note:** The REST API is the recommended interface for all new development. It provides a more modern, flexible, and powerful way to interact with the DSP.

### Speaker presets

A speaker preset describes one loudspeaker as four DSP channels -- a biquad
bank, a role, a level, a delay and a polarity each. Applying one turns a bare
four-channel amplifier into an active crossover for that speaker.

Presets are read from `/usr/share/hifiberry/speaker-presets` (shipped by
`hifiberry-dspprofiles`) and `/var/lib/hifiberry/speaker-presets` (local); a
local preset shadows a shipped one of the same name. A preset is validated
when it is read: a non-numeric or negative `level`/`delayMs`, or a
non-boolean `invert`/`enabled`, is rejected there rather than surfacing later
as an untyped error out of an apply. Fields that are simply absent stay
legal.

- `GET /presets` -- installed presets with compatibility against the loaded
  profile, plus `current`, the applied preset for this profile
- `GET /presets/<id>` -- one preset in full. 404 when no file has that id;
  500 when a file exists but fails validation, so a hand-edited preset with
  a typo reports its own error instead of quietly disappearing from the list.
- `POST /presets/<id>/apply` -- write it to the DSP

Applying validates everything before writing anything: the loaded profile
must be the one the preset names, at least the version it names, at the same
sample rate, with filter banks at least as large as the preset needs, and
every channel's role must be one the loaded profile can express. Any of
these failing is a 409 and writes nothing -- in particular, a role the
profile has no name for is caught before the first bank is touched, not
discovered partway through the write. The coefficients are computed for one
sample rate, which is why a rate mismatch is refused rather than rescaled.
A successful apply is recorded so the preset survives a reboot and a profile
reload; if that record can't be written, the request reports a 500 rather
than a silent 200.

## Command line utility (Deprecated)

> **DEPRECATED:** The dsptoolkit command line interface is now considered deprecated. For new development, please use the REST API instead, which provides more functionality and better integration options.

The dsptoolkit command is the legacy command line tool to communicate 
with the DSP TCP server. The command line parameters are documented
in [doc/dsptoolkit.md](doc/dsptoolkit.md).

We are no longer adding new features to dsptoolkit and it will eventually be phased out. All new development should use the REST API instead.

## REW integration

The software can be used to push filters created by Room Equalisation 
Wizard (REW) to the DSP.
Have a look at the guide in [doc/rew-basic.md](doc/rew-basics.md)

## DSP profile format

DSP profiles can be generated directly in SigmaStudio. However, to 
enable the full potential of DSP Profiles and allow DSPToolkit to 
directly control the DSP program, you need to add some additional 
metadata to the XML file.
The process to create a DSP profile is documented in [doc/dspprofiles.md](/doc/dspprofiles.md)

## Contributing

When contributing to this project, please follow the AI and style guidelines in `.ai-guidelines` and `.ai-config.json`. This ensures consistent, professional documentation without decorative elements like emojis.

