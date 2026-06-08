#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# rel. 2024-10-23 <milan.cizek@starnet.cz>

import logging

from models import Board, Relay, db


LOGGER = logging.getLogger(__name__)


def get_enabled_board_addresses():
    """Načte Modbus adresy povolených relay boardů z databáze."""
    addresses = []

    try:
        db.connect(reuse_if_open=True)

        query = (Board
                 .select(Board.modbus_address)
                 .where(Board.enabled == 'Y'))

        for board in query:
            addresses.append(board.modbus_address)

    except Exception as err:
        LOGGER.exception("DB error while loading relay boards: %s", err)
        return False, addresses
    finally:
        if not db.is_closed():
            db.close()

    return True, addresses


def get_relays_config():
    """Načte konfiguraci desek a relé z databáze pro CMD_GETCONFIG."""
    json_config = {}

    try:
        db.connect(reuse_if_open=True)

        relays = (Relay
                  .select(Relay, Board)
                  .join(Board, on=(Relay.board == Board.id))
                  .order_by(Board.modbus_address.asc(), Relay.relay_num.asc()))

        for relay in relays:
            modbus_address = relay.board.modbus_address

            if modbus_address not in json_config:
                json_config[modbus_address] = {
                    'id': relay.board.id,
                    'board_type': relay.board.board_type,
                    'total_relays': relay.board.total_relays,
                    'enabled': relay.board.enabled,
                    'relays': []
                }

            json_config[modbus_address]['relays'].append({
                'id': relay.id,
                'description': relay.description,
                'relay_num': relay.relay_num,
                'contact_type': relay.contact_type,
            })

        LOGGER.info("relays config: %s", json_config)

    except Exception as err:
        LOGGER.exception("DB error while loading relay configuration: %s", err)
        return False, json_config
    finally:
        if not db.is_closed():
            db.close()

    return True, json_config
