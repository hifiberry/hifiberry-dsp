Settings file format
====================

A settings file is a text file that consists of lines of attribute:value pairs. Attributes are register names defined in the profile metadata.  
Values can be

- float values
- integer values
- decibel values (in format +xdb, -xdb)
- percent values (for volume, will be converted to a -60db-0dB volume control range)
- IIR filter definitions (see above)

Example
-------

Let's assume the following DSP profile:

```xml
<ROM>
  <beometa>
    <metadata type="IIR_L">37/80</metadata>
    <metadata type="IIR_R">117/80</metadata>
    <metadata type="IIR_L1">197/40</metadata>
    <metadata type="IIR_R1">237/40</metadata>
    <metadata type="IIR_L2">277/40</metadata>
    <metadata type="IIR_R2">317/40</metadata>
    <metadata type="IIR_L3">357/40</metadata>
    <metadata type="IIR_R3">397/40</metadata>
    <metadata type="IIR_L4">437/40</metadata>
    <metadata type="IIR_R4">477/40</metadata>
    <metadata type="balanceRegister">525</metadata>
    <metadata type="channelSelectRegister">546</metadata>
    <metadata type="volumeControlRegister">541</metadata>
    <metadata type="volumeLimitRegister">542</metadata>
  </beometa>
  ....
</ROM>
```

A simple settings file for this DSP profile could look like this:

```
volumeLimitRegister: -10dB
```

Applying these settings would set the the volumeLimit to -10dB.

You can check this by running the command

```bash
dsptoolkit get-limit
```

A more complex file:

```
volumeControlRegister: -3dB
volumeLimitRegister: 90%
mute: 0x1
balanceRegister: 0.8
IIR_L: lp:1500Hz, hp:300Hz:0.6, eq: 1200Hz:2:+3dB, vol:-1dB
IIR_R1: vol: +3dB
IIR_R2: vol: -3dB
IIR_R3: vol: +0dB
```

In this case, the mute setting would be ignored as no mute attribute is available in the DSP profile.
