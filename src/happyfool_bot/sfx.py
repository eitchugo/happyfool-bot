# -*- coding: utf-8 -*-
"""
    happyfool_bot.sfx
    ~~~~~~~~~~~~~~~~~

    SoundFX thread

    :copyright: (c) 2022 by Hugo Cisneiros.
    :license: GPLv3, see LICENSE for more details.
"""
from pathlib import Path


class SoundFX:
    """
    SoundFX

    Args:
        sfx_path (str): Default path for relative sfx files
    """
    def __init__(self, sfx_path):
        self.sfx_path = Path(sfx_path)

