#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# rel. 2024-10-23 <milan.cizek@starnet.cz>

"""
RCPD terminal UI client prototype.

This is a standalone prototype for the future SSH/PuTTY relay controller.
It loads relay rows, labels, states, and queue depth from the running rcpd
daemon while exercising layout, keyboard navigation, scrolling, terminal
resize handling, and basic row actions.

Run on Linux/Raspberry Pi over SSH:

    python3 examples/rcpd_tui.py

Keys:
    Up/Down       move one relay
    PgUp/PgDn     move one page
    Home/End      jump to first/last relay
    Tab           move through action buttons on selected row
    Left/Right    move through row action buttons
    Enter         run focused action button
    q             quit
"""

from __future__ import annotations

import curses
import asyncio
import json
import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional

import websockets


STATE_ON = "ON"
STATE_OFF = "OFF"
STATE_DISABLED = "DIS"
ACTION_COUNT = 2
WS_SERVER_ADDR = "127.0.0.1"
WS_SERVER_PORT = 8001
DAEMON_STATUS_POLL_INTERVAL = 1.0
RESET_DELAY_SECONDS = 10.0


@dataclass
class RelayRow:
    board_num: int
    board_addr: int
    relay_num: int
    description: str
    state: str
    contact_type: str = "NO"
    board_enabled: bool = True
    last_action: str = ""


@dataclass
class RuntimeState:
    clock: str
    queue_depth: Optional[int] = None
    daemon_online: bool = False
    relay_states: Optional[dict[int, dict[int, int]]] = None
    status: str = ""


@dataclass
class PendingRelayCommand:
    command: str
    board_addr: int
    relay_num: int
    description: str


def websocket_uri() -> str:
    """Sestaví WebSocket URL pro komunikaci s rcpd démonem."""
    return f"ws://{WS_SERVER_ADDR}:{WS_SERVER_PORT}"


async def send_ws_command(command: str, payload=None) -> Optional[dict]:
    """Pošle jeden příkaz rcpd démonu a vrátí dekódovanou JSON odpověď."""
    try:
        async with websockets.connect(websocket_uri(), ping_interval=30, ping_timeout=5) as websocket:
            await websocket.send(json.dumps({command: payload}))
            response = await websocket.recv()
    except (OSError, websockets.exceptions.WebSocketException):
        return None

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return None


def normalize_relay_states(raw_states) -> dict[int, dict[int, int]]:
    """Převede stavy relé z JSON odpovědi na int-indexovaný slovník."""
    relay_states = {}

    for board_address, states in raw_states.items():
        address = int(board_address)
        relay_states[address] = {
            int(relay_num): int(state)
            for relay_num, state in states.items()
        }

    return relay_states


def state_text(relay_state: Optional[int]) -> str:
    """Převede číselný stav relé z démona na text pro TUI."""
    if relay_state == 1:
        return STATE_ON
    if relay_state == 0:
        return STATE_OFF
    return "?"


def opposite_power_command(relay: RelayRow) -> str:
    """Vrati prikaz pro prepnuti do opacneho napajeciho stavu rele."""
    if relay.state == STATE_ON:
        return "CMD_OFF"

    return "CMD_ON"


def opposite_power_action_label(relay: RelayRow) -> str:
    """Vrati popisek akcniho tlacitka podle aktualniho stavu rele."""
    if opposite_power_command(relay) == "CMD_OFF":
        return "[OFF]"

    return "[ON ]"


def build_relays_from_config(config: dict, relay_states: Optional[dict[int, dict[int, int]]] = None) -> list[RelayRow]:
    """Vytvoří řádky TUI z konfigurace načtené z rcpd démona."""
    relays: list[RelayRow] = []
    board_num = 0

    for board_address in sorted(config, key=lambda value: int(value)):
        board_config = config[board_address]
        board_num += 1
        board_enabled = board_config.get("enabled") == "Y"
        address = int(board_address)
        states = relay_states.get(address, {}) if relay_states else {}
        for relay in sorted(board_config.get("relays", []), key=lambda item: int(item["relay_num"])):
            relay_num = int(relay["relay_num"])
            relays.append(
                RelayRow(
                    board_num=board_num,
                    board_addr=address,
                    relay_num=relay_num,
                    description=relay.get("description") or "-",
                    state=state_text(states.get(relay_num)) if board_enabled else STATE_DISABLED,
                    contact_type=relay.get("contact_type") or "NO",
                    board_enabled=board_enabled,
                )
            )

    return relays


