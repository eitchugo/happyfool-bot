# happyfool bot

A Twitch bot that is happy and fool at the same time.

## Installing and developing

Install it inside a `virtualenv` to make things easier:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

This installs using develop mode, so you can also edit files at will :)

## Usage

Copy `sample-config.json` as `config.json` and configure its options. You will need at least a Twitch OAuth2 token and
the initial channels that the bot will join. 

To run the bot, there's only a CLI front-end for now:

```bash
# linux/macOS
happyfool-bot

# windows
venv/Scripts/happyfool-bot.exe
```

## Roadmap and ToDo

The following roadmap is planned for this bot:

### 1.0.0 milestone

* Heavy usage of `asyncio` and `TwitchIO` in all features
* Async sqlite database support
* Custom user commands (`!add, !edit, !delete, !stat`)
* Play local sounds with commands (bot running on the same PC as streamer)
* Points / Loyalty system to be used as a currency for commands/redemptions

### 1.1.0 milestone

* Use `Cogs` from `TwitchIO` to better organize code and features
* Gambling systems with points: Gamble, Roulette  
* Data backup systems

### 2.0.0 milestone

* Add a GUI (Graphical User Interface) on top of everything
* Configuration interface for core and cogs, with reload/save
