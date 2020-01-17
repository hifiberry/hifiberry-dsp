# Creating your own client

While dsptoolkit as a command line client works well, you might want to integrate DSP control in your own application. This document describes some use cases and recommendations how to implement these.

## Communication with the DSP

### dsptoolkit

The easiest way to communicate with the DSP is using the dsptoolkit as a command line tool. Even if your users don't use it directly, you can call it from your program to communicate with the DSP. While this isn't the most performant way, it integrates a lot of checks that make sure only supported parameters will be updated.

### TCP socket

You can directly communicate with the sigmatcpserver processing using TCP. The protocol is used by Analog's SigmaStudio,
but it was extended by us to support more features.
There is no authentication supported (as this would break SigmaStudio compatibility).
There is no document that describes the protocol in detail. It is recommended, to have a look at the Python source code.

### SPI

This is the lowest-level approach to communicate with the DSP. It is not recommended for most use cases for the following reasons:

- If the sigmatcpserver is running, it already blocks access to SPI
- You need to deal with the internals of the DSP chip
- There are no high-level functions (e.g. changing the volume), all these have to be implemented again.

## The DSP program

HiFiBerry DSP boards can be programmed by the user. While this offers a great flexibility, there are some risks.
DSP toolkits usually write to a specific memory cell of the DSP to change parameters. The addresses of these cells usually
depend on the deployed DSP program. Most commercial DSPs use a fixed DSP program that can only be parametrised.
This has the advantage that the addresses of all parameters are known and static. The client can just write to a given address.

With the HiFiBerry DSP products, it is a bit more complicated. As the user can change the DSP program at any time, you can't
be sure that a given DSP program is running. sigmatcpserver and dsptoolkit deal with this using 2 methods:

1. Checksum  
   There is checksum for the DSP program running. If the program changes, the checksum will also change
2. DSP profiles  
   DSP profiles include metadata that map specific functions to memory addresses. This allows the client to check what features are supported by a specific DSP program and look up the memory addresses of these features.

## Updating parameter values

To update specific paramaters e.g. filters in a BiQuad filter bank, we recommend the following:

1. Get the checksum from sigmatcpserver and cache it locally
2. Get the DSP profile from sigmatcperver
3. Parse the profile and find the memory addresses
4. Update the parameter

For live updates of specific parameters (e.g. user directly modifies a parameter using gestures), it is usually not needed to always check the checksum again as this might create some lagging.
However, we recommend getting the checksum again and checking if the users didn't interact with the application for some time.

If you're 100% sure the user won't upload another DSP profile while they're working with your application, you might skip the checksum verification.
