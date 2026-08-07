# DSP boot behaviour and what it does to profile deployment

Maintainer notes. This file is **not packaged** — `src/setup.py` uses an
explicit `packages=[...]` list with no `package_data`, no
`include_package_data` and no `MANIFEST.in`, so setuptools installs only `.py`
files from these directories. Keep it that way if you add more notes here.

## The DSP boots from its own EEPROM, and a Pi reboot does not reset it

The DSP self-boots its program from the external EEPROM on the board at
power-on.

Deploying a profile — `POST /dspprofile`, or the equivalent `dsptoolkit`
call — **writes the EEPROM**. It does not change the program the DSP is
currently executing.

**Rebooting the Pi does not reboot the DSP.** A warm reboot
(`systemctl reboot`) leaves the DSP powered and running whatever program it
booted with. Only an actual DSP reset — a power cycle, or the GPIO 17 reset
line described below — makes it re-read the EEPROM and start running a newly
deployed profile.

So the sequence after deploying a profile is:

1. write the profile (EEPROM is updated, `/var/lib/hifiberry/dspprogram.xml`
   is written)
2. **reset the DSP** — either a power cycle, or by toggling the DSP's reset
   line, which is wired to **GPIO 17** (see `doc/dspreset.md`). The reset is
   the cheap option; no power cycle needed.
3. only now is the DSP actually running the new program

Anything you measure between steps 1 and 2 describes the *old* program.

Note for Pi 5: `doc/dspreset.md` uses the legacy `/sys/class/gpio` sysfs
interface. On the Pi 5 test unit both that and libgpiod (`gpioset`,
`gpiodetect`) were present, but the 40-pin header does not live on
`gpiochip0` there — identify the right chip with `gpiodetect` before driving
the line, rather than assuming chip 0.

## What that looks like from the API (and why it's confusing)

Observed on a Beocreate 4-Channel Amplifier, hifiberry-dsp 1.3.13, after a
successful `POST /dspprofile` but before the DSP was reset:

- The write itself reports success:
  `{"status":"success","message":"Profile from file successfully written to EEPROM"}`
  — but with `"match": false`, because it compares the freshly written XML
  against program memory that is still running the old program.

- `GET /metadata` and `GET /dspprofile` return
  **`404 {"error": "DSP profile file not found or invalid"}`** even though
  `/var/lib/hifiberry/dspprogram.xml` exists and parses fine.

  The wording is misleading. The path that produces it is
  `get_xml_profile()` in `hifiberrydsp/api/restapi.py`: it reads the XML,
  compares memory checksums against the XML's checksums, and on mismatch sets
  `profile_valid = False`, caches that verdict, and returns `None`. The caller
  turns `None` into "file not found or invalid". The file is neither missing
  nor invalid — only the checksum comparison failed.

  Because the verdict is cached, it sticks until the cache is refreshed.

- Log lines that accompany this state:

  ```
  ERROR:root:couldn't find program end signature, using full program memory
  WARNING:root:SHA-1 checksum mismatch - Memory: DA39A3EE..., XML: E9C0BF06...
  ERROR:root:ALSA mixer not available, volume register unknown in profile
  ```

## Don't trust memory checksums as a liveness signal here

In the same state, the memory-side checksums were the hashes of **zero bytes**:

| value | meaning |
|---|---|
| `D41D8CD98F00B204E9800998ECF8427E` | MD5 of an empty input |
| `DA39A3EE5E6B4B0D3255BFEF95601890AFD80709` | SHA-1 of an empty input |

`GET /program-info` reported `program_length: 0` while
`GET /program-memory` simultaneously returned 32764 bytes — the length-based
and signature-based paths disagree. Across service restarts the reported
checksum also moved (`3C1EF88D...`, then `B9AC22DF...`) and `program_length`
flipped between `66733` and `0`.

Practical consequence: a checksum mismatch or a `program_length` of 0 is
**not** proof that a deploy failed. Reset the DSP first, then re-check.

## Open questions

- Post-reset behaviour was not confirmed in the session these notes come from;
  the verification was interrupted before the DSP was reset. Deploy a profile,
  reset via GPIO 17, and confirm that `/metadata` starts answering and the
  memory checksum matches the XML — then update this section.
- Since the reset line is available on GPIO 17, `POST /dspprofile` could
  arguably pulse it after a successful EEPROM write, so a deploy takes effect
  without the caller needing to know any of this.
- The `404 "DSP profile file not found or invalid"` message should probably
  distinguish "no file" / "unparseable file" / "checksum does not match running
  program", since only the third is what usually happens.
- Worth deciding whether a checksum mismatch should really invalidate the
  profile for `/metadata`, given the mismatch is expected between deploy and
  DSP reset.
