Command line utility
====================

dsptoolkit is a tool that is used to directly access functions of the DSP via the TCP server. This means it can run on another system.

The general usage pattern is

```bash
dsptoolkit command parameter
```

The following commands are supported. Note that some command need specific parameters in the DSP profile. If the DSP profile does not support these, the command won't have any effect.

* `install-profile`

  writes a DSP profile to the DSP EEPROM and activates it. A profile installed with this command will be automatically started after a reset.
  
* `set-volume volume`

  set the volume. Volume values can be defined in real values (0-1), percent (0% to 100%) or decibels (you need to use negative values to reduce the volume)
  For negative db values, you need to prefix these with `--`, e.g.  
    `dsptoolkit set-volume -- -3db`

* `adjust-volume volume`

  adjust the volume. Volume adjustment values can be defined just as for `set-volume`. With `adjust-volume`, the current volume is adjusted by the chosen amount, instead of setting it to a fixed level.
  For negative db values, you need to prefix these with `--`, e.g.  
    `dsptoolkit adjust-volume -- -3db`

* `get-volume`

  gets the current setting of the volume control register.

* `set-limit`

  sets the volume limit. The effect is the same as setting volume. The idea of this setting is having a volume control that can be changed between 0 and 100% (or -inf dB to 0dB) and the limit setting to set the maximum volume of the system.
  For negative db values, you need to prefix these with `--`, e.g.  
    `dsptoolkit set-limit -- -3db`

* `apply-rew-filters|apply-rew-filters-left|apply-rew-filters-right filename`

  Deploys parametric equaliser settings calculated by REW to the equaliser filter banks (left, right or both).
  Not all DSP profiles will support this setting.
  To make sure the filters are still active after a system reboot, make sure you use the store command.

* `apply-fir-filters|apply-fir-filters-left|apply-fir-filters-right`

  Deploys a FIR (finite impulse response) filter to the left, right or both FIR filter banks.
  A FIR filter file is a simple text file with one real number per line.
  Not all DSP profiles will support this setting.
  To make sure the filters are still active after a system reboot, make sure you use the store command.

* `clear-iir-filters`

  Resets the IIR filter banks to default values. This is helpful if you deployed filters to the DSP that do not perform as expected

* `read-dec|red-int|read-hex address`

  Reads a memory word from the given address and interprets it as a decimal value, integer value or just displays it as a HEX value.
  Addresses are 2byte long and they can be defined as integers or hex values.
  Hex values are defined by the prefix `0x` (e.g. `0x01aa`)

* `loop-read-dec|loop-read-int|loop-read-hex address`
  
  Works exactly like the read-xxx command. However, it reads the values in a loop. This is often useful when debugging DSP programs as you can easily see if and how parameters change

* `write-reg address value`

  Writes a value to a 2-byte register. This command should be used to write the DSP register addresses. While it will also accept DSP RAM addresses, these are 4 bytes long and the command will only set the first 2 bytes of a RAM cell.

* `write-mem address value`

  Writes a 4 byte value to a memory cell.
  The value can be given as an integer or hex value.
  When using this command on register addresses, the command will write to 2 consecutive register addresses as addresses have a length of only 2 bytes.
  
* `mute|unmute`

  Mutes/unmutes the output. This only works if the profile supports a mute register.

* `servers`

  Find all servers on the local network using Zeroconf.
  
* `apply-settings settings-file`

  Apply the parameter settings from the given parameter file to the running program.
  
* `store-settings settings-file [xml-file]`

  Apply the parameter from the given parameter file to the running program. Also store them into the given DSP profile.
  This means, the default settings of this DSP Profile will be changed.
  There are 2 possible ways to merge this into a DSP profile:
  1. If an XML file is given in the command line, the settings will be applied to this DSP profile. The profile file will be edited.  
     A backup version of teh DSP profile will be stored.
  2. If no xml-file parameter is given, dsptoolkit retrieves the currently running DSP program directly from the server, applies the settings and pushed the profile back to the server. In this case, the server not only activated this, but also stores the changed settings to the EEPROM. They will then be automatically activated after a reset of the DSP board.

* `save`

  saves the current parameter RAM to the file system. This is recommended if you have deployed new filters or changed other settings that should be re-activated later.  
  This does NOT save anything to EEPROM.

* `load`

  restores the parameter RAM from the file system.

* `store-filters`

  Store filters currently deployed in the IIR and FIR filter banks to the EEPROM.
  
* `store`

  Store all known parameter settings (filters, volume, balance) that are currently active on the DSP to the DSP's EEPROM.
  Resetting the EEPROM will than recover these settings.
  
* `reset`

  Resets the DSP. The program will be loaded from the EEPROM. The parameter RAM won't be stored and/or recovered from the file system.
