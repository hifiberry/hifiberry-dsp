#!/usr/bin/env python3
"""
sigmatcpserver.service must not wait for the network.

The server binds to localhost only (--localhost), and loopback is up before
any service starts. Ordering it after network.target made everything that
waits for it (config-detect, and through it the audio server's
configuration) wait for NetworkManager at boot, about 20 s on a Pi 4.
"""

import configparser
import os
import unittest

UNIT = os.path.join(os.path.dirname(__file__), "systemd", "sigmatcpserver.service")


def _unit_list(section, key):
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.optionxform = str
    parser.read(UNIT)
    return parser.get(section, key, fallback="").split()


class TestUnitOrdering(unittest.TestCase):

    def test_not_ordered_after_the_network(self):
        after = _unit_list("Unit", "After") + _unit_list("Unit", "Wants")
        self.assertNotIn("network.target", after)
        self.assertNotIn("network-online.target", after)

    def test_still_ordered_after_the_spi_device(self):
        self.assertIn("dev-spidev0.0.device", _unit_list("Unit", "After"))

    def test_binds_to_localhost(self):
        self.assertIn("--localhost", _unit_list("Service", "ExecStart"))


if __name__ == "__main__":
    unittest.main()
