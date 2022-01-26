# -*- coding: utf-8 -*-
"""
    happyfool_bot.utils
    ~~~~~~~~~~~~~~~~~~~

    Utilities/Misc methods

    :copyright: (c) 2022 by Hugo Cisneiros.
    :license: GPLv3, see LICENSE for more details.
"""

import re

def isolate_command(prefix, message):
    """
    Isolates the command from a chat message. Commands will begin with prefix. This also filters any non-wanted
    character from the command and strip the prefix.

    Args:
        prefix (str): When a chat message begins with this prefix, it will
            be considered a command. If it doesn't begin with this prefix,
            we'll just return None.
        message (str): The message to isolate the command from

    Returns:
        str|None: The string with the command. None if the message is not
            a command.
    """
    if re.search(r"^%s" % prefix, message):
        (command, *arguments) = message.split(maxsplit=1)
        # force only alphanum characters on command
        command = re.sub(r'[^a-z0-9]', '', command.lower())
        command = re.sub(r"^%s" % prefix, '', command)
    else:
        # this is not a command
        return None

    return command
