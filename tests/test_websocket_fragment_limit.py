# SPDX-License-Identifier: MIT
"""Bounded offline checks of the sync assembler used by the edge client."""

import unittest

from websockets.exceptions import TooManyFragments
from websockets.frames import Frame, Opcode
from websockets.sync.messages import Assembler


class WebSocketFragmentLimitTests(unittest.TestCase):
    def assembler(self, count, *, complete):
        assembler = Assembler()
        self.addCleanup(assembler.close)
        for index in range(count):
            assembler.put(
                Frame(
                    Opcode.TEXT if index == 0 else Opcode.CONT,
                    b"{}" if index == 0 else b"",
                    fin=complete and index == count - 1,
                )
            )
        return assembler

    def test_normal_message_is_unchanged(self):
        self.assertEqual(self.assembler(1, complete=True).get(timeout=0), "{}")

    def test_complete_message_at_fragment_limit_is_accepted(self):
        self.assertEqual(self.assembler(4096, complete=True).get(timeout=0), "{}")

    def test_unfinished_empty_fragments_stop_before_another_read(self):
        # Only 4,097 small frames, without sockets, threads or a time-based load.
        # 17.2 continued reading here until timeout; 17.4 rejects the count.
        with self.assertRaises(TooManyFragments):
            self.assembler(4097, complete=False).get(timeout=0)

    def test_oversized_fragment_count_cannot_hide_in_a_complete_message(self):
        with self.assertRaises(TooManyFragments):
            self.assembler(4097, complete=True).get(timeout=0)
