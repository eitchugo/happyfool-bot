# -*- coding: utf-8 -*-
"""
    happyfool_bot.db.dals
    ~~~~~~~~~~~~~~~~~~~~~

    Data Access Layers

    :copyright: (c) 2022 by Hugo Cisneiros.
    :license: GPLv3, see LICENSE for more details.
"""
import time
import sqlalchemy.exc
from sqlalchemy import update, delete
from sqlalchemy.future import select
from sqlalchemy.orm import Session

from happyfool_bot.db.models import UserCommand, UserPoints


class UserCommandDAL:
    """
    Data Access Layer for user commands

    Args:
        db_session (Session): Database session to work on
    """
    def __init__(self, db_session):
        self.db_session = db_session

    async def create_command(self, name, creator, text):
        """
        Creates a new user command

        Args:
            name (str): Command name
            creator (str): Who is creating the command
            text (str): Command reply text
        """
        new_command = UserCommand(name=name, creator=creator, timestamp=time.time(), text=text)
        self.db_session.add(new_command)
        await self.db_session.flush()

    async def get_command_by_name(self, name):
        """
        Gets a command by its name

        Args:
            name (str): Command name

        Returns:
            UserCommand: Object containing the command. None if not found.
        """
        query = select(UserCommand).where(UserCommand.name == name)
        result = await self.db_session.execute(query)
        try:
            return result.first()
        except sqlalchemy.exc.NoResultFound:
            return None

    async def get_command_by_id(self, id):
        """
        Gets a command by its ID

        Args:
            id (int): Command ID

        Returns:
            UserCommand: Object containing the command. None if not found.
        """
        query = select(UserCommand).where(UserCommand.id == id)
        result = await self.db_session.execute(query)
        try:
            return result.first()
        except sqlalchemy.exc.NoResultFound:
            return None

    async def get_all_commands(self):
        """
        Gets all commands

        Returns:
            list[UserCommand]: A list of objects containing all commands
        """
        query = select(UserCommand).order_by(UserCommand.id)
        result = await self.db_session.execute(query)
        return result.scalars().all()

    async def update_command(self, id, text):
        """
        Updates a command's text.

        Args:
            text (str): Command's reply text
        """
        query = update(UserCommand).where(UserCommand.id == id)
        query = query.values(text=text)

        query.execution_options(synchronize_session="fetch")
        await self.db_session.execute(query)

    async def delete_command(self, id):
        """
        Deletes a command.

        Args:
            id (int): ID of the command to delete
        """
        query = delete(UserCommand).where(UserCommand.id == id)
        query.execution_options(synchronize_session="fetch")
        await self.db_session.execute(query)

    async def increment_counter(self, id):
        """
        Increments a command's counter by one

        Args:
            id (int): Command ID
        """
        query = update(UserCommand).where(UserCommand.id == id)
        count = UserCommand.count + 1
        query = query.values(count=count)
        await self.db_session.execute(query)


class UserPointsDAL:
    """
    Data Access Layer for user points / loyality

    Args:
        db_session (Session): Database session to work on
    """
    def __init__(self, db_session):
        self.db_session = db_session

    async def add_user(self, user):
        """
        Adds a user to the table with zeroed stats

        Args:
            user (str): unique name of a user
        """
        new_user = UserPoints(user=user)
        self.db_session.add(new_user)
        await self.db_session.flush()

    async def get_user(self, user):
        """
        Gets a user

        Args:
            user (str): User unique name

        Returns:
            UserPoints: Object containing the User. None if not found.
        """
        query = select(UserPoints).where(UserPoints.user == user)
        result = await self.db_session.execute(query)
        try:
            return result.first()
        except sqlalchemy.exc.NoResultFound:
            return None

    async def delete_user(self, user):
        """
        Deletes a user from the points/loyality table

        Args:
            id (int): ID of the command to delete
        """
        query = delete(UserPoints).where(UserPoints.user == user)
        query.execution_options(synchronize_session="fetch")
        await self.db_session.execute(query)

    async def get_points(self, user):
        """
        Gets points quantity for a user

        Args:
            user (str): User unique name

        Returns:
            int: quantity of points the user currently have
        """
        user_obj = await self.get_user(user)
        if user_obj:
            return user_obj[0].points
        else:
            return 0

    async def increment_points(self, user, quantity):
        """
        Increment points for a user

        Args:
            user (str): unique name of a user
            quantity (int): how many points to increment
        """
        user_obj = await self.get_user(user)
        if user_obj:
            query = update(UserPoints).where(UserPoints.user == user)
            plus_points = UserPoints.points + quantity
            query = query.values(points=plus_points)
            await self.db_session.execute(query)
        else:
            await self.add_user(user)
            await self.increment_points(user, quantity)

    async def increment_minutes(self, user, quantity):
        """
        Increments minutes for a user

        Args:
            user (str): unique name of a user
            quantity (int): how many minutes to increment
        """
        user_obj = await self.get_user(user)
        if user_obj:
            query = update(UserPoints).where(UserPoints.user == user)
            plus_minutes = UserPoints.minutes + quantity
            query = query.values(minutes=plus_minutes)
            await self.db_session.execute(query)
        else:
            await self.add_user(user)
            await self.increment_minutes(user, quantity)

    async def decrement_points(self, user, quantity):
        """
        Decrements points for a user

        Args:
            user (str): unique name of a user
            quantity (int): how many points to decrement
        """
        user_obj = await self.get_user(user)
        if user_obj:
            query = update(UserPoints).where(UserPoints.user == user)
            # floor is always 0
            if (user_obj[0].points - quantity) <= 0:
                minus_points = 0
            else:
                minus_points = UserPoints.points - quantity

            query = query.values(points=minus_points)
            await self.db_session.execute(query)
        else:
            await self.add_user(user)
            await self.decrement_points(user, quantity)

    async def get_hours(self, user):
        """
        Gets watched hours for a user

        Args:
            user (str): User unique name

        Returns:
            str: registered hours
        """
        user_obj = await self.get_user(user)
        if user_obj:
            minutes = user_obj[0].minutes
            hours = int(minutes/60)
            return f"{hours}h"
        else:
            return "0h"

    @staticmethod
    def get_rank(ranks, points):
        """
        Gets a user rank based on points. The received ranks format is::

            {
                "<rank-name>": "<minimum-points>",
                "Rank1": "0",
                "Rank2: "1000",
                "Rank3: "5000",
                ...
            }

        Args:
            ranks (dict): A dict with the ranks and minimum points to reach them. See method description.
            points (int): Number of points to check for a rank

        Returns:
            str: Rank name
        """
        result = None
        for rank, minimum in ranks.items():
            if points >= int(minimum):
                result = f"{rank}"

        if result is None:
            result = "Sem rank"

        return result
