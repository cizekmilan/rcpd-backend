#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# rel. 2024-10-23 <milan.cizek@starnet.cz>

import fcntl
import getopt
import json
import logging
import os
import queue
import re
import signal
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from threading import Event, Lock
from dotenv import load_dotenv
from termcolor import colored

import repository
from models import db
import relay_drivers
from protocol import parse_modbus_address
import ws_server


VERSION = "0.95"

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def get_env_int(name, default):
    """Načte celočíselnou hodnotu z .env a při chybě vrátí výchozí hodnotu."""
    try:
        return int(os.getenv(name, default))
    except ValueError:
        print(f"Invalid value for {name} in .env, using default: {default}", file=sys.stderr)
        return default


def get_env_log_level(name, default):
    """Načte úroveň logování z .env a při chybě vrátí výchozí hodnotu."""
    levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARN": logging.WARNING,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    default = default.upper()
    value = (os.getenv(name, default) or default).upper()

    if value not in levels:
        print(f"Invalid value for {name} in .env, using default: {default}", file=sys.stderr)
        value = default

    return value, levels[value]


DEVICE = os.getenv("DEVICE", "/dev/ttyAMA0") or "/dev/ttyAMA0"
BAUD_RATE = get_env_int("BAUD_RATE", 9600)
WS_SERVER_LISTENING_ADDR = os.getenv("WS_SERVER_LISTENING_ADDR") or None
WS_SERVER_LISTENING_PORT = get_env_int("WS_SERVER_LISTENING_PORT", 8001)
COMMAND_QUEUE_MAX_SIZE = get_env_int("COMMAND_QUEUE_MAX_SIZE", 100)
LOG_FILE = os.getenv("LOG_FILE", "/var/log/rcpd.log") or "/var/log/rcpd.log"
LOG_LEVEL_NAME, LOG_LEVEL = get_env_log_level("LOG_LEVEL", "INFO")
PID_FILE = os.getenv("PID_FILE", "/var/run/rcpd.pid") or "/var/run/rcpd.pid"

DB_HOST = os.getenv("DB_HOST", "localhost") or "localhost"
DB_USER = os.getenv("DB_USER", "rcpd") or "rcpd"
DB_PASS = os.getenv("DB_PASS", "")
DB_NAME = os.getenv("DB_NAME", "rcpd") or "rcpd"


db.init(DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)


if COMMAND_QUEUE_MAX_SIZE < 1:
    print("Invalid value for COMMAND_QUEUE_MAX_SIZE in .env, using default: 100", file=sys.stderr)
    COMMAND_QUEUE_MAX_SIZE = 100


LOG_FORMAT = logging.Formatter('%(asctime)-25s %(name)-40s %(threadName)-15s %(levelname)-8s %(module)-30s %(funcName)-30s :%(lineno)-8s %(message)s')
LOGGER = logging.getLogger()
# globální logger nechává projít vše, úroveň výpisu řídí jednotlivé handlery
LOGGER.setLevel(logging.DEBUG)  # logging.NOTSET/DEBUG/INFO/WARN/ERROR/CRITICAL


def configure_file_logging():
    """Nastaví souborové logování démona; konzolový handler se přidává volitelně přes -d."""
    logger_fh = RotatingFileHandler(LOG_FILE, maxBytes=(1024*1024*1), backupCount=5)
    logger_fh.setFormatter(LOG_FORMAT)
    logger_fh.setLevel(LOG_LEVEL)
    LOGGER.addHandler(logger_fh)


def log_runtime_config():
    """Zapíše do logu základní runtime konfiguraci bez citlivých údajů."""
    LOGGER.info("serial: device=%s baud_rate=%d", DEVICE, BAUD_RATE)
    LOGGER.info("websocket: listen_addr=%s listen_port=%d", WS_SERVER_LISTENING_ADDR, WS_SERVER_LISTENING_PORT)
    LOGGER.info("command queue: max_size=%d", COMMAND_QUEUE_MAX_SIZE)
    LOGGER.info("database: host=%s name=%s", DB_HOST, DB_NAME)
    LOGGER.info("logging: level=%s file=%s", LOG_LEVEL_NAME, LOG_FILE)


# Poznámky:
#  * Ohledně zamykání operací nad MODBUS (vyčítání stavů vs. ovládání relé): zde není třeba kritické sekce řešit,
#    protože vlastní transfer by měl být zamykán v knihovně modbus.py. Doplnění: není tomu úplně 100%, např při souběhu
#     vyčítání stavů relé docházelo k náhodným pádům do výjimku ModbusException: RX error: Incorrect address received.
#     Uzavřením této operace do kritické sekce byl problém vyřešen. V případě vykonávání ostatních řídících příkazů není
#     potřeba žádných úprav, jelikož souběh zde díky frontě nehrozí.
#  * Protokol MOSBUS (RTU) umožňuje adresovat slave zařízení od 0, nicméně často je doporováno začínat 1.
#  * V databázi jsou MODBUS adresy uloženy v dekadickém tvaru, zde se vnitřně pracuje také s dekadickým tvarem, pouze
#    příchozí příkazy (JSON) mohou obsahovat také hex adresaci 0x, kterou po přijetí převedeme. Ve výpisech jsou uvedeny
#    obě reprezentace dec i hex.


