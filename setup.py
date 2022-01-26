# -*- coding: utf-8 -*-
"""
    happyfool_bot
    ~~~~~~~~~~~~~~~~~~

    Setup script for packaging and installing happyfool_bot
"""
import pathlib
from setuptools import setup, find_packages

this_directory = pathlib.Path(__file__).parent.resolve()
long_description = (this_directory / 'README.md').read_text(encoding='utf-8')

setup(
    name="happyfool_bot",
    version="0.1.0",
    description='A Twitch bot that is happy and fool at the same time',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Hugo Cisneiros (Eitch)',
    author_email='hugo.cisneiros@gmail.com',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3 :: Only',
    ],
    keywords='bot, twitch, chatbot, irc, entertainment',
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.6, <4",
    install_requires=[
        "twitchio==2.1.4",
        "aiosqlite==0.17.0",
        "SQLAlchemy==1.4.31"
    ],
    entry_points={
        'console_scripts': [
            'happyfool-bot=happyfool_bot.cli:main'
        ],
    },
)
