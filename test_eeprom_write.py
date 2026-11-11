#!/usr/bin/env python3
"""
Tests for writing a DSP profile to the self-boot EEPROM.

The write replays the profile's action list over SPI for about a minute:
the self-boot programmer erases the EEPROM, copies page after page into it,
and the tail loads the program into RAM and starts the core. Anything else
that talks to the DSP in between (the ALSA volume sync, a /checksum request,
which stops and restarts the core itself) lands in the middle of that and can
leave a half-written EEPROM that only shows up at the next power-on
(hifiberry-dsp#87).

Run with:
    python3 -m unittest test_eeprom_write -v
"""

import os
import shutil
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

import hifiberrydsp  # noqa: E402
hifiberrydsp._called_from_test = True

from hifiberrydsp.hardware import adau145x as adau145x_module  # noqa: E402
from hifiberrydsp.hardware.adau145x import Adau145x  # noqa: E402
from hifiberrydsp.hardware.spi import SpiHandler  # noqa: E402
from hifiberrydsp.api import restapi  # noqa: E402

ERASE_ADDR = 0x6000
PAGE_ADDR = 0x6100
PROGRAM_ADDR = 0xC000
DM0_ADDR = 0x0000
PROBE_ADDR = 0xF890


def write_action(name, addr, data):
    payload = " ".join("0x%02X" % b for b in data)
    return ('<action instr="writeXbytes" addr="%d" len="%d" ParamName="%s">%s</action>'
            % (addr, len(data), name, payload))


def profile_xml():
    actions = [
        write_action("IC 1.KILL_CORE", 0xF403, [0x00, 0x01]),
        write_action("g_Erase", ERASE_ADDR, [0, 0, 0, 1]),
        write_action("Page_A0_S256_N3_idx0", PAGE_ADDR, [0, 0, 0, 2]),
        write_action("Page_A256_S256_N3_idx1", PAGE_ADDR, [0, 0, 0, 3]),
        write_action("Page_A512_S256_N3_idx2", PAGE_ADDR, [0, 0, 0, 4]),
        '<action instr="delay" />',
        write_action("Sigma300.SelfbootProgrammer.PLL Lock Delay", 0x6200, [0, 0, 0, 5]),
        write_action("Program Data", PROGRAM_ADDR, [0, 0, 0, 6, 0, 0, 0, 7]),
        write_action("DM0 Data", DM0_ADDR, [0, 0, 0, 8]),
        write_action("IC 1.START_CORE", 0xF402, [0x00, 0x01]),
    ]
    return '<ROM><page modetype="Mode 0">%s</page></ROM>' % "".join(actions)


class FakeSpi:
    """Records every SPI write as (address, first payload byte)."""

    def __init__(self, events):
        self.events = events

    def xfer(self, request):
        address = (request[1] << 8) | request[2]
        if request[0] == 0:
            self.events.append(("write", address))
            return [0] * len(request)
        return [0] * len(request)

    xfer2 = xfer


class EepromWriteTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.events = []
        self._real_spi = SpiHandler.spi
        SpiHandler.spi = FakeSpi(self.events)
        self._patches = [
            mock.patch("hifiberrydsp.parser.xmlprofile.get_default_dspprofile_path",
                       return_value=os.path.join(self.temp_dir, "dspprogram.xml")),
            mock.patch.object(Adau145x, "clear_checksum_cache", lambda *a, **k: None),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        SpiHandler.spi = self._real_spi
        shutil.rmtree(self.temp_dir)

    def recording_sleep(self):
        def fake_sleep(seconds):
            if seconds >= 0.01:            # ignore the 100 us register settles
                self.events.append(("sleep", seconds))
        return fake_sleep

    def waits_after(self, address, occurrence=-1):
        """Total sleep between the given write and the next SPI write."""
        writes = [i for i, e in enumerate(self.events) if e == ("write", address)]
        index = writes[occurrence]
        total = 0
        for event in self.events[index + 1:]:
            if event[0] == "write":
                break
            total += event[1]
        return total

    def test_other_spi_users_wait_until_the_write_is_done(self):
        result = {}

        def other_user():
            SpiHandler.read(PROBE_ADDR, 2)
            result["done"] = True

        intruder = threading.Thread(target=other_user)
        state = {"started": False, "blocked": None}

        def fake_sleep(seconds):
            if seconds >= 1 and not state["started"]:
                state["started"] = True
                intruder.start()
                intruder.join(0.3)
                state["blocked"] = intruder.is_alive()

        with mock.patch("time.sleep", fake_sleep):
            self.assertTrue(Adau145x.write_eeprom_content(profile_xml()))

        intruder.join(2)
        self.assertTrue(state["started"])
        self.assertTrue(state["blocked"],
                        "another SPI user got the bus in the middle of the EEPROM write")
        self.assertTrue(result.get("done"))

    def test_program_data_write_is_followed_by_a_wait(self):
        with mock.patch("time.sleep", self.recording_sleep()):
            self.assertTrue(Adau145x.write_eeprom_content(profile_xml()))
        self.assertGreaterEqual(self.waits_after(PROGRAM_ADDR), 1)

    def test_last_page_gets_extra_time_before_the_ram_load(self):
        with mock.patch("time.sleep", self.recording_sleep()):
            self.assertTrue(Adau145x.write_eeprom_content(profile_xml()))
        self.assertEqual(self.waits_after(PAGE_ADDR, 0), 1)
        # the last page is followed by a delay action (1 s) in this profile;
        # the extra settle time comes on top of the page's own wait
        self.assertGreaterEqual(self.waits_after(PAGE_ADDR, -1),
                                1 + Adau145x.EEPROM_LAST_PAGE_WAIT)

    def test_erase_wait_is_kept(self):
        with mock.patch("time.sleep", self.recording_sleep()):
            self.assertTrue(Adau145x.write_eeprom_content(profile_xml()))
        self.assertEqual(self.waits_after(ERASE_ADDR), 10)

    def test_selfboot_programmer_parameters_get_no_program_wait(self):
        with mock.patch("time.sleep", self.recording_sleep()):
            self.assertTrue(Adau145x.write_eeprom_content(profile_xml()))
        self.assertEqual(self.waits_after(0x6200), 0)


class DspProfileEndpointTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.profile = os.path.join(self.temp_dir, "profile.xml")
        with open(self.profile, "w") as f:
            f.write('<ROM><beometa>'
                    '<metadata type="checksum">AAAA</metadata>'
                    '<metadata type="checksum_sha1">BBBB</metadata>'
                    '</beometa><page modetype="Mode 0">%s%s</page></ROM>'
                    % (write_action("Program Data", PROGRAM_ADDR, [0, 0, 0, 6]),
                       write_action("DM0 Data", DM0_ADDR, [0, 0, 0, 8])))
        self._patches = [
            mock.patch.object(Adau145x, "write_eeprom_content", return_value=True),
            mock.patch.object(restapi, "get_default_dspprofile_path", return_value=self.profile),
            mock.patch("time.sleep", lambda s: None),
        ]
        for p in self._patches:
            p.start()
        restapi.app.config['TESTING'] = True
        self.client = restapi.app.test_client()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        shutil.rmtree(self.temp_dir)

    def post(self, memory_checksums):
        with mock.patch.object(Adau145x, "calculate_program_checksums",
                               return_value=memory_checksums):
            return self.client.post('/dspprofile', json={"file": self.profile})

    def test_mismatch_is_reported_as_an_error(self):
        response = self.post({"sha1": "CCCC", "md5": "DDDD"})
        body = response.get_json()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(body["status"], "error")
        self.assertFalse(body["match"])
        self.assertIn("checksums", body)

    def test_match_is_success(self):
        response = self.post({"sha1": "bbbb", "md5": "aaaa"})
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["status"], "success")
        self.assertTrue(body["match"])


if __name__ == "__main__":
    unittest.main()