# objekty relay bordů
boards = []
# fronta (FIFO) přijatých příkazů přes websocket, které se postupně zpracovávají
cmds_queue = queue.Queue(maxsize=COMMAND_QUEUE_MAX_SIZE)
# poslední úspěšně vyčtený stav všech relé
relay_states = {}
# příznak prvního úspěšného vyčtení stavů relé
relay_states_initialized = False
# zámek kritické sekce bránící souběhu při Modbus komunikaci
lock = Lock()
# zámek pro konzistentní čtení a zápis snapshotu stavů relé mezi vlákny
state_lock = Lock()
shutdown_event = Event()
_modbus = None


def signal_handler(sig, frame):
    """Zpracuje ukončení přes Ctrl+C nebo SIGTERM a požádá démona o korektní doběhnutí."""
    LOGGER.info("shutdown requested, received signal %s", sig)
    shutdown_event.set()


def remove_pid_file():
    """Odstraní PID soubor vytvořený při startu démona."""
    try:
        os.remove(PID_FILE)
        LOGGER.debug("pid file '%s' removed", PID_FILE)
    except FileNotFoundError:
        LOGGER.debug("pid file '%s' already removed", PID_FILE)
    except OSError as err:
        LOGGER.error("pid file '%s' could not be removed: %s", PID_FILE, err)


def close_modbus():
    """Zavře otevřený Modbus/sériový port, pokud existuje."""
    if _modbus is None:
        return

    try:
        if _modbus.is_open():
            _modbus.close()
            LOGGER.info("serial device closed")
    except Exception as err:
        LOGGER.error("serial device could not be closed cleanly: %s", err)


def cleanup(websocket_t=None, remove_pid=False):
    """Uklidí runtime prostředky při ukončení démona."""
    LOGGER.info("stopping rcpd daemon ...")
    shutdown_event.set()

    if websocket_t and websocket_t.is_alive():
        websocket_t.join(timeout=5)
        if websocket_t.is_alive():
            LOGGER.warning("websocket server thread did not stop within timeout")

    close_modbus()

    if remove_pid:
        remove_pid_file()


def sleep_interruptible(seconds):
    """Spí po kratších úsecích, aby šlo rychle reagovat na shutdown signál."""
    return shutdown_event.wait(timeout=seconds)


