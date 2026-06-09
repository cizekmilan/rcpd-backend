#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# rel. 2024-10-23 <milan.cizek@starnet.cz>

import os
import sys
import types
import unittest


EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples")
sys.path.insert(0, EXAMPLES_DIR)

try:
    import curses  # noqa: F401
except ModuleNotFoundError:
    sys.modules["curses"] = types.ModuleType("curses")

import rcpd_tui


class TestRcpdTui(unittest.TestCase):

    def test_build_relays_keeps_disabled_board_relays(self):
        """Overi, ze TUI data obsahuji i rele z disabled desek."""
        relays = rcpd_tui.build_relays_from_config({
            "1": {
                "enabled": "Y",
                "relays": [
                    {"relay_num": 1, "description": "enabled"},
                ],
            },
            "3": {
                "enabled": "N",
                "relays": [
                    {"relay_num": 1, "description": "disabled"},
                    {"relay_num": 2, "description": "disabled"},
                ],
            },
        })

        self.assertEqual(len(relays), 3)
        self.assertEqual(relays[0].board_addr, 1)
        self.assertEqual(relays[1].board_addr, 3)
        self.assertEqual(relays[1].state, rcpd_tui.STATE_DISABLED)
        self.assertFalse(relays[1].board_enabled)
        self.assertEqual(rcpd_tui.first_selectable_index(relays), 0)
        self.assertEqual(rcpd_tui.next_selectable_index(relays, 0), 0)

    def test_build_relays_creates_header_row_for_board_without_relays(self):
        """Overi, ze deska bez rele zaznamu zustane viditelna jako hlavicka."""
        relays = rcpd_tui.build_relays_from_config({
            "4": {
                "enabled": "N",
                "relays": [],
            },
        })

        self.assertEqual(len(relays), 1)
        self.assertEqual(relays[0].board_addr, 4)
        self.assertEqual(relays[0].relay_num, 0)
        self.assertEqual(relays[0].state, rcpd_tui.STATE_DISABLED)
        self.assertEqual(rcpd_tui.first_selectable_index(relays), -1)


if __name__ == "__main__":
    unittest.main()