def apply_relay_states(relays: list[RelayRow], relay_states: Optional[dict[int, dict[int, int]]]) -> None:
    """Aktualizuje zobrazené stavy relé podle posledního snapshotu z démona."""
    if relay_states is None:
        return

    for relay in relays:
        if relay.board_enabled:
            relay.state = state_text(relay_states.get(relay.board_addr, {}).get(relay.relay_num))
        else:
            relay.state = STATE_DISABLED


async def load_initial_relays() -> tuple[list[RelayRow], Optional[int], bool]:
    """Načte konfiguraci a první snapshot stavů relé z rcpd démona."""
    response = await send_ws_command("CMD_GETCONFIG")
    if not response or response.get("result") != "OK":
        return [], None, False

    relay_states = normalize_relay_states(response.get("relay_states", {}))
    relays = build_relays_from_config(response.get("config", {}), relay_states)

    return relays, int(response.get("in_queue") or 0), True


async def load_daemon_status() -> tuple[Optional[int], bool, Optional[dict[int, dict[int, int]]]]:
    """Načte z démona aktuální počet příkazů ve frontě a stav relé."""
    response = await send_ws_command("CMD_GETSTATES")
    if not response or response.get("result") != "OK":
        return None, False, None

    return int(response.get("in_queue") or 0), True, normalize_relay_states(response.get("relay_states", {}))


def background_status_worker(state: RuntimeState, state_lock: threading.Lock, stop_event: threading.Event) -> None:
    """Na pozadí aktualizuje čas a reálnou hloubku fronty z rcpd démona."""
    while not stop_event.is_set():
        queue_depth, daemon_online, relay_states = asyncio.run(load_daemon_status())

        with state_lock:
            state.clock = time.strftime("%H:%M:%S")
            state.queue_depth = queue_depth
            state.daemon_online = daemon_online
            state.relay_states = relay_states

        stop_event.wait(DAEMON_STATUS_POLL_INTERVAL)


def format_command_target(command: PendingRelayCommand) -> str:
    """Vrati kratky text cile rele prikazu pro stavovou listu."""
    return f"0x{command.board_addr:02X}/{command.relay_num:02d}"


def send_pending_relay_command(command: PendingRelayCommand, ws_command: str) -> Optional[dict]:
    """Odesle jeden rele prikaz z background workeru."""
    return asyncio.run(send_ws_command(
        ws_command,
        {str(command.board_addr): {"relays": [command.relay_num]}},
    ))


def command_worker(
    commands: queue.Queue,
    state: RuntimeState,
    state_lock: threading.Lock,
    stop_event: threading.Event,
) -> None:
    """Na pozadi odesila rele prikazy, aby UI smycka necekala na WebSocket."""
    while not stop_event.is_set():
        try:
            pending_command = commands.get(timeout=0.2)
        except queue.Empty:
            continue

        target = format_command_target(pending_command)
        if pending_command.command == "RST":
            with state_lock:
                state.status = f"RST started for {target}. Waiting {RESET_DELAY_SECONDS:.0f}s between toggles."

            first_response = send_pending_relay_command(pending_command, "CMD_TOGGLE")
            if not first_response:
                message = f"RST failed for {target}: daemon offline."
            elif first_response.get("result") != "OK":
                message = f"RST failed for {target}: {first_response.get('message')}"
            elif stop_event.wait(RESET_DELAY_SECONDS):
                message = f"RST interrupted for {target}."
            else:
                second_response = send_pending_relay_command(pending_command, "CMD_TOGGLE")
                if not second_response:
                    message = f"RST second toggle failed for {target}: daemon offline."
                elif second_response.get("result") != "OK":
                    message = f"RST second toggle failed for {target}: {second_response.get('message')}"
                else:
                    message = f"RST finished for {target}."
        else:
            response = send_pending_relay_command(pending_command, pending_command.command)

            if not response:
                message = f"{pending_command.command} failed for {target}: daemon offline."
            elif response.get("result") != "OK":
                message = f"{pending_command.command} failed for {target}: {response.get('message')}"
            else:
                message = f"{pending_command.command} accepted for {target}."

        with state_lock:
            state.status = message

        commands.task_done()


