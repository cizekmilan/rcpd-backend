#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# rel. 2024-10-23 <milan.cizek@starnet.cz>

"""
Simple manual WebSocket toggle demo for a running rcpd daemon.

This is not the primary CLI/TUI client. It is a small guarded manual tool for
testing daemon connectivity, reading relay configuration, toggling one relay at
a time, and clearing the command queue.
"""

import asyncio
import getopt
import json
import os
import re
import signal
import sys
from termcolor import colored
import websockets

VERSION = "0.08"

WS_SERVER_ADDR = "127.0.0.1"
WS_SERVER_PORT = 8001
POST_TOGGLE_STATE_DELAY = 1


def signal_handler(sig, frame):
    """Ukončí demo klienta po přijetí signálu, typicky Ctrl+C."""
    print("\nExiting program...")
    sys.exit(0)


def websocket_uri():
    """Sestaví WebSocket URL podle aktuální adresy a portu serveru."""
    return f"ws://{WS_SERVER_ADDR}:{WS_SERVER_PORT}"


def print_connection_error(err):
    """Vypíše srozumitelnou chybu při nedostupném rcpd démonu."""
    print(f"Unable to connect to rcpd daemon at {websocket_uri()}: {err}", file=sys.stderr)
    print("Start rcpd.py or check the -s/--server and -p/--port options.", file=sys.stderr)


def print_usage():
    """Vypíše dostupné argumenty demo klienta."""
    print(f"Usage: {os.path.basename(__file__)} [-h] [-s 127.0.0.1] [-p {WS_SERVER_PORT}] [-v]")
    print(f"  -h|--help       display this help and exit")
    print(f"  -s|--server     websocket server host/IP (default: {WS_SERVER_ADDR})")
    print(f"  -p|--port       websocket server port (default: {WS_SERVER_PORT})")
    print(f"  -v|--version    print version of this script")


def parse_arguments():
    """Zpracuje argumenty příkazové řádky pro demo klienta."""
    global WS_SERVER_ADDR, WS_SERVER_PORT

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hs:p:v", ["help", "server=", "port=", "version"])
    except getopt.GetoptError:
        print_usage()
        sys.exit(2)

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print_usage()
            sys.exit(0)
        elif opt in ("-s", "--server"):
            WS_SERVER_ADDR = arg
        elif opt in ("-p", "--port"):
            WS_SERVER_PORT = arg
        elif opt in ("-v", "--version"):
            print(f"RCPD manual toggle demo {VERSION}")
            sys.exit(0)


async def send_to_websocket(data):
    """Pošle jeden JSON příkaz démonu a vrátí dekódovanou JSON odpověď."""
    try:
        async with websockets.connect(websocket_uri(), ping_interval=30, ping_timeout=5) as websocket:
            await websocket.send(data)
            response = await websocket.recv()
    except (OSError, websockets.exceptions.WebSocketException) as err:
        print_connection_error(err)
        return None

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        print(f"Invalid JSON response from daemon: {response}", file=sys.stderr)
        return None


def make_command(command, payload=None):
    """Sestaví JSON příkaz pro WebSocket API."""
    return json.dumps({command: payload})


def is_ok_response(response):
    """Vrátí True, pokud odpověď démona obsahuje result=OK."""
    return bool(response and response.get("result") == "OK")


async def check_daemon_connection():
    """Ověří spojení s démonem pomocí jednoduchého CMD_HELLO příkazu."""
    response = await send_to_websocket(make_command("CMD_HELLO"))
    if not is_ok_response(response):
        print(f"Daemon hello failed: {response}", file=sys.stderr)
        return False

    return True


def normalize_config(raw_config):
    """Převede konfiguraci z JSON odpovědi na slovník indexovaný int adresou desky."""
    boards = {}

    for board_address, board_config in raw_config.items():
        address = int(board_address)
        relays = {}

        for relay in board_config.get("relays", []):
            relay_num = int(relay["relay_num"])
            relays[relay_num] = {
                "id": relay.get("id"),
                "description": relay.get("description") or "",
                "contact_type": relay.get("contact_type") or "NO",
            }

        boards[address] = {
            "id": board_config.get("id"),
            "board_type": board_config.get("board_type") or "unknown",
            "enabled": board_config.get("enabled"),
            "total_relays": int(board_config.get("total_relays") or len(relays)),
            "relays": relays,
        }

    return boards


def format_contact_type(contact_type):
    """Vrátí kontaktní typ relé ve formátu vhodném pro konzolový výpis."""
    if contact_type not in ("NO", "NC"):
        contact_type = "NO"

    return f"[{contact_type}]"


def normalize_relay_states(raw_states):
    """Převede stav relé z JSON odpovědi na slovník indexovaný int adresou desky a relé."""
    relay_states = {}

    for board_address, states in raw_states.items():
        address = int(board_address)
        relay_states[address] = {
            int(relay_num): int(state)
            for relay_num, state in states.items()
        }

    return relay_states


def format_relay_state(state):
    """Vrátí barevný blok pro jeden stav relé."""
    if state == 1:
        return colored("  On  ", "white", "on_green")
    elif state == 0:
        return colored("  Off ", "white", "on_red")

    return colored("  ?   ", "white", "on_yellow")


def print_relay_states(boards, relay_states):
    """Vypíše barevnou vizualizaci stavů relé pro všechny aktivní desky."""
    print("\nRelay states:")
    enabled_boards = 0

    for address in sorted(boards):
        board = boards[address]
        if board["enabled"] != "Y":
            continue

        enabled_boards += 1
        states = relay_states.get(address, {})
        output = f"  board {address} / 0x{address:02X}: "

        for relay_num in sorted(board["relays"]):
            output += format_relay_state(states.get(relay_num))

        print(output)

    if enabled_boards == 0:
        print("  no enabled boards")


