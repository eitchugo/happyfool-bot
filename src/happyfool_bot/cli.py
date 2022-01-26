# -*- coding: utf-8 -*-
"""
    happyfool_bot.cli
    ~~~~~~~~~~~~~~~~~

    CLI entry command

    :copyright: (c) 2022 by Hugo Cisneiros.
    :license: GPLv3, see LICENSE for more details.
"""

from happyfool_bot.config import HappyFoolConfig
from happyfool_bot.logger import logger
from happyfool_bot.bot import Bot
from happyfool_bot.db.connection import DatabaseConnection


def main():
    """
    Main CLI handler
    """
    config = HappyFoolConfig()

    if config.debug_mode:
        logger.setLevel("DEBUG")
    else:
        # defaults to info
        logger.setLevel("INFO")

    # create a database session
    db = DatabaseConnection(config.database_filename)

    bot = Bot(
        token=config.access_token,
        prefix=config.user_commands_prefix,
        initial_channels=config.channels,
        db=db,
        config=config
    )

    bot.run()

    return 0

if __name__ == "__main__":
    run(main())