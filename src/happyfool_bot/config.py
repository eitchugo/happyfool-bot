# -*- coding: utf-8 -*-
"""
    happyfool_bot.config
    ~~~~~~~~~~~~~~~~~~~~

    Configuration defaults for happyfool

    :copyright: (c) 2022 by Hugo Cisneiros.
    :license: GPLv3, see LICENSE for more details.
"""
from pathlib import Path
import json


class HappyFoolConfig:
    """
    Represents a configuration.
    """
    # configuration defaults
    CONFIG = {
        "debug_mode": False,
        "config_filename": Path(__file__).parent.parent.parent / "config.json",
        "database_filename": Path(__file__).parent.parent.parent / "data/happyfool.db",
        "access_token": 'replace-me',
        "channels": [],
        "user_commands_prefix": '!',
        "points_enabled": True,
        "points_name": "gatos",
        "points_timer_quantity": "10",
        "points_timer_interval": "10",
        "points_ranks": {
            "Humano Maldito": "0",
            "Gatinho": "600",
            "Gato": "1800",
            "Gatão": "5400",
            "Pantera": "16200",
            "Odin Todo-Peludão": "50000",
            "Guppy": "100000"
        },
        "sfx_path": Path(__file__).parent.parent.parent / "data/sfx",
        "sfx_player_options": {},
        "obs_websocket": {
            "host": "localhost",
            "port": "4444",
            "password": "MYSecurePassword",
            "sound_path": Path(__file__).parent.parent.parent / "data/sfx",
            "sound_volume": 0.3
        }
    }

    def __init__(self, name=None, **kwargs):
        """
        Creates a new configuration
        """
        self.name = name or self.__class__.__name__.lower()

        # set defaults
        for key, value in self.CONFIG.items():
            setattr(self, key, value)

        # set from instancing
        for key, value in kwargs.items():
            if key in self.CONFIG:
                setattr(self, key, value)

        # set from file
        with open(self.config_filename) as fp:
            try:
                file_config = json.load(fp)
            # if we can't load, we'll just load the defaults
            except FileNotFoundError:
                file_config = {}

            # set attribute if it exists on the json
            # if not, just ignore and use the defaults
            for key, value in self.CONFIG.items():
                try:
                    setattr(self, key, file_config[key])
                except KeyError:
                    pass

    def __getstate__(self):
        return self.__dict__.items()

    def __setstate__(self, items):
        for key, val in items:
            self.__dict__[key] = val

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, dict.__repr__(self))

    def __str__(self):
        res = ["{}(name={!r}):".format(self.__class__.__name__, self.name)]
        res = res + [f"  {it[0]} = {it[1]}" for it in self.__dict__.items()]
        return "\n".join(res)
