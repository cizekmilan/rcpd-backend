#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# rel. 2024-10-23 <milan.cizek@starnet.cz>

import unittest
import sys
import types


try:
    import serial  # noqa: F401
except ImportError:
    class FakeSerial:
        """Minimální náhrada pySerial třídy pro vytvoření Modbus instance v testu."""

        def __init__(self):
            self.is_open = True

        def close(self):
            """Simuluje zavření sériového portu."""
            self.is_open = False

    serial_stub = types.ModuleType("serial")
    serial_stub.PARITY_NONE = "N"
    serial_stub.SerialException = Exception
    serial_stub.SerialTimeoutException = Exception
    serial_stub.Serial = FakeSerial
    sys.modules["serial"] = serial_stub

from relay_drivers.R421B16 import ModbusException, R421B16
from relay_drivers.modbus import Modbus


def noop_modbus_destructor(self):
    """V testech nevynucuje zavírání testovacího sériového portu."""
    pass


Modbus.__del__ = noop_modbus_destructor


def create_fake_modbus(response):
    """Vytvoří Modbus instanci s nahrazeným odesláním a příjmem rámců."""
    modbus = Modbus()
    modbus.response = response
    modbus.sent_data = None
    modbus.receive_length = None

    def is_open():
        """Simuluje otevřený sériový port."""
        return True

    def send(tx_data):
        """Uloží odeslaný Modbus rámec pro kontrolu v testu."""
        modbus.sent_data = list(tx_data)

    def receive(rx_length):
        """Vrátí připravenou odpověď a uloží očekávanou délku."""
        modbus.receive_length = rx_length
        return modbus.response

    modbus.is_open = is_open
    modbus.send = send
    modbus.receive = receive

    return modbus


def build_read_status_all_response(address, states):
    """Sestaví Modbus odpověď pro hromadné čtení stavů relé."""
    data = [address, 0x03, len(states) * 2]

    for state in states:
        data.extend([0x00, state])

    return data + Modbus.crc(data)


class TestR421B16(unittest.TestCase):

    def test_get_status_all_reads_all_relays_in_one_modbus_request(self):
        """Ověří rychlé čtení všech 16 relé jedním FC3 dotazem."""
        states = [0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]
        modbus = create_fake_modbus(build_read_status_all_response(1, states))
        board = R421B16(modbus, address=1)

        self.assertEqual(
            board.get_status_all(),
            {
                1: 0,
                2: 0,
                3: 0,
                4: 1,
                5: 0,
                6: 0,
                7: 0,
                8: 0,
                9: 0,
                10: 0,
                11: 0,
                12: 0,
                13: 0,
                14: 0,
                15: 0,
                16: 1,
            }
        )
        self.assertEqual(modbus.sent_data, [1, 0x03, 0x00, 0x01, 0x00, 0x10])
        self.assertEqual(modbus.receive_length, 37)

    def test_get_status_all_rejects_invalid_crc(self):
        """Ověří, že hromadné čtení kontroluje CRC odpovědi."""
        response = build_read_status_all_response(1, [0] * 16)
        response[-1] ^= 0xFF
        board = R421B16(create_fake_modbus(response), address=1)

        with self.assertRaises(ModbusException):
            board.get_status_all()


if __name__ == "__main__":
    unittest.main()
