#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# rel. 2024-10-23 <milan.cizek@starnet.cz>

from .modbus import Modbus, get_frame_str
from .modbus import FRAME_DELAY
from .modbus import SerialOpenException, TransferException
from .serial_ports import get_serial_ports
from .R421B16 import R421B16, ModbusException

__version__ = '1.0.1'
VERSION = __version__
