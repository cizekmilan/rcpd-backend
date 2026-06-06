#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# rel. 2024-10-23 <milan.cizek@starnet.cz>

import json
import os
import sys
import unittest


EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples")
sys.path.insert(0, EXAMPLES_DIR)

import websocket_manual_toggle_demo as demo


class TestWebsocketManualToggleDemo(unittest.TestCase):

    def test_make_command_serializes_websocket_command(self):
        """Ověří sestavení JSON příkazu pro WebSocket API."""
        data = demo.make_command("CMD_TOGGLE", {"1": {"relays": [3]}})

        self.assertEqual(
            json.loads(data),
            {"CMD_TOGGLE": {"1": {"relays": [3]}}},
        )

    def test_normalize_config_indexes_boards_and_relays_by_int(self):
        """Ověří normalizaci konfigurace vrácené démonem."""
        config = demo.normalize_config({
            "1": {
                "id": 10,
                "board_type": "R421B16",
                "enabled": "Y",
                "total_relays": 16,
                "relays": [
                    {"id": 101, "description": "server XY", "relay_num": 3},
                    {"id": 102, "description": None, "relay_num": 4},
                ],
            }
        })

        self.assertEqual(config[1]["board_type"], "R421B16")
        self.assertEqual(config[1]["total_relays"], 16)
        self.assertEqual(config[1]["relays"][3]["description"], "server XY")
        self.assertEqual(config[1]["relays"][4]["description"], "")

    def test_validate_board_relay_accepts_known_enabled_relay(self):
        """Ověří validní kombinaci desky a relé."""
        boards = {
            1: {
                "enabled": "Y",
                "relays": {
                    3: {"description": "server XY"},
                },
            }
        }

        self.assertEqual(demo.validate_board_relay(boards, 1, 3), (True, ""))

    def test_validate_board_relay_rejects_unknown_board(self):
        """Ověří odmítnutí neznámé desky."""
        is_valid, error = demo.validate_board_relay({}, 5, 1)

        self.assertFalse(is_valid)
        self.assertIn("Unknown board 5", error)

    def test_validate_board_relay_rejects_unknown_relay(self):
        """Ověří odmítnutí neexistujícího relé."""
        boards = {
            1: {
                "enabled": "Y",
                "relays": {
                    1: {},
                    2: {},
                },
            }
        }

        is_valid, error = demo.validate_board_relay(boards, 1, 3)

        self.assertFalse(is_valid)
        self.assertIn("Unknown relay 3", error)


if __name__ == "__main__":
    unittest.main()
