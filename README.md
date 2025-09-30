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

