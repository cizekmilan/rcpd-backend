#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# rel. 2024-10-23 <milan.cizek@starnet.cz>

"""
Hardware smoke test for a running rcpd daemon.

This script connects to the WebSocket API and sends a fixed command sequence
that switches real relay outputs. Run it only when the connected hardware and
powered devices can safely tolerate the relay operations below.
"""

import asyncio
import json
import sys

import websockets

VERSION = "0.02"

WS_SERVER_ADDR = "127.0.0.1"
WS_SERVER_PORT = 8001

# Relay boards used by this smoke test. Keep one address if only one board is connected.
BOARD_ADDRESSES = ["0x1", "0x2"]

# Delay between repeated state polling requests at the end of the smoke test.
STATE_POLL_INTERVAL = 5


def websocket_uri():
    """Sestaví WebSocket URL pro smoke test klienta."""
    return f"ws://{WS_SERVER_ADDR}:{WS_SERVER_PORT}"


def print_connection_error(err):
    """Vypíše srozumitelnou chybu při nedostupném rcpd démonu."""
    print(f"Unable to connect to rcpd daemon at {websocket_uri()}: {err}", file=sys.stderr)
    print("Is rcpd.py running and listening on the selected address/port?", file=sys.stderr)


async def send_and_print(websocket, command):
    """Pošle příkaz démonu a vypíše odpověď."""
    data = json.dumps(command)
    print(data)
    await websocket.send(data)
    response = await websocket.recv()
    print(f"< {response}\n")


async def hardware_smoke_test():
    """Provede pevnou testovací sekvenci WebSocket příkazů proti rcpd démonu."""
    if not BOARD_ADDRESSES:
        print("BOARD_ADDRESSES must contain at least one relay board address.", file=sys.stderr)
        sys.exit(1)

    uri = websocket_uri()
    async with websockets.connect(uri) as websocket:

        await asyncio.sleep(2)

        await send_and_print(websocket, {"CFG_CHANGED": None})

        await send_and_print(websocket, {"CMD_GETCONFIG": None})

        await send_and_print(websocket, {"CMD_RSTQUEUE": None})

        for board_address in BOARD_ADDRESSES:
            print(f"Testing board address: {board_address}\n")

            await send_and_print(websocket, {"CMD_ON_ALL": {board_address: None}})
            await asyncio.sleep(5)

            await send_and_print(websocket, {"CMD_OFF": {board_address: {"relays": [1, 2, 3]}}})
            await asyncio.sleep(5)

            await send_and_print(websocket, {"CMD_ON": {board_address: {"relays": [1, 2, 3]}}})
            await asyncio.sleep(5)

            await send_and_print(websocket, {"CMD_TOGGLE": {board_address: {"relays": [1, 2, 3, 4, 5, 6, 7]}}})
            await asyncio.sleep(5)

            await send_and_print(websocket, {"CMD_TOGGLE": {board_address: {"relays": [1, 2, 3, 4, 5, 6, 7]}}})
            await asyncio.sleep(5)

            await send_and_print(websocket, {"CMD_LATCH": {board_address: {"relays": [1, 2, 3]}}})
            await asyncio.sleep(5)

            await send_and_print(websocket, {"CMD_MOMENTARY": {board_address: {"relays": [14, 15, 16]}}})
            await asyncio.sleep(5)

            await send_and_print(websocket, {"CMD_DELAY": {board_address: {"relays": [8, 9, 10], "delay": 5}}})
            await asyncio.sleep(5)

            await send_and_print(websocket, {"CMD_OFF_ALL": {board_address: None}})
            await asyncio.sleep(5)

        while True:
            await send_and_print(websocket, {"CMD_GETSTATES": None})
            await asyncio.sleep(STATE_POLL_INTERVAL)


def main():
    """Spustí smoke test a ošetří běžné chyby připojení k démonu."""
    try:
        asyncio.get_event_loop().run_until_complete(hardware_smoke_test())
    except (OSError, websockets.exceptions.WebSocketException) as err:
        print_connection_error(err)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