async def load_config():
    """Načte konfiguraci desek a relé z démona přes CMD_GETCONFIG."""
    response = await send_to_websocket(make_command("CMD_GETCONFIG"))
    if not is_ok_response(response):
        print(f"Unable to load daemon configuration: {response}", file=sys.stderr)
        return None

    try:
        return normalize_config(response.get("config", {}))
    except (KeyError, TypeError, ValueError) as err:
        print(f"Invalid daemon configuration response: {err}", file=sys.stderr)
        return None


async def load_relay_states():
    """Načte poslední známé stavy relé z démona přes CMD_GETSTATES."""
    response = await send_to_websocket(make_command("CMD_GETSTATES"))
    if not is_ok_response(response):
        print(f"Unable to load relay states: {response}", file=sys.stderr)
        return None

    try:
        return normalize_relay_states(response.get("relay_states", {}))
    except (TypeError, ValueError) as err:
        print(f"Invalid relay states response: {err}", file=sys.stderr)
        return None


def print_config(boards):
    """Vypíše jednoduchý přehled dostupných relay boardů a relé."""
    if not boards:
        print("No relay boards received from daemon configuration.")
        return

    print("\nLoaded relay configuration:")
    for address in sorted(boards):
        board = boards[address]
        enabled = "enabled" if board["enabled"] == "Y" else "disabled"
        print(f"  board {address} / 0x{address:02X}: {board['board_type']}, {board['total_relays']} relays, {enabled}")

        if board["enabled"] == "Y":
            for relay_num in sorted(board["relays"]):
                description = board["relays"][relay_num]["description"] or "-"
                contact_type = board["relays"][relay_num]["contact_type"]
                print(f"    {address}/{relay_num:02d}  {format_contact_type(contact_type)}  {description}")


def print_prompt_help():
    """Vypíše stručnou nápovědu pro interaktivní příkazovou smyčku."""
    print("\nCommands:")
    print("  board/relay   toggle relay, for example 1/3")
    print("  conf          reload and print daemon configuration")
    print("  rq            reset daemon command queue")
    print("  quit          exit")


def parse_board_relay(user_input):
    """Převede vstup board/relay na dvojici int hodnot, nebo vrátí None."""
    match = re.match(r"^(\d+)/(\d+)$", user_input)
    if not match:
        return None

    return int(match.group(1)), int(match.group(2))


def validate_board_relay(boards, board_address, relay_num):
    """Ověří, zda zadaná deska a relé existují v načtené konfiguraci."""
    if board_address not in boards:
        known_boards = ", ".join(str(address) for address in sorted(boards)) or "none"
        return False, f"Unknown board {board_address}. Known boards: {known_boards}."

    board = boards[board_address]
    if board["enabled"] != "Y":
        return False, f"Board {board_address} exists but is disabled."

    if relay_num not in board["relays"]:
        relays = sorted(board["relays"])
        if relays:
            return False, f"Unknown relay {relay_num} on board {board_address}. Valid relays: {relays[0]}..{relays[-1]}."

        return False, f"Board {board_address} has no relays in daemon configuration."

    return True, ""


async def reset_queue():
    """Pošle CMD_RSTQUEUE a vypíše výsledek."""
    response = await send_to_websocket(make_command("CMD_RSTQUEUE"))
    if is_ok_response(response):
        print("Command queue was reset.")
    else:
        print(f"Queue reset failed: {response}")


async def toggle_relay(board_address, relay_num):
    """Pošle CMD_TOGGLE pro jedno relé."""
    data = make_command("CMD_TOGGLE", {str(board_address): {"relays": [relay_num]}})
    response = await send_to_websocket(data)

    if is_ok_response(response):
        print(f"Toggle command accepted for {board_address}/{relay_num}. Queue: {response.get('in_queue')}")
        return True
    else:
        print(f"Toggle command failed for {board_address}/{relay_num}: {response}")
        return False


async def interactive_loop(boards):
    """Čte interaktivní vstup uživatele a posílá odpovídající příkazy démonu."""
    print_prompt_help()

    while True:
        user_input = input("\nrcpd-demo> ").strip()
        command = user_input.lower()

        if command in ("q", "quit", "exit"):
            print("Exiting program...")
            break

        if command == "conf":
            refreshed_config = await load_config()
            if refreshed_config is not None:
                boards.clear()
                boards.update(refreshed_config)
                print_config(boards)
            continue

        if command == "rq":
            await reset_queue()
            continue

        parsed = parse_board_relay(user_input)
        if not parsed:
            print("Invalid input. Use board/relay, for example 1/3, or command: conf, rq, quit.")
            continue

        board_address, relay_num = parsed
        is_valid, error = validate_board_relay(boards, board_address, relay_num)
        if not is_valid:
            print(error)
            continue

        if await toggle_relay(board_address, relay_num):
            await asyncio.sleep(POST_TOGGLE_STATE_DELAY)
            relay_states = await load_relay_states()
            if relay_states is not None:
                print_relay_states(boards, relay_states)


async def main():
    """Spustí jednoduchý manual toggle demo klient."""
    parse_arguments()

    if not await check_daemon_connection():
        sys.exit(1)

    boards = await load_config()
    if boards is None:
        sys.exit(1)

    print_config(boards)
    relay_states = await load_relay_states()
    if relay_states is not None:
        print_relay_states(boards, relay_states)

    await interactive_loop(boards)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    asyncio.run(main())
