#!/usr/bin/env python3
"""
Tests for metadata attribute exposure.

XmlProfile.get_meta() returns the element text only, so every attribute
except @storable was invisible to the REST API -- including the two a speaker
preset needs: the role ordering on channelSelect*Register and the delay clamp
on delay*Register.

Requires the test venv:
    .venv-test/bin/python -m unittest test_metadata_attributes -v
"""

import os
import sys
import unittest
from collections import OrderedDict

import xmltodict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

import hifiberrydsp  # noqa: E402
hifiberrydsp._called_from_test = True

from hifiberrydsp.parser.xmlprofile import XmlProfile  # noqa: E402

PROFILE_XML = """<?xml version="1.0" standalone="no"?>
<ROM IC="ADAU1451" IC_Address="1" Address_byte_length="2">
  <beometa>
    <metadata type="profileName">Test Profile</metadata>
    <metadata type="IIR_A" storable="yes">691/80</metadata>
    <metadata type="channelSelectARegister" channels="left,right,mono,side"
              multiplier="1" storable="yes">4861</metadata>
    <metadata type="delayARegister" maxDelay="2000" storable="yes">786</metadata>
  </beometa>
</ROM>
"""


class TestGetMetaAttributes(unittest.TestCase):

    def setUp(self):
        # Set doc directly: update() expects program data this fixture omits.
        self.profile = XmlProfile()
        self.profile.doc = xmltodict.parse(PROFILE_XML,
                                           dict_constructor=OrderedDict)

    def test_returns_attributes_without_the_xmltodict_prefix(self):
        self.assertEqual(
            self.profile.get_meta_attributes("channelSelectARegister"),
            {"channels": "left,right,mono,side", "multiplier": "1",
             "storable": "yes"})

    def test_max_delay_is_reachable(self):
        self.assertEqual(
            self.profile.get_meta_attributes("delayARegister")["maxDelay"],
            "2000")

    def test_type_is_the_key_not_an_attribute(self):
        self.assertNotIn("type",
                         self.profile.get_meta_attributes("IIR_A"))

    def test_element_without_attributes_returns_empty(self):
        self.assertEqual(self.profile.get_meta_attributes("profileName"), {})

    def test_unknown_key_returns_empty(self):
        self.assertEqual(self.profile.get_meta_attributes("nosuchkey"), {})

    def test_text_is_still_reachable_unchanged(self):
        self.assertEqual(self.profile.get_meta("delayARegister"), "786")


if __name__ == "__main__":
    unittest.main()
