#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# rel. 2024-10-23 <milan.cizek@starnet.cz>

import json
import logging
import re


MIN_RELAY_NUM = 1
MAX_RELAY_NUM = 16
MIN_DELAY = 0
MAX_DELAY = 255

LOGGER = logging.getLogger(__name__)


def parse_modbus_address(address):
    """Převede Modbus adresu z dekadického nebo hexadecimálního zápisu na int."""
    if str(address).startswith("0x"):
        return int(address, base=16)

    return int(address)


def is_int_in_range(value, min_value, max_value):
    """Ověří, že hodnota je skutečný integer v zadaném rozsahu."""
    return isinstance(value, int) and not isinstance(value, bool) and min_value <= value <= max_value


def are_relays_valid(relays):
    """Ověří, že seznam relé je neprázdný a obsahuje jen čísla relé 1..16."""
    if not isinstance(relays, list) or len(relays) == 0:
        return False

    return all(is_int_in_range(relay, MIN_RELAY_NUM, MAX_RELAY_NUM) for relay in relays)


def is_command_valid(data):
    """
    Validátor, který kontroluje přijatá data (příkaz), jestli jeho obsah odpovídá definovanému vlastnímu protokolu.
    Pokud formát není validní, příkaz bude ignorován (nevykoná se / nepřidá se do fronty příkazů).
    Jsou definovány 2 skupiny příkazů:

      1) Řídící příkazy - jako první (klíč) je vždy identifikátor příkazu; následuje pak seznam, kde každý klíč identifikuje konkrétní
         desku (více desek) MODBUS slave adresou; akceptován je hexadecimální (0x), tak i dekadický tvar zápisu v rozsahu 0..63; další
         příklady v unit testech ...
           { "CMD_OFF_ALL": { "0x1": null } }
           { "CMD_ON": { "0x1": { "relays": [1, 2, 3] } } }
           { "CMD_DELAY": { "0x1": { "relays": [1, 2, 3], "delay": 5 } } }
           { "CMD_LATCH": { "0x1": { "relays": [1, 2, 3] } } }
           { "CMD_MOMENTARY": { "0x1": { "relays": [1, 2, 3] } } }

         jedním voláním je také možné požadovaný příkaz vykonat více deskách, např.
           { "CMD_TOGGLE": { "0x1": { "relays": [1, 2, 3] }, "0x2": { "relays": [1, 2, 3] } } }
           { "CMD_DELAY": { "0x1": { "relays": [1, 2, 3], "delay": 5 }, "0x2": { "relays": [1, 2, 3], "delay": 5 } } }
           { "CMD_OFF_ALL": { "0x1": null, "0x2": null, "0x3": null } }

      2) Pomocné příkazy které nevyužívají další klíče/hodnoty, jelikož nepracují s adresou desky:
           { "CMD_HELLO": null }
           { "CMD_GETCONFIG": null }
           { "CMD_GETSTATES": null }
           { "CFG_CHANGED": null }
           { "CMD_RSTQUEUE": null }
    """

    try:
        # ověříme, jestli jsme přijali validní JSON
        json_data = json.loads(data)
        LOGGER.debug("type of deserialized data: %s", json_data.__class__.__name__)

        if not isinstance(json_data, dict):
            LOGGER.error("JSON root must be an object!")
            return False, None
        elif not json_data:
            # JSON je bez obsahu '{}'
            LOGGER.error("JSON is empty!")
            return False, None
        else:
            # JSON něco obsahuje
            LOGGER.debug("passed to command validator")

            if len(json_data) != 1:
                LOGGER.error("JSON must contain exactly one command!")
                return False, None

            # v jedné zprávě očekáváme právě jeden příkaz
            for (command, command_data) in json_data.items():
                # na prvním místě (klíč) musí být vždy název příkazu
                if re.match("^CMD_(ON|OFF|ON_ALL|OFF_ALL|TOGGLE|LATCH|MOMENTARY|DELAY)$", command):
                    LOGGER.debug("parsed command '%s' is valid", command)

                    if command_data is None:
                        # neobsahuje ani jeden klíč s určením desky (adresu)
                        LOGGER.error("command does not specify any relay board address (mandatory)!")
                        return False, command
                    elif not isinstance(command_data, dict):
                        LOGGER.error("command board addresses must be specified as a JSON object!")
                        return False, command
                    elif len(command_data) == 0:
                        LOGGER.error("command does not specify any relay board address (mandatory)!")
                        return False, command
                    else:
                        # iterujeme přes desky: { "0x1": { "relays": [1, 2, 3] } }
                        for (address, arguments) in command_data.items():

                            # validace MODBUS adresy, akceptujeme dekadický i hexadecimální tvar s prefixem (0x)
                            try:
                                address = parse_modbus_address(address)

                                # deska R421B16 má pro volbu adresy 6x DIP přepínač, platná adresa musí být tedy z rozsahu 0..63
                                if not (0 <= address <= 63):
                                    LOGGER.error("address is out of the allowed range!")
                                    return False, command

                            except ValueError:
                                LOGGER.error("address '%s' is not valid number!", address)
                                return False, command

                            LOGGER.debug("address: %d (0x%X)", address, address)

                            if re.match("CMD_(ON|OFF)_ALL", command):
                                LOGGER.debug("command matched CMD_(ON|OFF)_ALL")
                                # tyto příkazy se provádějí vždy na všechna relé desky, tedy kromě adresy nemají žádné další argumenty
                                if arguments is not None:
                                    LOGGER.error("command '%s' does not accept relay arguments!", command)
                                    return False, command

                            elif re.match("CMD_(ON|OFF|TOGGLE|LATCH|MOMENTARY)", command):
                                LOGGER.debug("command matched CMD_(ON|OFF|TOGGLE|LATCH|MOMENTARY|DELAY)")

                                if arguments is None:
                                    # nedostali jsme žádné argumenty ('relays', popř. 'delay')
                                    LOGGER.error("command does not specify any arguments, eg. 'relays' (mandatory)!")
                                    return False, command
                                elif not isinstance(arguments, dict):
                                    LOGGER.error("command arguments must be specified as a JSON object!")
                                    return False, command

                                # v argumentech musí být specifikován klíč 'relays'
                                if 'relays' not in arguments:
                                    LOGGER.error("index 'relays' is not present (mandatory for this command)!")
                                    return False, command

                                if not are_relays_valid(arguments['relays']):
                                    LOGGER.error("index 'relays' must be a non-empty list of relay numbers in range %d..%d!", MIN_RELAY_NUM, MAX_RELAY_NUM)
                                    return False, command

                            elif command == "CMD_DELAY":
                                LOGGER.debug("command matched CMD_DELAY")
                                if arguments is None:
                                    LOGGER.error("command does not specify any arguments, eg. 'relays' and 'delay' (mandatory)!")
                                    return False, command
                                elif not isinstance(arguments, dict):
                                    LOGGER.error("command arguments must be specified as a JSON object!")
                                    return False, command

                                if 'relays' not in arguments:
                                    LOGGER.error("index 'relays' is not present (mandatory for this command)!")
                                    return False, command

                                if not are_relays_valid(arguments['relays']):
                                    LOGGER.error("index 'relays' must be a non-empty list of relay numbers in range %d..%d!", MIN_RELAY_NUM, MAX_RELAY_NUM)
                                    return False, command

                                # a u DELAY musí být v argumentech navíc specifikován ještě klíč 'delay'
                                if 'delay' not in arguments:
                                    LOGGER.error("index 'delay' is not present (mandatory for this command)!")
                                    return False, command

                                if not is_int_in_range(arguments['delay'], MIN_DELAY, MAX_DELAY):
                                    LOGGER.error("index 'delay' must be an integer in range %d..%d!", MIN_DELAY, MAX_DELAY)
                                    return False, command

                            else:
                                # nemělo by nastat, neprovedená validace příkazu
                                return False, command

                elif re.match("^(CMD_HELLO|CMD_GETCONFIG|CMD_GETSTATES|CFG_CHANGED|CMD_RSTQUEUE)$", command):
                    LOGGER.debug("command matched CMD_HELLO|CMD_GETCONFIG|CMD_GETSTATES|CFG_CHANGED|CMD_RSTQUEUE")
                    # příkazy bez jakýchkoliv dalších klíčů/hodnot (není dál co validovat, command_data = None)
                    if command_data is not None:
                        LOGGER.error("command '%s' does not accept any arguments!", command)
                        return False, command
                    break
                else:
                    LOGGER.error("unsupported command '%s'! Aborted.", command)
                    return False, command

            return True, command

    except ValueError as err:
        # řetězec není validní JSON formát
        LOGGER.error("json.loads exception (bad format): %s", err)
        return False, None

    return True, command