def set_status(state: RuntimeState, state_lock: threading.Lock, message: str) -> None:
    """Ulozi text pro spodni stavovou listu."""
    with state_lock:
        state.status = message


def init_colors() -> dict[str, int]:
    """Inicializuje curses barevné páry používané v TUI."""
    curses.start_color()
    curses.use_default_colors()

    pairs = {
        "normal": 1,
        "dim": 2,
        "header": 3,
        "board": 4,
        "selected": 5,
        "on": 6,
        "off": 7,
        "action": 8,
        "warn": 9,
        "action_focus": 10,
        "indicator": 11,
        "selected_indicator": 12,
    }

    curses.init_pair(pairs["normal"], curses.COLOR_WHITE, -1)
    curses.init_pair(pairs["dim"], curses.COLOR_CYAN, -1)
    curses.init_pair(pairs["header"], curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(pairs["board"], curses.COLOR_YELLOW, -1)
    curses.init_pair(pairs["selected"], curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(pairs["on"], curses.COLOR_GREEN, -1)
    curses.init_pair(pairs["off"], curses.COLOR_RED, -1)
    curses.init_pair(pairs["action"], curses.COLOR_CYAN, -1)
    curses.init_pair(pairs["warn"], curses.COLOR_YELLOW, -1)
    curses.init_pair(pairs["action_focus"], curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(pairs["indicator"], curses.COLOR_MAGENTA, -1)
    curses.init_pair(pairs["selected_indicator"], curses.COLOR_BLUE, curses.COLOR_WHITE)

    return pairs


def attr(pairs: dict[str, int], name: str, extra: int = 0) -> int:
    """Vrátí curses atribut pro pojmenovaný barevný pár a volitelné zvýraznění."""
    return curses.color_pair(pairs[name]) | extra


def add_clipped(stdscr: curses.window, y: int, x: int, text: str, width: int, style: int = 0) -> None:
    """Vypíše text oříznutý na šířku tak, aby nepřetekl mimo terminál."""
    if width <= 0:
        return
    try:
        stdscr.addnstr(y, x, text.ljust(width), width, style)
    except curses.error:
        pass


def ellipsize(text: str, width: int) -> str:
    """Zkrátí text na zadanou šířku a podle potřeby přidá tři tečky."""
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def add_split_bar(stdscr: curses.window, y: int, left_text: str, right_text: str, width: int, style: int) -> None:
    """VykreslĂ­ jednĂ©Ĺ™Ăˇdkovou stavovou liĹˇtu s levou a pravou ÄŤĂˇstĂ­."""
    add_clipped(stdscr, y, 0, " " * width, width, style)

    left = f" {left_text} "
    right = ellipsize(f" {right_text} ", width)
    left_width = max(0, width - len(right))

    add_clipped(stdscr, y, 0, ellipsize(left, left_width), left_width, style)
    add_clipped(stdscr, y, max(0, width - len(right)), right, len(right), style)


def render(
    stdscr: curses.window,
    pairs: dict[str, int],
    relays: list[RelayRow],
    selected: int,
    scroll: int,
    focused_action: Optional[int],
    status: str,
    runtime_state: RuntimeState,
    state_lock: threading.Lock,
) -> None:
    """Překreslí celou TUI obrazovku podle aktuálního výběru, scrollu a runtime stavu."""
    height, width = stdscr.getmaxyx()
    stdscr.erase()

    if height < 10 or width < 72:
        add_clipped(
            stdscr,
            0,
            0,
            "Terminal too small. Use at least 72x10.",
            width,
            attr(pairs, "warn", curses.A_BOLD),
        )
        stdscr.refresh()
        return

    with state_lock:
        clock = runtime_state.clock
        queue_depth = runtime_state.queue_depth
        runtime_status = runtime_state.status

    boards_count = len({relay.board_addr for relay in relays})
    relays_count = sum(1 for relay in relays if relay.relay_num > 0)
    queue_text = str(queue_depth) if queue_depth is not None else "?"
    header_left = "RCPD TUI - states and configuration"
    header_right = f"boards: {boards_count}  relays: {relays_count}  queue: {queue_text}  {clock}"
    add_split_bar(stdscr, 0, header_left, header_right, width, attr(pairs, "header", curses.A_BOLD))

    body_top = 2
    body_bottom = height - 1
    last = len(relays)
    next_index = scroll

    y = body_top
    previous_board = None

    for index in range(scroll, last):
        next_index = index + 1
        relay = relays[index]
        if relay.board_num != previous_board and y < body_bottom:
            board_status = "  DISABLED" if not relay.board_enabled else ""
            board_text = f" BOARD {relay.board_num} / 0x{relay.board_addr:02X}  R421B16{board_status} "
            board_style = attr(pairs, "board", curses.A_BOLD) if relay.board_enabled else attr(pairs, "normal", curses.A_BOLD)
            add_clipped(stdscr, y, 0, board_text, width, board_style)
            y += 1
            previous_board = relay.board_num
            if y >= body_bottom:
                break

        if not relay.board_enabled:
            continue

        if y >= body_bottom:
            next_index = index
            break

        is_selected = index == selected
        row_style = attr(pairs, "selected", curses.A_BOLD) if is_selected else attr(pairs, "normal")
        if is_selected:
            state_style = row_style
        elif relay.state == STATE_ON:
            state_style = attr(pairs, "on", curses.A_BOLD)
        elif relay.state == STATE_OFF:
            state_style = attr(pairs, "off", curses.A_BOLD)
        else:
            state_style = attr(pairs, "warn", curses.A_BOLD)
        marker = ">" if is_selected else " "
        ident = f"{relay.board_num:02d}/{relay.relay_num:02d}"
        state = f"{relay.state:<3}"
        contact_type = f"[{relay.contact_type}]"
        actions = (
            opposite_power_action_label(relay),
            "[RST]",
            "[MON]",
            "[SCHED]",
        )

        actions_width = sum(len(item) for item in actions) + len(actions) - 1
        reserved = 2 + 6 + 2 + 5 + 2 + 5 + 2 + actions_width
        desc_width = max(8, width - reserved - 1)
        desc = ellipsize(relay.description, desc_width)

        add_clipped(stdscr, y, 0, " " * width, width, row_style)
        add_clipped(stdscr, y, 0, marker, 1, row_style)
        add_clipped(stdscr, y, 2, ident, 5, row_style)
        add_clipped(stdscr, y, 9, state, 3, state_style)
        add_clipped(stdscr, y, 14, contact_type, 4, row_style)
        add_clipped(stdscr, y, 20, desc, desc_width, row_style)

        x = 21 + desc_width
        for action_index, item in enumerate(actions):
            is_control = action_index < ACTION_COUNT

            if is_control and is_selected and focused_action == action_index:
                action_style = attr(pairs, "action_focus", curses.A_BOLD)
            elif not is_control and is_selected:
                action_style = attr(pairs, "selected_indicator", curses.A_BOLD)
            elif not is_control:
                action_style = attr(pairs, "indicator", curses.A_BOLD)
            elif is_selected:
                action_style = row_style
            else:
                action_style = attr(pairs, "action")

            add_clipped(stdscr, y, x, item, len(item), action_style)
            x += len(item) + 1

        y += 1

    if scroll > 0:
        add_clipped(stdscr, body_top - 1, width - 10, "^ more", 10, attr(pairs, "dim"))
    if next_index < len(relays):
        add_clipped(stdscr, body_bottom - 1, width - 10, "v more", 10, attr(pairs, "dim"))

    footer_right = "Up/Down select | Left/Right action | Enter run | PgUp/PgDn page | q quit"
    add_split_bar(stdscr, height - 1, runtime_status or status, footer_right, width, attr(pairs, "header"))
    stdscr.refresh()


def page_size(stdscr: curses.window) -> int:
    """Spočítá přibližný počet řádků pro stránkový posun v aktuálním terminálu."""
    height, _ = stdscr.getmaxyx()
    return max(1, height - 4)


def clamp_scroll(selected: int, scroll: int, relays_count: int, stdscr: curses.window) -> int:
    """Upraví scroll tak, aby vybraný řádek zůstal viditelný."""
    if selected < 0:
        return max(0, min(scroll, max(0, relays_count - 1)))

    page = page_size(stdscr)
    if selected < scroll:
        scroll = selected
    elif selected >= scroll + page:
        scroll = selected - page + 1
    return max(0, min(scroll, max(0, relays_count - 1)))


def first_selectable_index(relays: list[RelayRow]) -> int:
    """Vrátí první ovladatelný řádek, nebo -1 pokud žádný neexistuje."""
    for index, relay in enumerate(relays):
        if relay.board_enabled:
            return index

    return -1


def last_selectable_index(relays: list[RelayRow]) -> int:
    """Vrátí poslední ovladatelný řádek, nebo -1 pokud žádný neexistuje."""
    for index in range(len(relays) - 1, -1, -1):
        if relays[index].board_enabled:
            return index

    return -1


def next_selectable_index(relays: list[RelayRow], selected: int) -> int:
    """Najde další ovladatelný řádek pod aktuálním výběrem."""
    for index in range(selected + 1, len(relays)):
        if relays[index].board_enabled:
            return index

    return selected


def previous_selectable_index(relays: list[RelayRow], selected: int) -> int:
    """Najde předchozí ovladatelný řádek nad aktuálním výběrem."""
    for index in range(selected - 1, -1, -1):
        if relays[index].board_enabled:
            return index

    return selected


def selectable_index_from_target(relays: list[RelayRow], target: int, direction: int) -> int:
    """Najde ovladatelný řádek poblíž cílového indexu pro stránkový posun."""
    if not relays:
        return -1

    target = max(0, min(target, len(relays) - 1))

    if direction >= 0:
        for index in range(target, len(relays)):
            if relays[index].board_enabled:
                return index
        return last_selectable_index(relays)

    for index in range(target, -1, -1):
        if relays[index].board_enabled:
            return index
    return first_selectable_index(relays)


def command_for_action(relay: RelayRow, focused_action: Optional[int]) -> Optional[str]:
    """Vrátí WebSocket příkaz pro vybranou řádkovou akci."""
    if focused_action is None:
        return None
    if focused_action == 0:
        return opposite_power_command(relay)
    if focused_action == 1:
        return "RST"
    return None


def enqueue_relay_command(commands: queue.Queue, relay: RelayRow, command: str) -> str:
    """Pošle relé příkaz démonu a vrátí stavovou hlášku pro spodní lištu."""
    pending_command = PendingRelayCommand(
        command=command,
        board_addr=relay.board_addr,
        relay_num=relay.relay_num,
        description=relay.description,
    )

    try:
        commands.put_nowait(pending_command)
    except queue.Full:
        return f"Local command queue is full. {command} for 0x{relay.board_addr:02X}/{relay.relay_num:02d} was not queued."

    relay.last_action = command
    return f"{command} queued for 0x{relay.board_addr:02X}/{relay.relay_num:02d}."


def run_focused_action(relay: RelayRow, focused_action: Optional[int], commands: queue.Queue) -> str:
    """Spustí akci vybranou v aktuálním řádku a vrátí stavovou hlášku."""
    command = command_for_action(relay, focused_action)
    if command:
        return enqueue_relay_command(commands, relay, command)

    return "Select an action with Tab/Left/Right first."


def read_key(stdscr: curses.window) -> int:
    """Přečte klávesu a ručně rozpozná běžné escape sekvence z PuTTY."""
    key = stdscr.getch()
    if key != 27:
        return key

    old_timeout = 250
    stdscr.timeout(20)
    sequence = []
    for _ in range(8):
        part = stdscr.getch()
        if part == -1:
            break
        sequence.append(chr(part))
    stdscr.timeout(old_timeout)

    text = "".join(sequence)
    if text in ("[D", "OD"):
        return curses.KEY_LEFT
    if text in ("[C", "OC"):
        return curses.KEY_RIGHT
    if text in ("[H", "OH", "[1~", "[7~"):
        return curses.KEY_HOME
    if text in ("[F", "OF", "[4~", "[8~"):
        return curses.KEY_END
    if text == "[5~":
        return curses.KEY_PPAGE
    if text == "[6~":
        return curses.KEY_NPAGE

    return -1


def main(stdscr: curses.window) -> None:
    """Hlavní curses smyčka TUI, která řeší kreslení a klávesové ovládání."""
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(250)

    pairs = init_colors()
    relays, queue_depth, daemon_online = asyncio.run(load_initial_relays())
    selected = first_selectable_index(relays)
    scroll = 0
    focused_action: Optional[int] = None
    if selected >= 0:
        status = "Loaded relay configuration from daemon."
    elif relays:
        status = "Relay configuration loaded, but all boards are disabled."
    else:
        status = "Unable to load relay configuration from daemon."
    runtime_state = RuntimeState(
        clock=time.strftime("%H:%M:%S"),
        queue_depth=queue_depth,
        daemon_online=daemon_online,
        status=status,
    )
    state_lock = threading.Lock()
    stop_event = threading.Event()
    command_queue = queue.Queue(maxsize=32)
    status_worker = threading.Thread(
        target=background_status_worker,
        args=(runtime_state, state_lock, stop_event),
        daemon=True,
    )
    relay_command_worker = threading.Thread(
        target=command_worker,
        args=(command_queue, runtime_state, state_lock, stop_event),
        daemon=True,
    )
    status_worker.start()
    relay_command_worker.start()

    try:
        while True:
            with state_lock:
                latest_relay_states = runtime_state.relay_states
                status = runtime_state.status

            apply_relay_states(relays, latest_relay_states)

            if selected >= 0:
                selected = min(selected, len(relays) - 1)
                scroll = clamp_scroll(selected, scroll, len(relays), stdscr)
            else:
                scroll = 0
                focused_action = None

            render(stdscr, pairs, relays, selected, scroll, focused_action, status, runtime_state, state_lock)
            key = read_key(stdscr)

            if key == -1:
                continue
            if key in (ord("q"), ord("Q")):
                break
            if key == curses.KEY_RESIZE:
                set_status(runtime_state, state_lock, "Terminal resized.")
                continue
            if selected < 0:
                if relays:
                    set_status(runtime_state, state_lock, "All configured boards are disabled. No relay can be controlled.")
                else:
                    set_status(runtime_state, state_lock, "No relay configuration loaded. Start rcpd daemon and restart TUI.")
                continue
            if key == curses.KEY_UP:
                selected = previous_selectable_index(relays, selected)
            elif key == curses.KEY_DOWN:
                selected = next_selectable_index(relays, selected)
            elif key == curses.KEY_PPAGE:
                selected = selectable_index_from_target(relays, selected - page_size(stdscr), -1)
            elif key == curses.KEY_NPAGE:
                selected = selectable_index_from_target(relays, selected + page_size(stdscr), 1)
            elif key == curses.KEY_HOME:
                selected = first_selectable_index(relays)
            elif key == curses.KEY_END:
                selected = last_selectable_index(relays)
            elif key in (9, curses.KEY_RIGHT):
                focused_action = 0 if focused_action is None else (focused_action + 1) % ACTION_COUNT
            elif key in (curses.KEY_BTAB, curses.KEY_LEFT):
                focused_action = ACTION_COUNT - 1 if focused_action is None else (focused_action - 1) % ACTION_COUNT
            elif key in (curses.KEY_ENTER, 10, 13):
                relay = relays[selected]
                set_status(runtime_state, state_lock, run_focused_action(relay, focused_action, command_queue))
    finally:
        stop_event.set()
        status_worker.join(timeout=1.5)
        relay_command_worker.join(timeout=1.5)


if __name__ == "__main__":
    curses.wrapper(main)
