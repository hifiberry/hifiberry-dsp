#!/usr/bin/env python3
"""
Test that --disable-tcp does not bind the SigmaTCP port.

The server socket used to be created unconditionally in
SigmaTCPServerMain.__init__, while serve_forever() was only called when TCP
was enabled. With --disable-tcp that left port 8086 listening but never
accepted: clients completed the TCP handshake, sat in the accept queue and
hung until they timed out.
"""

import os
import sys
import unittest
from unittest.mock import patch

# Add the src directory to the path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from hifiberrydsp.server import sigmatcp


BASE_ARGV = ["sigmatcpserver", "--localhost", "--enable-rest"]


class TestDisableTcpDoesNotBind(unittest.TestCase):

    def _build(self, extra_args):
        """Construct the server main object with SigmaTCPServer mocked out."""
        argv = BASE_ARGV + extra_args
        with patch.object(sigmatcp, "SigmaTCPServer") as server_cls, \
                patch.object(sys, "argv", argv):
            main = sigmatcp.SigmaTCPServerMain()
        return main, server_cls

    def test_disable_tcp_does_not_create_the_tcp_server(self):
        main, server_cls = self._build(["--disable-tcp"])
        server_cls.assert_not_called()
        self.assertIsNone(main.server)

    def test_tcp_server_is_created_when_not_disabled(self):
        main, server_cls = self._build([])
        server_cls.assert_called_once()
        self.assertIsNotNone(main.server)


if __name__ == '__main__':
    unittest.main()
