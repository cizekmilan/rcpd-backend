#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# rel. 2024-10-23 <milan.cizek@starnet.cz>

from peewee import CharField, ForeignKeyField, IntegerField, Model, MySQLDatabase


db = MySQLDatabase(None)


class BaseModel(Model):
    class Meta:
        database = db


class Board(BaseModel):
    id = IntegerField(primary_key=True)
    modbus_address = IntegerField()
    board_type = CharField(null=True)
    total_relays = IntegerField(default=16)
    enabled = CharField()  # sloupec 'enabled' je typu CHAR

    class Meta:
        table_name = 'boards'


class Relay(BaseModel):
    id = IntegerField(primary_key=True)
    board = ForeignKeyField(Board, backref='relays', on_delete='CASCADE')  # cizí klíč na Board
    description = CharField(null=True)
    relay_num = IntegerField()

    class Meta:
        table_name = 'relays'
