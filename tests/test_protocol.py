#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# rel. 2024-10-23 <milan.cizek@starnet.cz>

import unittest
import protocol


class TestRCPD(unittest.TestCase):

    def setUp(self):
        """Ztiší logger protokolu během validačních testů."""
        protocol.LOGGER.disabled = True

    def test_is_command_valid_accepts_valid_commands(self):
        """Ověří, že validátor přijímá podporované a správně sestavené příkazy."""
        valid_cases = [
            ('{ "CMD_OFF_ALL": { "0x1": null } }', "CMD_OFF_ALL"),
            ('{ "CMD_ON_ALL": { "0x1": null } }', "CMD_ON_ALL"),
            ('{ "CMD_OFF": { "0x1": { "relays": [1, 2, 3] } } }', "CMD_OFF"),
            ('{ "CMD_ON": { "0x1": { "relays": [1, 2, 3] } } }', "CMD_ON"),
            ('{ "CMD_TOGGLE": { "0x1": { "relays": [1, 2, 3] } } }', "CMD_TOGGLE"),
            ('{ "CMD_LATCH": { "0x1": { "relays": [1, 2, 3] } } }', "CMD_LATCH"),
            ('{ "CMD_MOMENTARY": { "0x1": { "relays": [1, 2, 3] } } }', "CMD_MOMENTARY"),
            ('{ "CMD_DELAY": { "0x1": { "relays": [1, 2, 3], "delay": 5 } } }', "CMD_DELAY"),
            ('{ "CMD_DELAY": { "0x1": { "relays": [1, 16], "delay": 0 } } }', "CMD_DELAY"),
            ('{ "CMD_DELAY": { "0x1": { "relays": [1, 16], "delay": 255 } } }', "CMD_DELAY"),
            ('{ "CMD_ON": { "0": { "relays": [1] } } }', "CMD_ON"),
            ('{ "CMD_ON": { "63": { "relays": [16] } } }', "CMD_ON"),
            ('{ "CMD_ON": { "0x0": { "relays": [1] } } }', "CMD_ON"),
            ('{ "CMD_ON": { "0x3F": { "relays": [16] } } }', "CMD_ON"),
            ('{ "CMD_OFF_ALL": { "24": null } }', "CMD_OFF_ALL"),
            ('{ "CMD_ON_ALL": { "24": null } }', "CMD_ON_ALL"),
            ('{ "CMD_OFF": { "0x1": { "relays": [1, 2, 3] }, "0x2": { "relays": [1, 2, 3] } } }', "CMD_OFF"),
            ('{ "CMD_TOGGLE": { "0x1": { "relays": [1, 2, 3] }, "0x2": { "relays": [1, 2, 3] } } }', "CMD_TOGGLE"),
            ('{ "CMD_DELAY": { "0x1": { "relays": [1, 2, 3], "delay": 5 }, "0x2": { "relays": [1, 2, 3], "delay": 5 } } }', "CMD_DELAY"),
            ('{ "CMD_HELLO": null }', "CMD_HELLO"),
            ('{ "CMD_GETCONFIG": null }', "CMD_GETCONFIG"),
            ('{ "CMD_GETSTATES": null }', "CMD_GETSTATES"),
            ('{ "CFG_CHANGED": null }', "CFG_CHANGED"),
            ('{ "CMD_RSTQUEUE": null }', "CMD_RSTQUEUE"),
            ('{ "CMD_OFF_ALL": { "0x1": null, "0x2": null, "0x3": null } }', "CMD_OFF_ALL"),
        ]

        for data, command in valid_cases:
            with self.subTest(data=data):
                self.assertEqual(protocol.is_command_valid(data), (True, command))

    def test_is_command_valid_rejects_invalid_commands(self):
        """Ověří, že validátor odmítá neznámé nebo špatně sestavené příkazy."""
        invalid_cases = [
            ('{ "CMD_UNKNOWN": { } }', "CMD_UNKNOWN"),
            ('{ "CMD_UNKNOWN": null }', "CMD_UNKNOWN"),
            ('{ }', None),
            ('{ 1, 2, 3 }', None),
            ('{ [0, 1, 2] }', None),
            ('null', None),
            ('true', None),
            ('123', None),
            ('"CMD_HELLO"', None),
            ('{ "CMD_ON": { "0x1": { } } }', "CMD_ON"),
            ('{ "CMD_ON": { "0x1": null } }', "CMD_ON"),
            ('{ "CMD_ON": null }', "CMD_ON"),
            ('{ "CMD_ON": { } }', "CMD_ON"),
            ('{ "CMD_DELAY": { "0x1": { "relays": [1, 2, 3] }, "0x2": { "relays": [1, 2, 3] } } }', "CMD_DELAY"),
            ('{ "CMD_ON": { "": { "relays": [1] } } }', "CMD_ON"),
            ('{ "CMD_ON": { "-1": { "relays": [1] } } }', "CMD_ON"),
            ('{ "CMD_ON": { "64": { "relays": [1] } } }', "CMD_ON"),
            ('{ "CMD_ON": { "0xZZ": { "relays": [1, 2, 3] } } }', "CMD_ON"),
            ('{ "CMD_ON": { "0xFF": { "relays": [1, 2, 3] } } }', "CMD_ON"),
            ('{ "CMD_HELLO_EXTRA": null }', "CMD_HELLO_EXTRA"),
            ('{ "CMD_GETCONFIG_EXTRA": null }', "CMD_GETCONFIG_EXTRA"),
            ('{ "CMD_HELLO": { "unexpected": true } }', "CMD_HELLO"),
            ('{ "CMD_GETCONFIG": { "unexpected": true } }', "CMD_GETCONFIG"),
            ('{ "CMD_ON": { "0x1": { "relays": [0, 1, 2] } } }', "CMD_ON"),
            ('{ "CMD_ON": { "0x1": { "relays": [1, 17] } } }', "CMD_ON"),
            ('{ "CMD_ON": { "0x1": { "relays": [false] } } }', "CMD_ON"),
            ('{ "CMD_ON": { "0x1": { "relays": [null] } } }', "CMD_ON"),
            ('{ "CMD_ON": { "0x1": { "relays": [1.0] } } }', "CMD_ON"),
            ('{ "CMD_ON": { "0x1": { "relays": [] } } }', "CMD_ON"),
            ('{ "CMD_ON": { "0x1": { "relays": "1" } } }', "CMD_ON"),
            ('{ "CMD_ON": { "0x1": { "relays": [true] } } }', "CMD_ON"),
            ('[1]', None),
            ('{ "CMD_ON": [] }', "CMD_ON"),
            ('{ "CMD_ON": { "0x1": [] } }', "CMD_ON"),
            ('{ "CMD_DELAY": { "0x1": { "relays": [1], "delay": -1 } } }', "CMD_DELAY"),
            ('{ "CMD_DELAY": { "0x1": { "relays": [1], "delay": 256 } } }', "CMD_DELAY"),
            ('{ "CMD_DELAY": { "0x1": { "relays": [1], "delay": "5" } } }', "CMD_DELAY"),
            ('{ "CMD_DELAY": { "0x1": { "relays": [1], "delay": true } } }', "CMD_DELAY"),
            ('{ "CMD_DELAY": { "0x1": { "relays": [1], "delay": null } } }', "CMD_DELAY"),
            ('{ "CMD_DELAY": { "0x1": { "relays": [1], "delay": 5.5 } } }', "CMD_DELAY"),
            ('{ "CMD_OFF_ALL": { "0x1": { "relays": [1] } } }', "CMD_OFF_ALL"),
            ('{ "CMD_RSTQUEUE": false }', "CMD_RSTQUEUE"),
            ('{ "CFG_CHANGED": { } }', "CFG_CHANGED"),
            ('{ "CMD_HELLO": null, "CMD_GETSTATES": null }', None),
        ]

        for data, command in invalid_cases:
            with self.subTest(data=data):
                self.assertEqual(protocol.is_command_valid(data), (False, command))

    def test_parse_modbus_address_accepts_decimal_and_hex(self):
        """Ověří převod Modbus adres z dekadického i hexadecimálního zápisu."""
        self.assertEqual(protocol.parse_modbus_address("24"), 24)
        self.assertEqual(protocol.parse_modbus_address("0x18"), 24)

    def test_parse_modbus_address_rejects_invalid_values(self):
        """Ověří, že nečíselné Modbus adresy vyvolají chybu převodu."""
        invalid_addresses = ["", "x", "0xZZ", "1.5"]

        for address in invalid_addresses:
            with self.subTest(address=address):
                with self.assertRaises(ValueError):
                    protocol.parse_modbus_address(address)

    def test_is_int_in_range_accepts_only_real_integers(self):
        """Ověří, že rozsahová kontrola nepřijímá bool, string ani float hodnoty."""
        self.assertTrue(protocol.is_int_in_range(1, 1, 16))
        self.assertTrue(protocol.is_int_in_range(16, 1, 16))

        invalid_values = [0, 17, True, False, "1", 1.0, None]
        for value in invalid_values:
            with self.subTest(value=value):
                self.assertFalse(protocol.is_int_in_range(value, 1, 16))

    def test_are_relays_valid_accepts_only_non_empty_relay_lists(self):
        """Ověří validaci seznamu relé v rozsahu 1..16."""
        valid_relay_lists = [[1], [16], [1, 2, 16]]
        invalid_relay_lists = [[], [0], [17], [1, "2"], [True], None, "1"]

        for relays in valid_relay_lists:
            with self.subTest(relays=relays):
                self.assertTrue(protocol.are_relays_valid(relays))

        for relays in invalid_relay_lists:
            with self.subTest(relays=relays):
                self.assertFalse(protocol.are_relays_valid(relays))
