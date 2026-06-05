#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# rel. 2024-10-23 <milan.cizek@starnet.cz>

import asyncio
import json
import logging
import queue

import websockets
from termcolor import colored

import repository
from protocol import is_command_valid


LOGGER = logging.getLogger(__name__)


def clear_command_queue(cmds_queue):
    """Bezpečně vyprázdní frontu dosud nezpracovaných příkazů."""
    with cmds_queue.mutex:
        cmds_queue.queue.clear()


def command_status_text(command, success):
    """Vrátí barevný text výsledku zpracování příkazu pro konzolový výpis."""
    if success:
        return f"command {repr(command):<15} [{colored('SUCCESS', 'green')}]"

    return f"command {repr(command):<15} [{colored('FAILED', 'red')}]"


def mark_command_processed(json_reply, success):
    """Doplní do JSON odpovědi výsledek okamžitě zpracovaného příkazu."""
    if success:
        json_reply['result'] = "OK"
        json_reply['message'] = "Command accepted and processed."
    else:
        json_reply['result'] = "ERROR"
        json_reply['message'] = "Command accepted but processing failed."


def enqueue_command(cmds_queue, data, command, json_reply):
    """Vloží validovaný příkaz do fronty, nebo vrátí chybu při zaplnění fronty."""
    try:
        cmds_queue.put_nowait(data)
    except queue.Full:
        LOGGER.warning("command queue is full, command '%s' rejected", command)
        json_reply['result'] = "ERROR"
        json_reply['message'] = "Command queue is full. Command was rejected."
        return False

    LOGGER.debug("received command '%s' added to the queue", command)
    json_reply['message'] = "Command accepted and placed to the queue."
    return True


async def websocket_handler(websocket, path, cmds_queue, get_relay_states_snapshot):
    """Obslouží jednu WebSocket relaci a odpovídá na příchozí JSON příkazy."""
    while True:
        try:
            data = await websocket.recv()

            retval, command = is_command_valid(data)
            json_reply = {}

            if retval:
                LOGGER.debug("received data match the defined protocol and will be processed")
                json_reply['result'] = "OK"

                if command == "CMD_HELLO":
                    LOGGER.debug("received command '%s' processed without adding to the queue", command)
                    json_reply['message'] = "I am here!"

                elif command == "CMD_GETCONFIG":
                    LOGGER.debug("received command '%s' processed without adding to the queue", command)

                    retval, json_config = repository.get_relays_config()
                    json_reply['config'] = json_config

                    print(command_status_text(command, retval))
                    mark_command_processed(json_reply, retval)

                elif command == "CMD_GETSTATES":
                    LOGGER.debug("received command '%s' processed without adding to the queue", command)

                    print(command_status_text(command, True))
                    mark_command_processed(json_reply, True)

                elif command == "CMD_RSTQUEUE":
                    LOGGER.debug("received command '%s' processed without adding to the queue", command)

                    clear_command_queue(cmds_queue)
                    print(command_status_text(command, True))
                    mark_command_processed(json_reply, True)

                else:
                    enqueue_command(cmds_queue, data, command, json_reply)
            else:
                LOGGER.error("received data does not match the defined protocol and will not be processed!")
                json_reply['result'] = "ERROR"
                json_reply['message'] = "Command does not match the defined protocol and was discarded."

            json_reply['relay_states'] = get_relay_states_snapshot()
            json_reply['in_queue'] = cmds_queue.qsize()

            await websocket.send(json.dumps(json_reply))

        except websockets.ConnectionClosed:
            break


def run(listen_addr, listen_port, cmds_queue, get_relay_states_snapshot, startup_event=None, startup_error=None):
    """Spustí WebSocket server v aktuálním vlákně."""
    async def handler(websocket, path):
        await websocket_handler(websocket, path, cmds_queue, get_relay_states_snapshot)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        start_server = websockets.serve(handler, listen_addr, listen_port, ping_interval=30, ping_timeout=5)
        loop.run_until_complete(start_server)
        LOGGER.info("websocket server listening on %s:%d", listen_addr, listen_port)

        if startup_event:
            startup_event.set()

        loop.run_forever()
    except Exception as err:
        LOGGER.exception("websocket server failed to start or stopped unexpectedly: %s", err)

        if startup_error is not None:
            startup_error["error"] = err
        if startup_event:
            startup_event.set()
    finally:
        loop.close()
