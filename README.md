![Python package](https://github.com/hifiberry/hifiberry-dsp/workflows/Python%20package/badge.svg)
[![PyPI version](https://badge.fury.io/py/hifiberrydsp.svg)](https://badge.fury.io/py/hifiberrydsp)
[![PyPI license](https://img.shields.io/pypi/l/ansicolortags.svg)](https://pypi.python.org/pypi/hifiberrydsp/)
[![PyPI download month](https://img.shields.io/pypi/dm/hifiberrydsp.svg)](https://pypi.python.org/pypi/hifiberrydsp/)
[![GitHub contributors](https://img.shields.io/github/contributors/hifiberry/hifiberry-dsp.svg)](https://gitHub.com/hifiberry/hifiberry-dsp/graphs/contributors/)

# HiFiberry DSP

Software for HiFiBerry boards equipped with DSP. This package can be 
used to read/write data to HiFiBerry DSP boards using the Beocreate TCP 
server.

## Installation

Before installing the dsptoolkit, you need to have a working Python 3
installation (>=3.5) and a working pip. You also need to enable SPI as
dsptoolkit needs SPI to communicate with the DSP.
Check out 
https://www.raspberrypi-spy.co.uk/2014/08/enabling-the-spi-interface-on-the-raspberry-pi/

You can then install the toolkit by just running
```bash
sudo pip3 install --upgrade hifiberrydsp
```

This will only install the software, but not activate the server.
Depending on your system, you might need to create a startup script 
or a systemd unit file for this.

If you're using a Debian based system (e.g. Debian, Raspbian), there
is a script that does all the work for you. Just run the following 
command:

```bash
bash <(curl https://raw.githubusercontent.com/hifiberry/hifiberry-dsp/master/install-dsptoolkit)
```

## sigmatcpserver

This server runs in background and provides a TCP interface (port 8089) 
to access DSP functions. It is compatible with SigmaStudio. That means 
you can directly deploy DSP programs from SigmaStudio and change 
parameters online.

You can also enable the REST API with this server:

```bash
sigmatcpserver --enable-rest
```

## Command line utility

The dsptoolkit command is the main command line tool to communicate 
with the DSP TCP server. The command line parameters are documented
in [doc/dsptoolkit.md](doc/dsptoolkit.md)


## REW integration

The software can be used to push filters created by Room Equalisation 
Wizard (REW) to the DSP.
Have a look at the guide in[doc/rew-basic.md](doc/rew-basics.md)

## REST API

The DSP REST API provides a REST interface to access metadata from the currently loaded DSP profile. It runs by default on localhost port 31415.

Start the API server either as a standalone:

```bash
dsp-metadata-server
```

Or integrated with the sigmatcpserver:

```bash
sigmatcpserver --enable-rest
```

Access the metadata:
```bash
curl http://localhost:31415/metadata
```

Read more about it in [doc/metadata-api.md](/doc/metadata-api.md).

## DSP profile format

DSP profiles can be generated directly in SigmaStudio. However, to 
enable the full potential of DSP Profiles and allow DSPToolkit to 
directly control the DSP program, you need to add some additional 
metadata to the XML file.
The process to create a DSP profile is documented in [doc/dspprofiles.md](/doc/dspprofiles.md)

