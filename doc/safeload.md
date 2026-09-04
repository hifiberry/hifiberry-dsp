# Safeload

A biquad occupies five consecutive cells in DSP data memory. Writing them
one at a time while the core is running means the core can execute a frame
against a slot that holds two coefficients of the new filter and three of
the old one. The result is a filter that exists only for that frame, and
whose response is not the old one or the new one. It is audible as a click
on an EQ change, and on a crossover it is a moment of wrong slope.

SigmaStudio's answer is *software safeload*: the words are staged in a
window in memory, and the core copies them to their real destination
between two frames. The update is then atomic from the audio's point of
view.

## The staging window

The window is seven consecutive cells at the start of DM1:

| Address | Meaning |
|---|---|
| `0x6000` – `0x6004` | up to five data words |
| `0x6005` | address the words belong at |
| `0x6006` | number of words, 1 to 5 |

Writing the count is what asks the core to act. The core performs the copy
at the next frame boundary and then writes zero back to the count cell, so
the handshake can be observed rather than guessed at: read `0x6006` until
it reads zero.

The whole request is one SPI burst of seven words, so posting it costs no
more than a single-cell write did.

## How the toolkit uses it

`Adau145x.write_biquad()` goes through safeload by default. Nothing needs
to be configured, and callers of the REST API see no difference beyond the
filter arriving in one piece.

The raw memory writes of the SigmaTCP protocol do not: a client sending
five separate cell writes still gets five separate cell writes, so
`dsptoolkit set-filters` is unchanged. The protocol carries a safeload flag
that the server does not act on yet.

The primitive underneath is available on its own:

```python
Adau145x.safeload_write(address, words)   # 1..5 words, returns True/False
```

This is the low-level primitive. It posts the request and waits, and it
does not probe, verify the transfer or restore the window - on a program
whose safeload support is not established, use `write_biquad()`, which
does all three. It returns `True` when the DSP consumed the request and
`False` when the request went unanswered — see the next section for what that means. The
words are passed in the DSP's own 8.24 format, as `decimal_repr()` returns
them; `safeload_write()` does not convert.

## Programs without safeload

Safeload is an option of the SigmaStudio project, not a property of the
chip. A program compiled without it never looks at the staging window, and
those seven cells are then ordinary DM1 data belonging to the program.

The toolkit therefore probes rather than assumes, and the first filter
write after a program is loaded doubles as the probe:

1. If the core is stopped, do not probe at all. See below.
2. If the slot already holds the words about to be written, do not probe
   either: the readback could not tell a transfer from what was already
   there.
3. Read the seven cells.
4. Post the request and poll the count cell for up to 10 ms.
5. If the count clears, read the slot back and check the words are really
   there.
6. Only then does the program count as supporting safeload. Remember that
   and use it for every later write.
7. Otherwise put the seven cells back exactly as they were, remember that
   the program has no safeload, and write the coefficients directly - one
   cell at a time, highest address first, which is what the toolkit did
   before safeload existed.

Step 5 is not belt and braces. On a program without safeload those seven
cells are ordinary data belonging to the running program, and the cell
being polled may hold zero for reasons of its own. Taking the handshake
as proof would mean posting every later filter into a window nobody
reads, while reporting success each time. The comparison is against the
values as they go on the wire, not the Python integers: `decimal_repr()`
can return 2**32 for a coefficient just below zero, and `int_data()` puts
that on the wire as four zero bytes.

The probe is not free on a program that turns out not to implement
safeload. For as long as the poll lasts, seven cells of that program's
live data hold a filter instead of whatever they held before. That is why
the timeout is 10 ms rather than something leisurely -- the core answers
within one audio frame, about 21 us, so the wait is already ample margin
-- why the answer is remembered instead of asked again, and why a probe
that could not prove anything is skipped rather than attempted.

The window is put back on any path that does not end in a proven
transfer, including an error part-way through the handshake. Otherwise
the coefficients left behind would be read as the program's own data by
the next probe, and faithfully restored over it.

So an unsupported program is probed once, gets its seven cells put back,
and is not probed again until a different program is loaded. The answer
belongs to the program, so it is reset by
`Adau145x.clear_checksum_cache()`, which already runs on a program
change, and can be reset by hand with
`Adau145x.reset_safeload_detection()`.

The Beocreate Universal profile is known to support safeload, verified on
a Beocreate 4-Channel Amplifier. The other profiles HiFiBerry ships have
not been checked on hardware; the probe settles it either way at run time,
which is the reason it exists.

## A stopped core

Several operations stop the core to get a consistent read -- every block
memory read does -- and start it again afterwards, with the bus free in
between. A TCP client can stop it too, by writing the registers itself.

A probe that ran in one of those windows would time out and say nothing
about the program, so the core's state is read from the chip before
probing, and read again before a failure is recorded. `HIBERNATE` and
`KILLCORE` both read back what was written, verified on hardware. Asking
the chip is deliberate: a flag maintained by `kill_dsp()` and
`start_dsp()` would miss a TCP client stopping the core, and would stay
wrong if an error left it stale.

Nothing is recorded while the core is down, so the next write with the
core running probes as usual.

## Locking

The staging window is a single shared resource. If a second request is
posted before the core has consumed the first, the first one is silently
replaced and that filter is simply never applied.

Several threads write to the DSP — the REST API workers, the ALSA volume
sync, the TCP server — so `safeload_write()` holds the SPI bus lock across
the write *and* the polling reads that follow it. The lock lives on
`SpiHandler` because every path to the DSP goes through it, and it is
reentrant so nested reads and writes are free to take it again.

A request is normally consumed within one audio frame, about 21 µs at
48 kHz, so the lock is held for one poll in the ordinary case.
