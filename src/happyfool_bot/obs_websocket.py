# -*- coding: utf-8 -*-
"""
    happyfool_bot.obs_remote
    ~~~~~~~~~~~~~~~~~~~~~~~~

    OBS Remote for sending events to an OBS web-socket server. Currently used for playing sounds, videos, changing
    scenes and such.

    :copyright: (c) 2022 by Hugo Cisneiros.
    :license: GPLv3, see LICENSE for more details.
"""
import asyncio
import simpleobsws


class OBSWebSocket:
    """
    OBS WebSocket connection that will handle all communications with OBS

    Args:
        loop (BaseEventLoop): The asyncio loop in which the websocket will work on.
        password (str): Password to use when connecting to the websocket
        host (str|Optional): Websocket Host to reach obs-websocket at
        port (int|Optional): Websocket Port to reach obs-websocket at
    """
    def __init__(self, loop, password, host="localhost", port=4444):
        self.obs_websocket = simpleobsws.obsws(
            host=host,
            port=port,
            password=password,
            loop=loop
        )

    async def connect(self):
        """
        Checks if the websocket connection is active. If it's not, tries to connect to it.

        Returns:
            bool: True if connected, otherwise False.
        """
        await self.obs_websocket.connect()
        return True

    async def play_sound(self, sound, volume, scene="current"):
        """
        Plays a sound by creating a ffmpeg_source on OBS via WebSocket.

        Args:
            sound (str): Full path of sound file.
            volume (float): Volume to play the sound. Ranges from 0.0 to 1.0.
            scene (str|Optional): The scene name to create the ffmpeg_source into. By default, uses the name `current`
                which create the source into the dynamic current scene instead of a fixed one.
        """
        # force sound path to be a str and volume to float
        sound = str(sound)
        volume = float(volume)

        # check if there's already a sound playing
        # TODO: add 1 minute of tolerance
        while True:
            # by default gets the current scene
            if scene == "current":
                result = await self.obs_websocket.call('GetCurrentScene')
            else:
                scene_list = await self.obs_websocket.call('GetSceneList')
                # check if we have the scene inside the list of scenes
                index = 0
                result = None
                for iter_scene in scene_list['scenes']:
                    if iter_scene['name'] == scene:
                        result = iter_scene
                        break
                    else:
                        index = index+1

                # fallback to current scene if we don't find any scene specified
                if not result:
                    result = await self.obs_websocket.call("GetCurrentScene")

            scene = result['name']
            sources_list = result['sources']

            sound_active = False
            for source_item in sources_list:
                if source_item['name'] == f"sound-{sound}":
                    # source is active, sound should be playing
                    sound_active = True
                    break

            # we should wait until the sound is finished
            if sound_active:
                await asyncio.sleep(1)

            # or we break the loop to play it
            else:
                break

        # create a media source for playing the sound
        await self.obs_websocket.call('CreateSource', {
            "sourceName": f"sound-{sound}",
            "sourceKind": "ffmpeg_source",
            "sceneName": scene,
            "sourceSettings": {
                "local_file": sound,
            },
            "setVisible": False
        })

        # set to a good volume...
        await self.obs_websocket.call('SetVolume', {
            "source": f"sound-{sound}",
            "volume": volume
        })

        # change monitorType so the streamer can hear it too
        await self.obs_websocket.call('SetAudioMonitorType', {
            "sourceName": f"sound-{sound}",
            "monitorType": "monitorOnly"
        })

        # play it
        await self.obs_websocket.call('SetSceneItemProperties', {
            "scene-name": scene,
            "item": {
                "name": f"sound-{sound}",
            },
            "visible": True
        })

        # check if sound is done and delete the source
        # TODO: add 1 minute of tolerance
        while True:
            result = await self.obs_websocket.call('GetMediaState', {
                "sourceName": f"sound-{sound}"
            })

            if result['mediaState'] != "ended":
                await asyncio.sleep(1)
            else:
                break

        # delete the scene
        await self.obs_websocket.call('DeleteSceneItem', {
            "scene": scene,
            "item": {
                "name": f"sound-{sound}"
            }
        })
