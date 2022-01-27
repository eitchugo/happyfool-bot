# -*- coding: utf-8 -*-
"""
    happyfool_bot.db.connection
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Database connection

    :copyright: (c) 2022 by Hugo Cisneiros.
    :license: GPLv3, see LICENSE for more details.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


class DatabaseConnection:
    """
    The database connection/session generation class

    Args:
        database_file (str): Path to the SQLite database file.
    """
    def __init__(self, database_file):
        database_url = f"sqlite+aiosqlite:///{database_file}"
        self.engine = create_async_engine(database_url, future=True)
        self.session = sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)
