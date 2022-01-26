# -*- coding: utf-8 -*-
"""
    happyfool_bot.bot
    ~~~~~~~~~~~~~~~~~

    Bot interface, listener, etc

    :copyright: (c) 2022 by Hugo Cisneiros.
    :license: GPLv3, see LICENSE for more details.
"""
import re
from twitchio import Channel
from twitchio.ext import commands, routines
from twitchio.ext.commands.errors import CommandNotFound
from happyfool_bot.logger import logger
from happyfool_bot.utils import isolate_command
from happyfool_bot.db.dals import UserCommandDAL, UserPointsDAL
from happyfool_bot.db.models import UserCommand, Base


class Bot(commands.Bot):
    """
    Bot handler class

    Args:
        token (str): OAuth token to be used when joining Twitch channels
        prefix (str): Prefix to be used for bot commands
        db (DatabaseConnection): Database object to work on
        config (HappyFoolConfig): Configuration object for the bot
        initial_channels (list|Optional): List of strings with channels to be joined
    """

    def __init__(self, token, prefix, db, config, initial_channels=[]):
        super().__init__(
            token=token,
            prefix=prefix,
            initial_channels=initial_channels
        )
        self.prefix = prefix
        self.initial_channels = initial_channels
        self.sfx_path = config.sfx_path

        # database init
        self.db_engine = db.engine
        self.db_session = db.session
        self.loop.create_task(self.db_startup())

        # points system
        if config.points_enabled:
            self.points_enabled = True
            self.points_timer_interval = int(config.points_timer_interval)
            self.points_timer_quantity = int(config.points_timer_quantity)
            # routine to add points in intervals (instead of decorator)
            self.add_points_system = routines.routine(
                seconds=(self.points_timer_interval * 60),
                wait_first=True)(self.add_points_system)

    async def db_startup(self):
        # create db tables
        async with self.db_engine.begin() as db_conn:
            await db_conn.run_sync(Base.metadata.create_all)

    async def is_live(self):
        """
        Detect if the stream is live or not

        Returns:
            bool: True if live, otherwise False.
        """
        result = await self.fetch_streams(user_logins=self.initial_channels)
        if result:
            return True
        else:
            return False

    async def list_channel_users(self):
        """
        List channel users

        Args:
            channel (str): A channel to search on, without the leading `#`

        Returns:
            list: usernames that are currently on channel
        """
        for channel in self.connected_channels:
            user_list = []
            for chatter in channel.chatters:
                user_list.append(chatter.name)
            return user_list

    async def add_points_system(self, points):
        """
        Routine to add points and minutes to the points / loyality system.
        This lists all chatters currently on the channel and adds points to
        all of them.

        We only add points when the stream is live.

        Args:
            points (int): How many points to add
        """
        if not await self.is_live():
            return

        user_list = await self.list_channel_users()
        for user in user_list:
            async with self.db_session() as session:
                async with session.begin():
                    userpoints_dal = UserPointsDAL(session)
                    await userpoints_dal.increment_points(user, points)
                    await userpoints_dal.increment_minutes(user, self.points_timer_interval)

    async def event_ready(self):
        logger.info(f"Successfully logged in as: {self.nick}")
        if self.points_enabled:
            self.add_points_system.start(self.points_timer_quantity)

    async def event_message(self, message):
        if message.echo:
            user = self.nick
        else:
            user = message.author.name

        channel = message.channel
        content = message.content

        # check if it's a whipser
        if channel is None:
            channel = "@whisper"
        else:
            channel = f"#{message.channel.name}"

        # logging all messages
        logger.info(f"[{channel}] <{user}> {content}")

        # stop if this is the bot's message
        if message.echo:
            return

        # handle fixed commands
        await self.handle_commands(message)

    async def event_command_error(self, ctx, error):
        if isinstance(error, CommandNotFound):
            await self.user_command(ctx)

    async def user_command(self, ctx):
        """
        Searches for a user command and reply if exists

        Args:
            ctx (commands.Context): The Context object from the message that triggered the command
        """
        message = ctx.message
        content = ctx.message.content
        user = ctx.message.author.name

        command = isolate_command(self.prefix, content)
        if command:
            # if argument exists, generate to_user reply variable
            (_, *arguments) = content.split(maxsplit=1)
            try:
                to_user = arguments[0]
            except IndexError:
                to_user = user

            async with self.db_session() as session:
                async with session.begin():
                    usercommand_dal = UserCommandDAL(session)
                    usercommand = await usercommand_dal.get_command_by_name(command)
                    if usercommand is not None:
                        # increment the counter
                        await usercommand_dal.increment_counter(usercommand[0].id)
                        # replace reply with variables if needed
                        reply = usercommand[0].text
                        reply = re.sub(r"\$\(count\)", str(usercommand[0].count), reply)
                        reply = re.sub(r"\$\(user\)", str(user), reply)
                        reply = re.sub(r"\$\(touser\)", str(to_user), reply)
                        await ctx.send(reply)
                        return

    @commands.command()
    async def add(self, ctx):
        """
        Adds a command to the database of user commands. Only adds if it doesn't already exist. Only subscribers
        and moderators can add commands.

        Args:
            ctx (commands.Context): The Context object from the message that triggered the command
        """
        # only add if it's subscribers or moderators
        if not (ctx.message.author.is_subscriber or ctx.message.author.is_mod):
            return

        (_, *content) = ctx.message.content.split(maxsplit=1)
        try:
            command = isolate_command(self.prefix, f"{self.prefix}{content[0]}")
            (_, *text) = content[0].split(maxsplit=1)
            text = text[0]
        except IndexError:
            await ctx.send(f"Uso correto: !add <comando> <texto>")
            return

        async with self.db_session() as session:
            async with session.begin():
                usercommand_dal = UserCommandDAL(session)
                usercommand = await usercommand_dal.get_command_by_name(command)
                if usercommand is None:
                    # add command
                    await usercommand_dal.create_command(command, ctx.author.name, text)
                    await ctx.send(f"Comando {self.prefix}{command} adicionado")
                else:
                    # command already exists
                    await ctx.send(f"Comando {self.prefix}{command} já existe")

    @commands.command()
    async def edit(self, ctx):
        """
        Edits a command on database of user commands. Only the creator or moderators can edit commands.

        Args:
            ctx (commands.Context): The Context object from the message that triggered the command
        """
        (_, *content) = ctx.message.content.split(maxsplit=1)
        try:
            command = isolate_command(self.prefix, f"{self.prefix}{content[0]}")
            (_, *text) = content[0].split(maxsplit=1)
            text = text[0]
        except IndexError:
            await ctx.send(f"Uso correto: !edit <comando> <texto>")
            return

        user = ctx.message.author.name

        async with self.db_session() as session:
            async with session.begin():
                usercommand_dal = UserCommandDAL(session)
                usercommand = await usercommand_dal.get_command_by_name(command)
                if usercommand is not None:
                    # only edit if it's the author or moderators
                    if usercommand[0].creator == user or ctx.message.author.is_mod:
                        # add command
                        await usercommand_dal.update_command(usercommand[0].id, text)
                        await ctx.send(f"Comando {self.prefix}{command} editado")
                    else:
                        await ctx.send(f"Comandos só podem ser editados pelo autor ou moderadores")
                else:
                    # command doesn't exist
                    await ctx.send(f"Comando {self.prefix}{command} não existe")

    @commands.command()
    async def delete(self, ctx):
        """
        Deletes a command. Only moderators can use this command.

        Args:
            ctx (commands.Context): The Context object from the message that triggered the command
        """
        # only delete if it's moderators
        if not ctx.message.author.is_mod:
            return

        (_, *content) = ctx.message.content.split(maxsplit=1)
        try:
            command = isolate_command(self.prefix, f"{self.prefix}{content[0]}")
        except IndexError:
            await ctx.send(f"Uso correto: !delete <comando>")
            return

        async with self.db_session() as session:
            async with session.begin():
                usercommand_dal = UserCommandDAL(session)
                usercommand = await usercommand_dal.get_command_by_name(command)
                if usercommand is not None:
                    # delete command
                    await usercommand_dal.delete_command(usercommand[0].id)
                    await ctx.send(f"Comando {self.prefix}{command} removido")
                else:
                    # command doesn't exist
                    await ctx.send(f"Comando {self.prefix}{command} não existe")

    @commands.command()
    async def stat(self, ctx):
        """
        Gives info about a command. Everyone can use it.

        Args:
            ctx (commands.Context): The Context object from the message that triggered the command
        """
        (_, *content) = ctx.message.content.split(maxsplit=1)
        try:
            command = isolate_command(self.prefix, f"{self.prefix}{content[0]}")
        except IndexError:
            await ctx.send(f"Uso correto: !stat <comando>")
            return

        async with self.db_session() as session:
            async with session.begin():
                usercommand_dal = UserCommandDAL(session)
                usercommand = await usercommand_dal.get_command_by_name(command)
                if usercommand is not None:
                    # delete command

                    await usercommand_dal.delete_command(usercommand[0].id)
                    await ctx.send(
                        f"Comando {self.prefix}{command} "
                        f"criado por {usercommand[0].creator}, "
                        f"usado {usercommand[0].count} vezes"
                    )
                else:
                    # command doesn't exist
                    await ctx.send(f"Comando {self.prefix}{command} não existe")
