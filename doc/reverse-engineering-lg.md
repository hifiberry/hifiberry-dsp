# Reverse engineering LG SoundSync

LG TVs have a feature calles "SoundSync (optical)" that allows the TV to control the
volume of a sound bar or speaker that is connected via SPDIF.
As this might be useful, let's see if we can find out how this works.

## Basics

SPDIF is a one-way protocol. There is no feedback from the receiver to the sender.
Therefore no negotiation between sender and receiver is possible. SPDIF sends a 
left/right data stream. In addition to the PCM data, additional status and user bits
can be set. Unfortunately there is no common standard to encode control information 
into these bits.

I would expected that LG uses some of these bits to send additional control information.
Let's have a look.

## Status of the SPDIF registers with no active SPDIF

```
0xf61: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 02 02 00 8C 04
0xf62: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 02 00 8C 04
```

## Status of the SPDIF registers with active SPDIF

```
0xf61: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 02 02 00 8C 04
0xf62: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 02 00 8C 04
```

no change yet

## Status of the SPDIF registers with LG Sound Sync optical

```
0xf61: 00 00 00 00 00 00 00 00 00 00 01 E0 00 00 00 10 1F 04 8A 62 02 00 8C 04
0xf62: 00 00 00 00 00 00 00 00 00 00 01 E0 00 00 00 10 1F 04 8A 60 02 00 8C 04
```

Now, we see additional channel status bits set

## Changing the volume

```
0xf61: 00 00 00 00 00 00 00 00 00 00 00 60 00 00 00 11 9F 04 8A 62 02 00 8C 04
0xf62: 00 00 00 00 00 00 00 00 00 00 00 60 00 00 00 11 9F 04 8A 60 02 00 8C 04
```

Looks like this changes some status bits - cool :-)

## Setting volume to 0

```
0xf61: 00 00 00 00 00 00 00 00 00 00 01 F0 00 00 00 10 0F 04 8A 62 02 00 8C 04
0xf62: 00 00 00 00 00 00 00 00 00 00 01 F0 00 00 00 10 0F 04 8A 60 02 00 8C 04
```

## Setting volume to max

```
0xf61: 00 00 00 00 00 00 00 00 00 00 07 B0 00 00 00 16 4F 04 8A 62 02 00 8C 04
0xf62: 00 00 00 00 00 00 00 00 00 00 07 B0 00 00 00 16 4F 04 8A 60 02 00 8C 04
```

## Setting volume to 50%

```
0xf61: 00 00 00 00 00 00 00 00 00 00 02 D0 00 00 00 13 2F 04 8A 62 02 00 8C 04
0xf62: 00 00 00 00 00 00 00 00 00 00 02 D0 00 00 00 13 2F 04 8A 60 02 00 8C 04
```

## Setting volume to 51%

```
0xf61: 00 00 00 00 00 00 00 00 00 00 02 C0 00 00 00 13 3F 04 8A 62 02 00 8C 04
0xf62: 00 00 00 00 00 00 00 00 00 00 02 C0 00 00 00 13 3F 04 8A 60 02 00 8C 04
```

## Setting volume to 52%

```
0xf61: 00 00 00 00 00 00 00 00 00 00 02 B0 00 00 00 13 4F 04 8A 62 02 00 8C 04
0xf62: 00 00 00 00 00 00 00 00 00 00 02 B0 00 00 00 13 4F 04 8A 60 02 00 8C 04
```

## Setting volume to 53%

```
0xf61: 00 00 00 00 00 00 00 00 00 00 02 A0 00 00 00 13 5F 04 8A 62 02 00 8C 04
0xf62: 00 00 00 00 00 00 00 00 00 00 02 A0 00 00 00 13 5F 04 8A 60 02 00 8C 04
```

## Conclusions

It seems the volume information is encoded multiple times. It might be the 
easiest way to use Bytes 16/17 and map the range 0x100f - 0x164F to the volume
range 0-100%.

This gives the simple formula:

value = 0x100f + percent * 0x0010

Checking bytes 18/19 for 0x048A seems to indicate that SoundSync is active.

## Other

- More about channel status bits 
https://www.av-iq.com/avcat/images/documents/pdfs/digaudiochannelstatusbits.pdf
