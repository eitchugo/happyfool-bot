# -*- coding: utf-8 -*-
"""
    happyfool_bot.db.models
    ~~~~~~~~~~~~~~~~~~~~~~~

    Database models

    :copyright: (c) 2022 by Hugo Cisneiros.
    :license: GPLv3, see LICENSE for more details.
"""
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class UserCommand(Base):
    __tablename__ = 'user_commands'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    timestamp = Column(Integer, nullable=False)
    count = Column(Integer, nullable=False, default=0)
    creator = Column(String, nullable=False)
    text = Column(String, nullable=False)

    def __repr__(self):
        return(
            f"<{self.__class__.__name__}("
            f"id='{self.id}', "
            f"name='{self.name}', "
            f"timestamp='{self.timestamp}', "
            f"count='{self.count}', "
            f"creator='{self.creator}', "
            f"text='{self.text}', "
            f")>"
        )

class UserPoints(Base):
    __tablename__ = 'user_points'

    id = Column(Integer, primary_key=True)
    user = Column(String, unique=True, nullable=False)
    minutes = Column(Integer, nullable=False, default=0)
    points = Column(Integer, nullable=False, default=0)

    def __repr__(self):
        return(
            f"<{self.__class__.__name__}("
            f"id='{self.id}', "
            f"user='{self.user}', "
            f"minutes='{self.minutes}', "
            f"points='{self.points}', "
            f")>"
        )
