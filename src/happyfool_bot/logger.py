# -*- coding: utf-8 -*-
"""
    happyfool_bot.logger
    ~~~~~~~~~~~~~~~~~~~~

    Log handling

    :copyright: (c) 2022 by Hugo Cisneiros.
    :license: GPLv3, see LICENSE for more details.
"""
import logging
import os

if not logging.getLogger().hasHandlers():
    logging.basicConfig(
        format='[%(asctime)s] [%(levelname)s] %(message)s'
    )
logging.getLogger().setLevel(os.getenv("LOG_LEVEL", "FATAL"))
logger = logging.getLogger("happyfool_bot")