def is_already_running():
    """Zjistí, zda už běží jiná instance démona se stejným PID souborem."""
    lock_fp = os.open(PID_FILE, os.O_WRONLY | os.O_CREAT, mode=0o644)
    try:
        fcntl.lockf(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.ftruncate(lock_fp, 0)
        os.lseek(lock_fp, 0, os.SEEK_SET)
        os.write(lock_fp, str.encode(str(os.getpid())))
        LOGGER.debug("pid file '%s' created", PID_FILE)
        already_running = False
    except IOError:
        already_running = True

    return already_running


def print_usage():
    """Vypíše dostupné argumenty démona."""
    print(f"Usage: {os.path.basename(__file__)} [-d] [-h] [-v]")
    print("  -d|--debug        mirror logs to console using LOG_LEVEL")
    print("  -h|--help         display this help and exit")
    print("  -v|--version      print version of this script")


def parse_arguments():
    """Zpracuje argumenty příkazové řádky, které mění chování procesu."""
    try:
        opts, args = getopt.getopt(sys.argv[1:], "dhv", ["debug", "help", "version"])
    except getopt.GetoptError:
        print_usage()
        sys.exit(2)

    for opt, arg in opts:
        if opt in ("-d", "--debug"):
            # přidáme logování do konzole
            logger_ch = logging.StreamHandler(sys.stdout)
            logger_ch.setFormatter(LOG_FORMAT)
            logger_ch.setLevel(LOG_LEVEL)  # logging.NOTSET/DEBUG/INFO/WARN/ERROR/CRITICAL
            LOGGER.addHandler(logger_ch)
        elif opt in ("-h", "--help"):
            print_usage()
            sys.exit(0)
        elif opt in ('-v', '--version'):
            print(f"RCPD {VERSION}")
            sys.exit(0)


def get_boards_from_db():
    """Načte povolené relay boardy z databáze, vytvoří runtime objekty a vrátí jejich počet."""
    retval, board_addresses, total_boards, disabled_boards = repository.get_enabled_board_addresses()
    if not retval:
        return len(boards)

    loaded_boards = []
    for address in board_addresses:
        loaded_boards.append(relay_drivers.R421B16(_modbus, address=address))
        LOGGER.debug("added relay board with address %d (0x%X)", address, address)

    boards.clear()
    boards.extend(loaded_boards)
    LOGGER.info("loaded relay boards: %d (%d disabled)", total_boards, disabled_boards)
    return len(boards)


def format_relay_states(states):
    """Zformátuje stavy relé do krátkého jednořádkového zápisu pro log."""
    formatted_boards = []

    for board_address in sorted(states):
        board_states = states[board_address]
        relay_states_text = "".join(str(board_states[relay]) for relay in sorted(board_states))
        formatted_boards.append(f"0x{board_address:02X}={relay_states_text}")

    return " ".join(formatted_boards)


def get_relay_states():
    """Vyčte aktuální stavy všech registrovaných relé přes Modbus a vrátí, zda čtení proběhlo úspěšně."""
    global relay_states_initialized

    time.sleep(0.02)

    if not boards:
        with state_lock:
            relay_states.clear()
            relay_states_initialized = False
        LOGGER.warning("relay states could not be read because no relay boards are registered")
        return False

    current_states = {}

    # postupně načteme stavy relé všech našich desek
    for board in boards:
        try:
            with lock:
                current_states[board.address] = board.get_status_all()
        except (relay_drivers.TransferException, relay_drivers.ModbusException) as err:
            LOGGER.error("error when reading relay board address %d (0x%X), status: %s", board.address, board.address, err)
            return False

    with state_lock:
        previous_states = {
            board_address: dict(states)
            for board_address, states in relay_states.items()
        }
        first_successful_read = not relay_states_initialized
        states_changed = previous_states != current_states
        relay_states.clear()
        relay_states.update(current_states)
        relay_states_initialized = True

    time.sleep(0.02)

    if first_successful_read:
        LOGGER.info("relay states initial: %s", format_relay_states(current_states))
    elif states_changed:
        LOGGER.info("relay states changed: %s", format_relay_states(current_states))
    else:
        LOGGER.debug("relay states unchanged: %s", format_relay_states(current_states))

    return True


def get_relay_states_snapshot():
    """Vrátí konzistentní kopii posledního známého stavu relé pro WebSocket odpovědi."""
    with state_lock:
        return {
            board_address: dict(states)
            for board_address, states in relay_states.items()
        }


def get_board_by_addr(address):
    """Najde runtime objekt relay boardu podle Modbus adresy."""
    for board in boards:
        if board.address == address:
            return board

    return None  # null object


def print_command_result(command, retval):
    """Vypíše výsledek vykonání příkazu do konzole."""
    if not retval:
        print(f"command {repr(command):<15} [{colored('FAILED', 'red')}]")
    else:
        print(f"command {repr(command):<15} [{colored('SUCCESS', 'green')}]")


def execute_relay_command(board, command, arguments):
    """Vykoná řídící příkaz nad konkrétní relay deskou."""
    if command == "CMD_ON_ALL":
        LOGGER.debug("call board.on_all()")
        return board.on_all()
    elif command == "CMD_OFF_ALL":
        LOGGER.debug("call board.off_all()")
        return board.off_all()
    elif command == "CMD_ON":
        LOGGER.debug("call board.on_multi(%s)", arguments["relays"])
        return board.on_multi(arguments["relays"])
    elif command == "CMD_OFF":
        LOGGER.debug("call board.off_multi(%s)", arguments["relays"])
        return board.off_multi(arguments["relays"])
    elif command == "CMD_TOGGLE":
        LOGGER.debug("call board.toggle_multi(%s)", arguments["relays"])
        return board.toggle_multi(arguments["relays"])
    elif command == "CMD_LATCH":
        LOGGER.debug("call board.latch_multi(%s)", arguments["relays"])
        return board.latch_multi(arguments["relays"])
    elif command == "CMD_MOMENTARY":
        LOGGER.debug("call board.momentary_multi(%s)", arguments["relays"])
        return board.momentary_multi(arguments["relays"])
    elif command == "CMD_DELAY":
        LOGGER.debug("call board.delay_multi(%s, %d)", arguments["relays"], arguments["delay"])
        return board.delay_multi(arguments["relays"], arguments["delay"])

    return False


def process_relay_command(command, command_data):
    """Zpracuje řídící příkaz, který pracuje s jednou nebo více relay deskami."""
    for (address, arguments) in command_data.items():
        address = parse_modbus_address(address)

        print(f"processing command '{command}' on slave address: {address:d} (0x{address:X})")

        board = get_board_by_addr(address)
        if not board:
            LOGGER.error("relay board with address %d (0x%X) is not registered!", address, address)
            continue

        try:
            retval = execute_relay_command(board, command, arguments)
            print_command_result(command, retval)

            if retval and cmds_queue.qsize() > 0 and cmds_queue.qsize() % 5 == 0:
                LOGGER.debug("queue is long: %d, get_relay_states() processed", cmds_queue.qsize())
                get_relay_states()

        except (relay_drivers.TransferException, relay_drivers.ModbusException) as err:
            print_command_result(command, False)
            LOGGER.error("MODBUS transfer error: %s", err)


def process_helper_command(command):
    """Zpracuje pomocný příkaz, který se dostal do hlavní fronty."""
    if command == "CFG_CHANGED":
        get_boards_from_db()


def process_queued_command(json_data):
    """Zpracuje jeden validovaný JSON příkaz vyzvednutý z fronty."""
    for (command, command_data) in json_data.items():
        if re.match("^CMD_(ON|OFF|ON_ALL|OFF_ALL|TOGGLE|LATCH|MOMENTARY|DELAY)$", command):
            process_relay_command(command, command_data)
        elif re.match("^(CMD_HELLO|CMD_GETCONFIG|CMD_GETSTATES|CFG_CHANGED|CMD_RSTQUEUE)$", command):
            process_helper_command(command)
        else:
            print("unsupported command '%s'! Aborted." % command)


def process_command_queue():
    """Postupně zpracuje všechny příkazy čekající ve frontě."""
    while not cmds_queue.empty():
        json_data = json.loads(cmds_queue.get())
        LOGGER.debug("processing request: %s", json_data)
        process_queued_command(json_data)


def print_startup_banner():
    """Vypíše základní startovací informace démona."""
    print(colored("Remote Control Power Delivery (RCPD)", 'red', attrs=['reverse', 'blink']))
    print("initializing ....")


def init_modbus():
    """Vytvoří a otevře Modbus spojení k relay deskám."""
    modbus = relay_drivers.Modbus(serial_port=DEVICE, baud_rate=BAUD_RATE)

    try:
        modbus.open()
        print(f"serial device '{DEVICE}' successfully opened at {BAUD_RATE} baud.")
    except relay_drivers.SerialOpenException as err:
        LOGGER.error("serial device '%s' error: %s", DEVICE, err)
        print(err)
        sys.exit(1)

    return modbus


def start_ws_server():
    """Spustí WebSocket server v samostatném vlákně."""
    LOGGER.info("starting websocket server thread ...")
    startup_event = Event()
    startup_error = {}

    websocket_t = threading.Thread(
        target=ws_server.run,
        args=(WS_SERVER_LISTENING_ADDR, WS_SERVER_LISTENING_PORT, cmds_queue, get_relay_states_snapshot, startup_event, startup_error, shutdown_event),
        daemon=True,
    )
    websocket_t.start()

    if not startup_event.wait(timeout=5):
        LOGGER.error("websocket server did not report startup status within timeout")
        print("WebSocket server startup timeout. Terminated.")
        sys.exit(1)

    if startup_error:
        LOGGER.error("websocket server startup failed: %s", startup_error["error"])
        print(f"WebSocket server startup failed: {startup_error['error']}")
        sys.exit(1)

    LOGGER.info("websocket server thread started")
    return websocket_t


def main_loop():
    """Spouští hlavní nekonečnou smyčku démona."""
    while not shutdown_event.is_set():
        # zaregistrujeme (přidáme do seznamu) objekty relay desek
        # pokud se nepodaří nebo neexistuje v databázi žádný záznam, pak nemá smysl pokračovat (není co vyčítat ani řídit, zbrzdíme)
        if len(boards) == 0:
            LOGGER.debug("there are no relay boards in the list we are trying to load them")
            LOGGER.debug("refreshing configuration ...")
            get_boards_from_db()
            if sleep_interruptible(5):
                break

        # vyčteme stavy relé na všech dostupných deskách
        get_relay_states()
        process_command_queue()


def main():
    """Inicializuje démona a předá řízení hlavní smyčce."""
    global _modbus
    websocket_t = None
    pid_owned = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        parse_arguments()
        configure_file_logging()
        print_startup_banner()
        log_runtime_config()

        if is_already_running():
            print("Another instance is already running! Terminated.")
            sys.exit(1)
        pid_owned = True

        _modbus = init_modbus()

        websocket_t = start_ws_server()
        print("initializing done.")
        main_loop()
    finally:
        if pid_owned or websocket_t or _modbus:
            cleanup(websocket_t, remove_pid=pid_owned)


if __name__ == '__main__':
    main()
