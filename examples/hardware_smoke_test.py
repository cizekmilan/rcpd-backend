#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# rel. 2024-10-23 <milan.cizek@starnet.cz>

"""
Hardware smoke test for a running rcpd daemon.

This script connects to the WebSocket API and sends a fixed command sequence
that switches real relay outputs. Run it only when the connected hardware and
powered devices can safely tolerate the relay operations below.
"""

import sys
import asyncio
import websockets
import time

VERSION = "0.02"

WS_SERVER_ADDR = "127.0.0.1"
WS_SERVER_PORT = 8001


def websocket_uri():
    """Sestaví WebSocket URL pro smoke test klienta."""
    return f"ws://{WS_SERVER_ADDR}:{WS_SERVER_PORT}"


def print_connection_error(err):
    """Vypíše srozumitelnou chybu při nedostupném rcpd démonu."""
    print(f"Unable to connect to rcpd daemon at {websocket_uri()}: {err}", file=sys.stderr)
    print("Is rcpd.py running and listening on the selected address/port?", file=sys.stderr)


async def hardware_smoke_test():
    """Provede pevnou testovací sekvenci WebSocket příkazů proti rcpd démonu."""
    uri = websocket_uri()
    async with websockets.connect(uri) as websocket:

        time.sleep(2)

        data = '{ "CFG_CHANGED": null }'
        print(data)
        await websocket.send(data)
        data = await websocket.recv()
        print(f"< {data}\n")

        data = '{ "CMD_GETCONFIG": null }'
        print(data)
        await websocket.send(data)
        data = await websocket.recv()
        print(f"< {data}\n")

        data = '{ "CMD_RSTQUEUE": null }'
        print(data)
        await websocket.send(data)
        data = await websocket.recv()
        print(f"< {data}\n")

        data = '{ "CMD_ON_ALL": { "0x1": null, "0x2": null } }'
        print(data)
        await websocket.send(data)
        data = await websocket.recv()
        print(f"< {data}\n")
        time.sleep(5)

        data = '{ "CMD_OFF": { "0x1": { "relays": [1, 2, 3] }, "0x2": { "relays": [1, 2, 3] } } }'
        print(data)
        await websocket.send(data)
        data = await websocket.recv()
        print(f"< {data}\n")
        time.sleep(5)

        data = '{ "CMD_ON": { "0x1": { "relays": [1, 2, 3] }, "0x2": { "relays": [1, 2, 3] } } }'
        print(data)
        await websocket.send(data)
        data = await websocket.recv()
        print(f"< {data}\n")
        time.sleep(5)

        data = '{ "CMD_TOGGLE": { "0x1": { "relays": [1, 2, 3, 4, 5, 6, 7] }, "0x2": { "relays": [1, 2, 3, 4, 5, 6, 7] } } }'
        print(data)
        await websocket.send(data)
        data = await websocket.recv()
        print(f"< {data}\n")
        time.sleep(5)

        data = '{ "CMD_TOGGLE": { "0x1": { "relays": [1, 2, 3, 4, 5, 6, 7] }, "0x2": { "relays": [1, 2, 3, 4, 5, 6, 7] } } }'
        print(data)
        await websocket.send(data)
        data = await websocket.recv()
        print(f"< {data}\n")
        time.sleep(5)

        data = '{ "CMD_LATCH": { "0x1": { "relays": [1, 2, 3] } } }'
        print(data)
        await websocket.send(data)
        data = await websocket.recv()
        print(f"< {data}\n")
        time.sleep(5)

        data = '{ "CMD_MOMENTARY": { "0x1": { "relays": [14, 15, 16] } } }'
        print(data)
        await websocket.send(data)
        data = await websocket.recv()
        print(f"< {data}\n")
        time.sleep(5)

        data = '{ "CMD_DELAY": { "0x1": { "relays": [8, 9, 10], "delay": 5 } } }'
        print(data)
        await websocket.send(data)
        data = await websocket.recv()
        print(f"< {data}\n")
        time.sleep(5)

        data = '{ "CMD_OFF_ALL": { "0x1": null, "0x2": null } }'
        print(data)
        await websocket.send(data)
        data = await websocket.recv()
        print(f"< {data}\n")
        time.sleep(5)

        while True:
            data = '{ "CMD_GETSTATES": null }'
            print(data)
            await websocket.send(data)
            data = await websocket.recv()
            print(f"< {data}\n")

try:
    asyncio.get_event_loop().run_until_complete(hardware_smoke_test())
except (OSError, websockets.exceptions.WebSocketException) as err:
    print_connection_error(err)
    sys.exit(1)
except KeyboardInterrupt:
    sys.exit(0)
