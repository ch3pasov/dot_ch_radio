from pytgcalls import PyTgCalls
from pytgcalls.types import (
    AudioPiped,
    # AudioVideoPiped,
    AudioParameters,
    AudioQuality,
    # VideoParameters,
    # VideoQuality,
    Update,
)
from volume.config.debug import disable_radio
from volume.config.tg_ids import dot_ch_id, dot_ch_radio_id, dot_ch_radio_access_hash
from volume.content import default_url

from decorators import admin_only

from global_vars import app_robot, app_dj

import asyncio
import pyrogram
import re

if not disable_radio:
    app_dj_calls = PyTgCalls(app_dj)
    app_dj_calls.start()

    app_dj_calls.join_group_call(
        dot_ch_id,
        join_as=pyrogram.raw.types.InputPeerChannel(channel_id=dot_ch_radio_id, access_hash=dot_ch_radio_access_hash)
    )

    # USE THIS IF YOU WANT ASYNC WAY
    async def get_youtube_stream(url='https://www.youtube.com/watch?v=jfKfPfyJRdk'):
        proc = await asyncio.create_subprocess_exec(
            'yt-dlp',
            '-g',
            '-f',
            # 'best[height<=?720][width<=?1280]',
            'ba',  # best audio
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return stdout.decode().split('\n')[0]

    async def change_stream(url: str, who_called=''):
        assert url.startswith('https://'), 'url must be https://...'
        print(f"{who_called} calls change_stream to {url}")
        if re.search(r'http(?:s?):\/\/(?:www\.)?youtu(?:be\.com\/watch\?v=|\.be\/)([\w\-\_]*)(&(amp;)?‌​[\w\?‌​=]*)?', url):
            new_stream = await get_youtube_stream(url=url)
            # print(new_stream)
        else:
            new_stream = url
        await app_dj_calls.change_stream(
            dot_ch_id,
            AudioPiped(
                new_stream,
                audio_parameters=AudioParameters.from_quality(AudioQuality.HIGH),
            ),
            # AudioVideoPiped(
            #     new_stream,
            #     audio_parameters=AudioParameters.from_quality(AudioQuality.HIGH),
            #     video_parameters=VideoParameters.from_quality(VideoQuality.HD_720p),
            # )
        )

    async def get_participants(chat_id):
        return await app_dj_calls.get_participants(chat_id)

    async def leave_group_call(chat_id):
        await app_dj_calls.leave_group_call(chat_id)

    @app_robot.on_message(pyrogram.filters.command(["pause"]) & pyrogram.filters.private)
    @admin_only
    async def pause_handler(client, message):
        print(f"{message.from_user.id} calls pause")
        await app_robot.send_message(message.from_user.id, await app_dj_calls.pause_stream(dot_ch_id))

    @app_robot.on_message(pyrogram.filters.command(["resume"]) & pyrogram.filters.private)
    @admin_only
    async def resume_handler(client, message):
        print(f"{message.from_user.id} calls resume")
        await app_robot.send_message(message.from_user.id, await app_dj_calls.resume_stream(dot_ch_id))

    @app_robot.on_message(pyrogram.filters.command(["time"]) & pyrogram.filters.private)
    @admin_only
    async def time_handler(client, message):
        print(f"{message.from_user.id} calls time")
        await app_robot.send_message(message.from_user.id, await app_dj_calls.played_time(dot_ch_id))

    @app_robot.on_message(pyrogram.filters.command(["change_stream"]) & pyrogram.filters.private)
    @admin_only
    async def change_stream_handler(client, message):
        url = message.command[1]
        await change_stream(
            url,
            who_called=message.from_user.id
        )
        await app_robot.send_message(
            message.from_user.id,
            "True?!"
        )

    @app_dj_calls.on_stream_end()
    async def handler(client: PyTgCalls, update: Update):
        # print("stream ended, changing to default")
        remote = await get_youtube_stream(default_url)
        await app_dj_calls.change_stream(
            dot_ch_id,
            AudioPiped(
                remote,
                audio_parameters=AudioParameters.from_quality(AudioQuality.HIGH),
            )
        )
else:
    async def start_radio():
        print("Radio is disabled")
        return None

    async def change_stream(url: str, who_called=''):
        print("Radio is disabled")
        return None

    async def get_participants(chat_id):
        print("Radio is disabled")
        return []

    async def leave_group_call(chat_id):
        print("Radio is disabled")
        return None
