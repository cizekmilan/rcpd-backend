# ⚡ RCPD Backend

> Python daemon and WebSocket API for remotely switching power outputs through R421B16 Modbus relay boards.

# 🎯 Overview

RCPD Backend provides a small daemon for controlling relay outputs over Modbus RTU. It is primarily intended for 16-channel R421B16 RS485 relay boards connected to a Raspberry Pi or another Linux device.

The original use case is remote power control in a server room: switching or restarting devices that do not provide IPMI, managed PDU support, or another dedicated remote power interface.

The backend currently provides:

* R421B16 relay board support over Modbus RTU
* a long-running `rcpd.py` daemon
* a WebSocket API for control and state queries
* MySQL/MariaDB-backed board and relay configuration
* hardware smoke test script
* protocol unit tests

The daemon keeps Modbus access serialized, periodically reads relay states, and exposes the latest known state through the WebSocket API.

# 🗂️ Project Structure

```text
/
├── rcpd.py                      # Main daemon entry point
├── ws_server.py                 # WebSocket server and immediate API responses
├── protocol.py                  # WebSocket command validation and address parsing
├── models.py                    # Peewee database models
├── repository.py                # Database read/query helpers
├── requirements.txt             # Python dependencies
├── .env.example                 # Example local configuration
├── relay_drivers/
│   ├── R421B16.py               # R421B16 relay board driver
│   ├── modbus.py                # Low-level Modbus RTU helper
│   └── serial_ports.py          # Serial port discovery helper
├── examples/
│   └── hardware_smoke_test.py
└── tests/
    └── test_protocol.py         # WebSocket protocol validation tests
```

# ⚙️ Requirements

Runtime requirements:

* Python 3
* MySQL or MariaDB
* RS485 serial interface
* one or more R421B16 relay boards

Python dependencies:

```text
peewee
PyMySQL
python-dotenv
pyserial
termcolor
websockets
```

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

# 🔧 Configuration

Create a local `.env` file from the example:

```bash
cp .env.example .env
```

Example configuration:

```env
DB_HOST=localhost
DB_USER=rcpd
DB_PASS=change-me
DB_NAME=rcpd

DEVICE=/dev/ttyAMA0
BAUD_RATE=9600

WS_SERVER_LISTENING_ADDR=127.0.0.1
WS_SERVER_LISTENING_PORT=8001

LOG_FILE=/var/log/rcpd.log
PID_FILE=/var/run/rcpd.pid
```

Common serial devices:

```text
/dev/ttyAMA0  Raspberry Pi HAT such as Waveshare RS485 CAN HAT
/dev/ttyUSB0  USB-to-RS485 converter, often CH340-based
```

If you use a Raspberry Pi, the Waveshare RS485 CAN HAT is a recommended option.

The R421B16 factory default baud rate is usually `9600`. If your boards were reconfigured, update `BAUD_RATE` in `.env`.

The WebSocket server listens on `127.0.0.1` by default. Use `0.0.0.0` only when the API should be reachable from other hosts.

# 🚀 Running

Start the daemon:

```bash
./rcpd.py
```

Enable debug output to the console:

```bash
./rcpd.py --debug
```

Show version:

```bash
./rcpd.py --version
```

The daemon writes detailed logs to `LOG_FILE` and stores its process lock in `PID_FILE`.

# 🔌 WebSocket API

Default endpoint:

```text
ws://127.0.0.1:8001
```

The WebSocket API uses a small custom JSON protocol.

Each request must be a JSON object containing exactly one command. Incoming messages are validated before they are accepted. Invalid JSON, unknown commands, missing board addresses, invalid relay numbers, unsupported argument types, and out-of-range values are rejected and not added to the command queue.

There are two command groups:

* helper commands, which do not operate on a specific relay board
* relay commands, where the command payload is keyed by Modbus board address

Relay command payloads use this general shape:

```json
{ "COMMAND": { "BOARD_ADDRESS": { "relays": [1, 2, 3] } } }
```

Helper commands:

```json
{ "CMD_HELLO": null }
{ "CMD_GETCONFIG": null }
{ "CMD_GETSTATES": null }
{ "CMD_RSTQUEUE": null }
{ "CFG_CHANGED": null }
```

Helper command meaning:

* `CMD_HELLO` - simple daemon availability check.
* `CMD_GETCONFIG` - returns relay board and relay label configuration from the database.
* `CMD_GETSTATES` - returns the latest known relay state snapshot.
* `CMD_RSTQUEUE` - clears queued control commands that have not been processed yet.
* `CFG_CHANGED` - tells the daemon to reload relay board configuration from the database.

Relay commands:

These commands can switch one relay, multiple relays, or all relays on a selected board.

```json
{ "CMD_ON": { "0x1": { "relays": [1, 2, 3] } } }
{ "CMD_OFF": { "0x1": { "relays": [1, 2, 3] } } }
{ "CMD_TOGGLE": { "0x1": { "relays": [1, 2, 3] } } }
{ "CMD_LATCH": { "0x1": { "relays": [1] } } }
{ "CMD_MOMENTARY": { "0x1": { "relays": [1] } } }
{ "CMD_DELAY": { "0x1": { "relays": [1], "delay": 5 } } }
{ "CMD_ON_ALL": { "0x1": null } }
{ "CMD_OFF_ALL": { "0x1": null } }
```

Relay command meaning:

* `CMD_ON` / `CMD_OFF` - switch selected relay numbers on or off.
* `CMD_TOGGLE` - toggle selected relay numbers.
* `CMD_ON_ALL` / `CMD_OFF_ALL` - switch all relays on the selected board.
* `CMD_LATCH` - board-level latch command for selected relays.
* `CMD_MOMENTARY` - board-level momentary pulse command for selected relays.
* `CMD_DELAY` - board-level delayed command using the `delay` value.

Relay numbers are `1..16`.

Board addresses can be decimal or hexadecimal strings, for example `1`, `24`, `0x01`, or `0x18`.

Each WebSocket response includes:

* `result` - `OK` or `ERROR`
* `message` - short status text
* `relay_states` - latest known relay state snapshot
* `in_queue` - number of queued control commands

# 🧪 Examples

Run the hardware smoke test against a running daemon:

```bash
python3 examples/hardware_smoke_test.py
```

The smoke test sends real relay commands. Use it only when the connected hardware can be safely switched.

# ✅ Tests

Run unit tests:

```bash
python3 -m unittest discover -s tests
```

or:

```bash
bash tests/run_unittest.sh
```

Run a syntax/bytecode check:

```bash
python3 -m compileall .
```

# 📝 Notes

- This project is intentionally focused on the backend daemon.
- The current implementation assumes R421B16-style relay numbering `1..16` in the public WebSocket protocol.
- Modbus board addresses are validated in the range `0..63`, matching the 6 DIP switch address range used by the R421B16 board.

# 🙏 Special Thanks

- [Erriez/R421A08-rs485-8ch-relay-board](https://github.com/Erriez/R421A08-rs485-8ch-relay-board) for publishing the R421A08 RS485 relay board project, which this project was originally based on and from which some files were adapted.

# License

This project is provided free of charge for personal, educational, and experimental use.

Some files in `relay_drivers/` are based on the MIT-licensed Erriez R421A08 relay board project and keep their original MIT license header.
