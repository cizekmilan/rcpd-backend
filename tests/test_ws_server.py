#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# rel. 2024-10-23 <milan.cizek@starnet.cz>

import queue
import sys
import types
import unittest


try:
    import websockets  # noqa: F401
except ImportError:
    websockets_stub = types.ModuleType("websockets")

    class ConnectionClosed(Exception):
        """Minimální náhrada výjimky z balíku websockets pro import ws_server."""

    websockets_stub.ConnectionClosed = ConnectionClosed
    sys.modules["websockets"] = websockets_stub


try:
    import termcolor  # noqa: F401
except ImportError:
    termcolor_stub = types.ModuleType("termcolor")
    termcolor_stub.colored = lambda text, *args, **kwargs: text
    sys.modules["termcolor"] = termcolor_stub


repository_stub = types.ModuleType("repository")
repository_stub.get_relays_config = lambda: (True, {})
sys.modules["repository"] = repository_stub


try:
    import ws_server
except ImportError as err:
    ws_server = None
    WEBSOCKET_IMPORT_ERROR = err
else:
    WEBSOCKET_IMPORT_ERROR = None


@unittest.skipIf(ws_server is None, f"ws_server import failed: {WEBSOCKET_IMPORT_ERROR}")
class TestWsServer(unittest.TestCase):

    def setUp(self):
        """Ztiší logger WebSocket serveru během testů fronty."""
        self.logger_disabled = ws_server.LOGGER.disabled
        ws_server.LOGGER.disabled = True

    def tearDown(self):
        """Vrátí původní stav loggeru WebSocket serveru."""
        ws_server.LOGGER.disabled = self.logger_disabled

    def test_enqueue_command_rejects_full_queue(self):
        """Ověří, že zaplněná fronta odmítne další relay příkaz."""
        cmds_queue = queue.Queue(maxsize=1)
        cmds_queue.put('{ "CMD_ON": { "0x1": { "relays": [1] } } }')
        json_reply = {}

        retval = ws_server.enqueue_command(
            cmds_queue,
            '{ "CMD_OFF": { "0x1": { "relays": [1] } } }',
            "CMD_OFF",
            json_reply,
        )

        self.assertFalse(retval)
        self.assertEqual(json_reply["result"], "ERROR")
        self.assertEqual(json_reply["message"], "Command queue is full. Command was rejected.")
        self.assertEqual(cmds_queue.qsize(), 1)

    def test_enqueue_command_accepts_when_queue_has_space(self):
        """Ověří, že příkaz projde, pokud je ve frontě místo."""
        cmds_queue = queue.Queue(maxsize=1)
        json_reply = {}

        retval = ws_server.enqueue_command(
            cmds_queue,
            '{ "CMD_ON": { "0x1": { "relays": [1] } } }',
            "CMD_ON",
            json_reply,
        )

        self.assertTrue(retval)
        self.assertEqual(json_reply["message"], "Command accepted and placed to the queue.")
        self.assertEqual(cmds_queue.qsize(), 1)


if __name__ == "__main__":
    unittest.main()
