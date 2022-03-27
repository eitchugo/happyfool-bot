# -*- coding: utf-8 -*-
"""
    happyfool_bot.bot
    ~~~~~~~~~~~~~~~~~

    Bot interface, listener, etc

    :copyright: (c) 2022 by Hugo Cisneiros.
    :license: GPLv3, see LICENSE for more details.
"""
import re
from time import time
import random
from twitchio.ext import commands, routines
from twitchio.ext.commands.errors import CommandNotFound
from happyfool_bot.logger import logger
from happyfool_bot.utils import isolate_command
from happyfool_bot.db.dals import UserCommandDAL, UserPointsDAL, SFXCommandDAL
from happyfool_bot.db.models import Base
from happyfool_bot.obs_websocket import OBSWebSocket


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

        # database init
        self.db_engine = db.engine
        self.db_session = db.session
        self.loop.create_task(self.db_startup())

        # points system
        self.points_enabled = False
        if config.points_enabled:
            self.points_enabled = True
            self.points_name = config.points_name
            self.points_ranks = config.points_ranks
            self.points_timer_interval = int(config.points_timer_interval)
            self.points_timer_quantity = int(config.points_timer_quantity)

            # main points command
            self.points_command = commands.command(
                name=self.points_name
            )(self.points_command)
            self.add_command(self.points_command)

            # routine to add points in intervals (instead of decorator)
            self.add_points_system = routines.routine(
                seconds=(self.points_timer_interval * 60),
                wait_first=True)(self.add_points_system)

        # obs websocket system
        self.obs_websocket_enabled = False
        if config.obs_websocket['enabled']:
            self.obs_websocket_enabled = True
            self.obs_websocket = OBSWebSocket(
                host=config.obs_websocket['host'],
                port=config.obs_websocket['port'],
                password=config.obs_websocket['password'],
                loop=self.loop
            )
            self.sound_path = config.obs_websocket['sound_path']
            self.sound_volume = config.obs_websocket['sound_volume']
            self.sound_scene_name = config.obs_websocket['sound_scene_name']

        # sfx system
        self.sfx_enabled = False
        if config.sfx_enabled:
            self.sfx_enabled = True

            # cooldown tables
            self.sfx_global_cooldown = {
                "<command>": "<last_used_timestamp>"
            }

            self.sfx_user_cooldown = {
                "<user1>": {
                    "<command1>": "<last_used_timestamp>",
                    "<command2>": "<last_used_timestamp>"
                }
            }

            # sfx backend type - currently only obs_websocket is supported
            if self.obs_websocket_enabled:
                self.sfx_backend = "obs_websocket"
            else:
                self.sfx_backend = None

            # jokes system
            self.jokes_filename = config.jokes_filename
            self.jokes_cooldown = config.jokes_cooldown
            self.jokes_lastused = 0

            # raffle system
            self.raffle_enabled = False
            self.raffle_is_subscriber_only = False
            self.raffle_wordkey = ""
            self.raffle_participants = []
            self.raffle_picked = []
            self.raffle_lastpick = ""

            # bets system
            self.bets_enabled = False
            if config.bets_enabled and self.points_enabled:
                self.bets_enabled = config.bets_enabled
                self.bets_minimum_bet = config.bets_minimum_bet
                self.bets_command = config.bets_command
                self.bets_all_in_word = config.bets_all_in_word
                self.bets_double_chance = config.bets_double_chance
                self.bets_triple_chance = config.bets_triple_chance
                self.bets_lose_chance = config.bets_lose_chance
                self.bets_user_cooldown = config.bets_user_cooldown
                self.bets_cooldowns = {
                    "<user>": "<last_used_timestamp>"
                }

                # add bets command
                self.bets = commands.command(
                    name=self.bets_command
                )(self.bets)
                self.add_command(self.bets)

                # slots system
                self.slots_enabled = False
                if config.slots_enabled and self.points_enabled:
                    self.slots_enabled = config.slots_enabled
                    self.slots_bet = config.slots_bet
                    self.slots_user_cooldown = config.slots_user_cooldown
                    self.slots_emotes = config.slots_emotes
                    self.slots_super_emote = config.slots_super_emote
                    self.slots_cooldowns = {
                        "<user>": "<last_used_timestamp>"
                    }

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
        if self.points_enabled:
            self.add_points_system.start(self.points_timer_quantity)

        # connect to obs websocket to enable system
        if self.obs_websocket_enabled:
            if await self.obs_websocket.connect():
                logger.info("Connected to OBS Websocket.")
            else:
                logger.error("Couldn't enable OBS Websocket system. Disabling feature.")

        # we're logged in and ready!
        logger.info(f"Successfully logged in as: {self.nick}. Bot is running!")

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

        # raffle system
        if self.raffle_enabled:
            if content == self.raffle_wordkey:
                # subscriber only workflow
                if self.raffle_is_subscriber_only:
                    if message.author.is_subscriber:
                        await self.raffle_add_participant(user)
                else:
                    await self.raffle_add_participant(user)

    async def event_command_error(self, ctx, error):
        if isinstance(error, CommandNotFound):
            await self.user_command(ctx)
            await self.sfx_command(ctx)

    ##############################################################################################
    # USER COMMANDS
    ##############################################################################################

    async def user_command(self, ctx):
        """
        Searches for a user command and reply if exists

        Args:
            ctx (commands.Context): The Context object from the message that triggered the command
        """
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
                    await ctx.send(
                        f"Comando {self.prefix}{command} "
                        f"criado por {usercommand[0].creator}, "
                        f"usado {usercommand[0].count} vezes"
                    )
                else:
                    # command doesn't exist
                    await ctx.send(f"Comando {self.prefix}{command} não existe")

    ##############################################################################################
    # POINTS SYSTEM
    ##############################################################################################

    async def points_command(self, ctx):
        """
        Wrapper command for points sub-commands

        Args:
            ctx (commands.Context): The Context object from the message that triggered the command
        """
        (_, *content) = ctx.message.content.split()
        # check if using a sub-command or just showing points
        try:
            command = isolate_command(self.prefix, f"{self.prefix}{content[0]}")
        except IndexError:
            await self.points_show(ctx)
            return

        # commands restricted to the streamer
        if ctx.message.author.is_broadcaster:
            if command == "add":
                try:
                    user = content[1]
                    quantity = int(content[2])
                except IndexError:
                    await ctx.send(f"Uso correto: {self.prefix}{self.points_name} add <user> <quantity>")
                    return

                await self.points_add(user, quantity)
                await ctx.send(f"Adicionados {quantity} {self.points_name} para {user}...")
                return

            elif command == "remove":
                try:
                    user = content[1]
                    quantity = int(content[2])
                except IndexError:
                    await ctx.send(f"Uso correto: {self.prefix}{self.points_name} remove <user> <quantity>")
                    return

                await self.points_remove(user, quantity)
                await ctx.send(f"Removidos {quantity} {self.points_name} de {user}...")
                return

            elif command == "add_all":
                await self.points_add_all(ctx)
            elif command == "remove_all":
                await self.points_remove_all(ctx)

        # for everyone else
        if command == "show":
            await self.points_show(ctx)
        else:
            await self.points_show(ctx)

    @commands.command()
    async def points_show(self, ctx):
        """
        Shows how many points a user has in the points system

        Args:
            ctx (commands.Context): The Context object from the message that triggered the command
        """
        user = ctx.author.name
        async with self.db_session() as session:
            async with session.begin():
                userpoints_dal = UserPointsDAL(session)
                points = await userpoints_dal.get_points(user)
                rank = UserPointsDAL.get_rank(self.points_ranks, points)
                hours = await userpoints_dal.get_hours(user)
                await ctx.send(f"{user}, você tem {points} {self.points_name} e é [{rank}]. Horas na live: {hours}")

    async def points_add(self, user, quantity):
        """
        Adds points to a user

        Args:
            user (str): User who will receive points
            quantity (int): Quantity of points to receive
        """
        async with self.db_session() as session:
            async with session.begin():
                userpoints_dal = UserPointsDAL(session)
                await userpoints_dal.increment_points(user, quantity)

    async def points_remove(self, user, quantity):
        """
        Removes points from a user

        Args:
            user (str): User who will lose points
            quantity (int): Quantity of points to lose
        """
        async with self.db_session() as session:
            async with session.begin():
                userpoints_dal = UserPointsDAL(session)
                await userpoints_dal.decrement_points(user, quantity)

    async def points_add_all(self, points):
        pass

    async def points_remove_all(self, points):
        pass

    async def points_query(self, user):
        """
        Queries how many points a user has and returns it.

        Args:
            user (str): User which we will query points

        Returns:
            int: how many points the user have
        """
        async with self.db_session() as session:
            async with session.begin():
                userpoints_dal = UserPointsDAL(session)
                points = await userpoints_dal.get_points(user)
                return int(points)

    ##############################################################################################
    # SFX SYSTEM
    ##############################################################################################

    @commands.command()
    async def sfx(self, ctx):
        """
        Wrapper command for sfx sub-commands

        Args:
            ctx (commands.Context): The Context object from the message that triggered the command
        """
        if not self.sfx_enabled:
            return

        (_, *content) = ctx.message.content.split(maxsplit=1)
        # check if using a sub-command
        try:
            command = isolate_command(self.prefix, f"{self.prefix}{content[0]}")
        except IndexError:
            await ctx.send(f"Uso correto: !sfx <add|remove>")
            return

        if command == "add":
            await self.sfx_add(ctx)
        elif command == "remove":
            await self.sfx_remove(ctx)

    @commands.command()
    async def sfx_add(self, ctx):
        """
        Adds an SFX command to the database of sfx commands. Only adds if it doesn't already exist. Only the streamer
        can add commands.

        Args:
            ctx (commands.Context): The Context object from the message that triggered the command
        """
        if not self.sfx_enabled:
            return

        if not ctx.message.author.is_broadcaster:
            return

        (_, *content) = ctx.message.content.split(maxsplit=1)
        try:
            action = isolate_command(self.prefix, f"{self.prefix}{content[0]}")
            (_, *command) = content[0].split()
            sfx_command = command[0]
            audio_file = command[1]
        except IndexError:
            await ctx.send(f"Uso correto: !sfx add <comando> <audio_file> [cost] [user_cooldown] [global_cooldown]")
            return

        kvargs = {}
        try:
            kvargs['cost'] = int(command[2])
        except IndexError:
            pass

        try:
            kvargs['user_cooldown'] = int(command[3])
        except IndexError:
            pass

        try:
            kvargs['global_cooldown'] = int(command[4])
        except IndexError:
            pass

        async with self.db_session() as session:
            async with session.begin():
                sfxcommand_dal = SFXCommandDAL(session)
                sfxcommand = await sfxcommand_dal.get_command_by_name(sfx_command)
                if sfxcommand is None:
                    # add command
                    await sfxcommand_dal.create_command(sfx_command, audio_file, **kvargs)
                    await ctx.send(f"Som {self.prefix}{sfx_command} adicionado")
                else:
                    # command already exists
                    await ctx.send(f"Som {self.prefix}{sfx_command} já existe")

    @commands.command()
    async def sfx_remove(self, ctx):
        """
        Deletes a command. Only moderators can use this command.

        Args:
            ctx (commands.Context): The Context object from the message that triggered the command
        """
        if not self.sfx_enabled:
            return

        # only delete if it's the stramer
        if not ctx.message.author.is_broadcaster:
            return

        (_, *content) = ctx.message.content.split(maxsplit=1)
        try:
            action = isolate_command(self.prefix, f"{self.prefix}{content[0]}")
            (_, *command) = content[0].split(maxsplit=3)
            sfx_command = command[0]
        except IndexError:
            await ctx.send(f"Uso correto: !sfx remove <comando>")
            return

        async with self.db_session() as session:
            async with session.begin():
                sfxcommand_dal = SFXCommandDAL(session)
                sfxcommand = await sfxcommand_dal.get_command_by_name(sfx_command)
                if sfxcommand is not None:
                    # delete command
                    await sfxcommand_dal.delete_command(sfxcommand[0].id)
                    await ctx.send(f"Som {self.prefix}{sfx_command} removido")
                else:
                    # command doesn't exist
                    await ctx.send(f"Som {self.prefix}{sfx_command} não existe")

    async def sfx_command(self, ctx):
        """
        Searches for an sfx command and play sound if it exists

        Args:
            ctx (commands.Context): The Context object from the message that triggered the command
        """
        if not self.sfx_enabled:
            return

        content = ctx.message.content
        user = ctx.message.author.name

        command = isolate_command(self.prefix, content)
        if command:
            async with self.db_session() as session:
                async with session.begin():
                    sfxcommand_dal = SFXCommandDAL(session)
                    sfxcommand = await sfxcommand_dal.get_command_by_name(command)
                    if sfxcommand is not None:
                        # cooldowns
                        time_now = int(time())
                        try:
                            global_cooldown = self.sfx_global_cooldown[command]
                        except KeyError:
                            global_cooldown = 1

                        try:
                            user_cooldown = self.sfx_user_cooldown[user][command]
                        except KeyError:
                            user_cooldown = 1

                        command_global_cooldown = int(sfxcommand[0].global_cooldown)
                        command_user_cooldown = int(sfxcommand[0].user_cooldown)

                        # check if command is on global cooldown
                        if (time_now - global_cooldown) < command_global_cooldown:
                            return

                        # check if user is on cooldown
                        if (time_now - user_cooldown) < command_user_cooldown:
                            return

                        # check if user has points to spend
                        if self.points_enabled:
                            command_cost = int(sfxcommand[0].cost)
                            user_points = await self.points_query(user)
                            if user_points < command_cost:
                                return
                            else:
                                await self.points_remove(user, command_cost)

                        # increment the counter
                        await sfxcommand_dal.increment_counter(sfxcommand[0].id)

                        # update cooldown counters
                        self.sfx_global_cooldown[command] = time_now
                        try:
                            self.sfx_user_cooldown[user][command] = time_now
                        except KeyError:
                            self.sfx_user_cooldown[user] = {}
                            self.sfx_user_cooldown[user][command] = time_now

                        # play the effing sound
                        await self.obs_websocket.play_sound(
                            self.sound_path / str(sfxcommand[0].audio_file),
                            self.sound_volume,
                            self.sound_scene_name
                        )

    ##############################################################################################
    # PIADAS RUIMS SYSTEM
    ##############################################################################################

    @commands.command()
    async def piadaruim(self, ctx):
        """
        PIADA RUIM LUL

        Args:
            ctx (commands.Context): The Context object from the message that triggered the command
        """
        # cooldown
        time_now = int(time())
        if not time_now > self.jokes_lastused + int(self.jokes_cooldown):
            return

        with open(self.jokes_filename, encoding="utf-8") as fp:
            lines = fp.readlines()
            quantity = len(lines)
            line_out = random.randint(0, quantity)
            await ctx.send(lines[line_out])
            self.jokes_lastused = int(time())

    ##############################################################################################
    # RAFFLE SYSTEM
    ##############################################################################################

    @commands.command()
    async def raffle(self, ctx):
        """
        Wrapper command for raffle command

        Args:
            ctx (commands.Context): The Context object from the message that triggered the command
        """
        (_, *content) = ctx.message.content.split(maxsplit=1)
        # check if using a sub-command
        try:
            command = isolate_command(self.prefix, f"{self.prefix}{content[0]}")
        except IndexError:
            await ctx.send(f"Uso correto: !sfx <add|remove>")
            return

        if command == "start":
            await self.raffle_start(ctx)
        elif command == "startsub":
            self.raffle_is_subscriber_only = True
            await self.raffle_start(ctx)
        elif command == "stop":
            await self.raffle_stop(ctx)
        elif command == "pick":
            await self.raffle_pick(ctx)

    @commands.command()
    async def raffle_start(self, ctx):
        """
        Starts a raffle.

        Args:
            ctx (commands.Context): The Context object from the message that triggered the command
        """
        # only the streamer can use this command
        if not ctx.message.author.is_broadcaster:
            return

        self.raffle_enabled = True
        self.raffle_participants = []
        self.raffle_picked = []
        message_started = "Raffle started"

        # sub-only mode if needed
        if self.raffle_is_subscriber_only:
            message_started = "Subscriber/VIP only Raffle started"

        (_, *content) = ctx.message.content.split(maxsplit=1)
        try:
            (_, *command) = content[0].split()
            self.raffle_wordkey = command[0]
        except IndexError:
            await ctx.send(f"Uso correto: !raffle start <word-key>")
            return

        await ctx.send(f"{message_started}. Word key: {self.raffle_wordkey}")

    @commands.command()
    async def raffle_stop(self, ctx):
        """
        Stops a raffle.

        Args:
            ctx (commands.Context): The Context object from the message that triggered the command
        """
        # only the streamer can use this command
        if not ctx.message.author.is_broadcaster:
            return

        self.raffle_enabled = False
        await ctx.send(f"Raffle stopped.")

    @commands.command()
    async def raffle_pick(self, ctx):
        """
        Picks a winner from the raffle participants list.

        Args:
            ctx (commands.Context): The Context object from the message that triggered the command
        """
        # only the streamer can use this command
        if not ctx.message.author.is_broadcaster:
            return

        number_participants = len(self.raffle_participants)

        if number_participants > 0:
            random_pick_number = random.randint(0, (number_participants-1))

            user_pick = self.raffle_participants[random_pick_number]
            self.raffle_participants.remove(user_pick)
            self.raffle_picked.append(user_pick)
            self.raffle_lastpick = user_pick

            await ctx.send(f"Picked a participant from the raffle: {user_pick}.")
        else:
            await ctx.send(f"No participants left in this raffle!")

    async def raffle_add_participant(self, user):
        """
        Adds a participant to the raffle participant list.

        Args:
            user (str): Nick to add to the participant list
        """
        # add raffle participant if not already added
        if user not in self.raffle_participants:
            self.raffle_participants.append(user)

    ##############################################################################################
    # BETS SYSTEM
    ##############################################################################################
    async def bets(self, ctx):
        """
        Bets main command

        Args:
            ctx (commands.Context): The Context object from the message that triggered the command
        """
        user = ctx.message.author.name

        # cooldowns
        time_now = int(time())
        try:
            user_cooldown = self.bets_cooldowns[user]
        except KeyError:
            user_cooldown = 1

        # check if user is on cooldown
        if (time_now - user_cooldown) < int(self.bets_user_cooldown):
            return

        # update cooldown timers for user
        self.bets_cooldowns[user] = time_now

        # check user points
        user_points = await self.points_query(user)

        (_, *content) = ctx.message.content.split(maxsplit=1)
        try:
            if str(content[0]) == self.bets_all_in_word:
                number_points = user_points
            else:
                number_points = int(content[0])
        except IndexError:
            number_points = self.bets_minimum_bet

        # check if the bet is at least on minimun
        if number_points < self.bets_minimum_bet:
            await ctx.send(f"{user}, você tem que apostar no mínimo 60 gatos!")
            return

        # check if the user has points or not
        if number_points > user_points:
            await ctx.send(f"{user}, você não tem gatos suficientes para apostar isso!")
            return

        # subtract quantity of points from user
        await self.points_remove(user, number_points)

        # test if the sum of odds are 100
        # if not, we will use a placeholder
        try:
            if not self.bets_double_chance + self.bets_triple_chance + self.bets_lose_chance == 100:
                self.bets_double_chance = 45
                self.bets_triple_chance = 5
                self.bets_lose_chance = 50
        except TypeError:
            self.bets_double_chance = 45
            self.bets_triple_chance = 5
            self.bets_lose_chance = 50

        number_bet = random.randint(1, 100)
        if number_bet <= self.bets_lose_chance:
            total_points = user_points - number_points
            await ctx.send(f"{user}, você perdeu {number_points} gatos. LUL Agora você tem {total_points} gatos!")
            return
        elif (number_bet > self.bets_lose_chance) and (number_bet < (100 - self.bets_triple_chance)):
            win_points = number_points * 2
            emote = "Clap"
        else:
            win_points = number_points * 3
            emote = "HYPERCLAP"

        # add the points to the user
        await self.points_add(user, win_points)
        total_points = user_points + win_points
        await ctx.send(f"{user}, você ganhou {win_points} gatos. {emote} Agora você tem {total_points} gatos!")

    ##############################################################################################
    # SLOTS SYSTEM
    ##############################################################################################
    @commands.command()
    async def slots(self, ctx):
        """
        Slots main command

        Args:
            ctx (commands.Context): The Context object from the message that triggered the command
        """
        user = ctx.message.author.name

        # cooldowns
        time_now = int(time())
        try:
            user_cooldown = self.slots_cooldowns[user]
        except KeyError:
            user_cooldown = 1

        # check if user is on cooldown
        if (time_now - user_cooldown) < int(self.slots_user_cooldown):
            return

        # update cooldown timers for user
        self.slots_cooldowns[user] = time_now

        # check user points
        user_points = await self.points_query(user)

        # check if the user has points or not
        if self.slots_bet > user_points:
            await ctx.send(f"{user}, você não tem gatos suficientes para apostar isso!")
            return

        # subtract quantity of points from user
        await self.points_remove(user, self.slots_bet)

        emotes = self.slots_emotes + [self.slots_super_emote]
        quantity_of_emotes = len(emotes)
        slot_1 = random.randint(1, quantity_of_emotes) - 1
        slot_2 = random.randint(1, quantity_of_emotes) - 1
        slot_3 = random.randint(1, quantity_of_emotes) - 1

        slots = [slot_1, slot_2, slot_3]
        slots_result = f"[ {emotes[slot_1]} {emotes[slot_2]} {emotes[slot_3]} ]"

        points_win = False
        for emote in slots:
            emote_count = slots.count(emote)
            if emote_count == 3:
                if emote == self.slots_super_emote:
                    points_win = self.slots_bet * 5
                    result_msg = f"JACKPOT!!! Ganhou {points_win} gatos!!! Kreygasm"
                    break
                else:
                    points_win = self.slots_bet * 3
                    result_msg = f"Triplo! Ganhou {points_win} gatos! CoolCat"
                    break
            elif emote_count == 2:
                points_win = self.slots_bet * 2
                result_msg = f"Dobro! Ganhou {points_win} gatos. BloodTrail"
                break;

        if not points_win:
            result_msg = f"Só perdeu {self.slots_bet} gatos. LUL"
        else:
            pass
            # add the points to the user
            await self.points_add(user, points_win)

        # message to channel with results
        await ctx.send(f"Slots deu: {slots_result} {result_msg}")
