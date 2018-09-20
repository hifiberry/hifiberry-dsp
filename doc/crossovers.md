# Creating speaker crossovers with dsptoolkit

While you can always use SigmaStudio to design your individual DSP 
program for HiFiBerry DSP boards, for simple use cases, this might be
overkill. 

Therefore, we provide a simple way to create your own n-way crossovers
using a configuration file

## What you need

### DSP toolkit
First you need to have the DSP toolkit in at least version 0.10 installed.
Get it at https://github.com/hifiberry/hifiberry-dsp

### A DSP profile that supports a mixing/crossover matrix
A mixing/crossover matrix allows you to mix each input channel onto 
each output channel and also apply filtering.
In SigmaStudio it looks like this:

![crossover matrix](img/crossover-matrix.png)

We provide an example profile here:
https://raw.githubusercontent.com/hifiberry/hifiberry-dsp/master/sample_files/xml/4way-iir.xml

## Installing the DSP profile

First, you need to install the profile onto the DSP:
```
dsptoolkit install-profile 4way-iir.xml
```

You don't even have to download the profile by yourself as dsptoolkit 
directly accepts URLs:

```
dsptoolkit install-profile https://raw.githubusercontent.com/hifiberry/hifiberry-dsp/master/sample_files/xml/4way-iir.xml
```



## Create a crossover settings file

The settings files defines the filters used on each channel of the 
mixing/crossover matrix

A very simply example looks like this:

```
IIR_L1: pass
IIR_L2: mute
IIR_L3: mute
IIR_L4: mute
IIR_R1: mute
IIR_R2: pass
IIR_R3: mute
IIR_R4: mute
```

This settings will pass the left channel to output 1 of the DSP board
and the right channel to output 2 without any processing. This is 
basically a normal stereo fullrange configuration.

For a crossover, you need to use low-pass and high-pass filters. Let's 
do a simple 2 way setup with a crossover at 2kHz.
The connection to the DSP board is as follows:
- woofer left:   channel 1
- woofer right:  channel 2
- tweeter left:  channel 3
- tweeter right: channel 4

On the Beocreate 4 channel amplifier it is recommended to connect woofers
to channels 1 and 2 as these can provide twice the power of channels 
3 and 4

```
IIR_L1: lp:2000Hz
IIR_L2: mute
IIR_L3: hp:2000Hz
IIR_L4: mute
IIR_R1: mute
IIR_R2: lp: 2000Hz
IIR_R3: mute
IIR_R4: hp: 2000Hz
```

With this settings configuration, 
* output 1 receives a signal from the left channel filtered with a 2kHz low-pass filter
* output 2 receives a signal from the right channel filtered with a 2kHz low-pass filter
* output 3 receives a signal from the left channel filtered with a 2kHz high-pass filter
* output 4 receives a signal from the right channel filtered with a 2kHz high-pass filter

## Applying the crossover

Save you crossover file as a file, e.g. crossover.txt. Then use 
dsptoolkit to apply the settings on the DSP

```
dsptoolkit apply-settings crossover.txt
```

This will apply the settings just in the DSP RAM, not store them 
permanently. This is recommended especially when you develop crossovers
as it is the fastest way to apply settings and fix potential problems.
Sometimes things can go wrong, e.g. if you have mixed up channels.
In this case, just edit the file and apply the settings again.

In rare cases it can happen that something is completely wrong and you
fear that your speakers might be damaged (e.g. if you have accidentelly 
applied a huge volume increase). In these cases, the fastest way to 
return to the default settings is to reset the DSP:

```
dsptoolkit reset
```

This will load the standard settings from the DSP's EEPROM.

## Optimizing the crossover

In most cases a crossover like this won't work perfectly as this would
only be correct if woofers and tweeters have exactly the same efficiency.
Usually the tweeters will be some decibels too loud. You can correct 
this with an additional "vol" filter:

```
IIR_L1: lp:2000Hz
IIR_L2: mute
IIR_L3: hp:2000Hz,vol:-3dB
IIR_L4: mute
IIR_R1: mute
IIR_R2: lp: 2000Hz
IIR_R3: mute
IIR_R4: hp: 2000Hz, vol:-3dB
```

This would reduce the volume of the tweeters by 3dB

## Further optimizations

There are a lot more optimisations you can do here:

### Adding a subsonic filter

Filtering low frequencies that the speaker can't really handle is 
often a good idea:
```
IIR_L1: lp:2000Hz,hp:30Hz,hp:30Hz
```
This adds a 4th order high-pass filter to the woofer channel that 
removes very low frequencies. Depending on your speaker a value 
between 20 and 100Hz might be used

### Filtering specific frequencies

The frequency response of almost any loudspeakers isn't really flat.
So you might add some filters to increase or decrease the volume at 
a specific frequency:

```
IIR_R4: hp: 2000Hz, vol:-3dB, eq:5000Hz,2,+2dB
```

Note that you will need measurement equipment to correctly design these
filters.

### Delays for specific channels 

It might be necessary to delay a channel a bit (often the tweeter). If the profile
supports delays, you can configure them also with settings:

```
delay1: 100
```

Note that the delay is defined in samples. At 48kHz the lengths of a sample is roughly 
0.02ms. So a delay 100 means approximately 2ms delay. If your profile is using a 
different sample rate, you need to do the calculations according to your sample rate
(which is the internal DSP sample rate, NOT the sample rate of music you want to  
play back).

## Write the settings to the EEPROM

If your crossover is working as expected, you should save it to the 
EEPROM of the DSP board. This ensures that the crossover is still 
correctly configured after a reboot.

```
dsptoolkit store-settings crossover.txt
```

Check if is stored correctly by resetting the DSP:

```
dsptoolkit reset
```


## Merge the settings into an existing DSP profile

If you want to share your settings or apply the profile including these
settings on another system, it can help to merge the settings into
an existing XML DSP profile. 
This can also be done with dsptoolkit by just adding the file name of 
the XML profile file:

```
dsptoolkit store-settings crossover.txt profile.xml
```

Note that this will NOT apply the settings directly to the DSP, but 
only to the XML profile file.
