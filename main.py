import pyrogram
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pytgcalls import PyTgCalls
from pytgcalls import idle
from pytgcalls.types import (
    AudioPiped,
    # AudioVideoPiped,
    AudioParameters,
    AudioQuality,
    # VideoParameters,
    # VideoQuality,
    Update,
)
import asyncio
# from random import randint
from volume.config.app import api_id, api_hash
from volume.config.tg_ids import dot_ch_id, dot_ch_radio_id, dot_ch_radio_access_hash
from volume.radio import default_url, startup_url, shutdown_url, radio_stations
from get_hashdict import common_hashdict, root_path_hash
from decorators import admin_only

import logging
import sys
import re

formatter = logging.Formatter('%(asctime)s %(levelname)s [%(filename)s:%(lineno)s] %(message)s')
handler_fancy_stdout = logging.StreamHandler(sys.stdout)
handler_logger = logging.FileHandler("volume/common.log", mode='a')
handler_fancy_stdout.setFormatter(formatter)
handler_logger.setFormatter(formatter)
# Корневой логгер. Должен ловить все ошибки и писать в файл.
root = logging.getLogger()
root.setLevel(logging.WARNING)
root.addHandler(handler_fancy_stdout)
root.addHandler(handler_logger)
# Логгер для красивого принта. Почему он работает, не смотря на то, что root отлавливает только WARNING — не знаю.
fancy_stdout = logging.getLogger(__name__)
fancy_stdout.setLevel(logging.INFO)
print = fancy_stdout.info

print('login in robot account')
app_robot = pyrogram.Client("volume/sessions/robot_account", api_id, api_hash)
app_robot.start()

print('login in dj account')
app_dj = pyrogram.Client("volume/sessions/dj_account", api_id, api_hash)
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


async def change_stream(url, who_called=''):
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


async def open_common_hashdict(path_hash, message):
    if path_hash in common_hashdict:
        obj = common_hashdict[path_hash]
        if "children" in obj:
            children = obj["children"]
            # print(children)
            children_buttons = [
                [
                    InlineKeyboardButton(
                        text=children[child],
                        callback_data=child
                    )
                ] for child in children
            ]
            share_button = InlineKeyboardButton(
                text="🔗",
                switch_inline_query=obj["share"]
            )
            if "parent" in obj:
                children_buttons.append(
                    [
                        InlineKeyboardButton(
                            text="⬅️",
                            callback_data=obj["parent"]
                        ),
                        share_button
                    ]
                )
            else:
                children_buttons.append(
                    [
                        share_button
                    ]
                )
            reply_markup = InlineKeyboardMarkup(children_buttons)
            await app_robot.edit_message_text(
                message.chat.id,
                message.id,
                text=obj['name'],
                reply_markup=reply_markup
            )
            return None
        if "radio_url" in obj:
            await change_stream(obj['radio_url'], who_called=message.from_user.id)
            return "▶️"
    else:
        await open_common_hashdict(root_path_hash, message)
        return "😬 битая кнопка"


@app_robot.on_message(pyrogram.filters.command(["start"]) & pyrogram.filters.private)
async def start_handler(client, message):
    new_message = await app_robot.send_message(
        message.from_user.id,
        text="Загрузка"
    )
    if len(message.command) >= 2:
        return await open_common_hashdict(message.command[1], new_message)
    return await open_common_hashdict(root_path_hash, new_message)


@app_robot.on_callback_query()
async def answer_library_id(client, callback_query, **kwargs):
    answer = await open_common_hashdict(callback_query.data, callback_query.message)
    if answer:
        await callback_query.answer(answer)


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


@app_robot.on_message(pyrogram.filters.command(["radio"]) & pyrogram.filters.private)
@admin_only
async def radio_handler(client, message):
    if len(message.command) >= 2:
        radio = message.command[1]
        if radio in radio_stations:
            print(f"{message.from_user.id} calls radio to {radio}")
            return await change_stream(
                radio_stations[radio],
                who_called=message.from_user.id
            )
            await app_robot.send_message(
                message.from_user.id,
                "True?!"
            )
    await app_robot.send_message(
        message.from_user.id,
        "**Available radio stations:**\n" + '\n'.join([key for key in radio_stations.keys()])
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


# главный обработчик событий в войсчате
@app_dj.on_raw_update()
async def raw(client, update, users, chats):
    # print(type(update))
    # print(dir(update))
    if type(update) is pyrogram.raw.types.update_group_call_participants.UpdateGroupCallParticipants:
        call = update.call
        for participant in update.participants:
            # print(participant)
            match type(participant.peer):
                case pyrogram.raw.types.PeerUser:
                    participant_type = 'user'
                    participant_id = participant.peer.user_id
                case pyrogram.raw.types.PeerChat:
                    return
                    participant_type = 'chat'
                    participant_id = participant.peer.dot_ch_chat_id
                case pyrogram.raw.types.PeerChannel:
                    return
                    participant_type = 'channel'
                    participant_id = participant.peer.dot_ch_id
            assert participant_type == 'user'

            if participant.left:
                print(f'{participant_type} {participant_id} left')
            if participant.just_joined:
                print(f'{participant_type} {participant_id} just joined')
                peer = await app_dj.resolve_peer(participant_id)
                await app_dj.invoke(
                    pyrogram.raw.functions.phone.EditGroupCallParticipant(
                        call=call,
                        participant=peer,
                        muted=False
                    )
                )
            if participant.raise_hand_rating:
                print(f'{participant_type} {participant_id} raise hand with rating {participant.raise_hand_rating}')
                # peer = await app_dj.resolve_peer(participant_id)
                # await asyncio.sleep(5)
                # if randint(0, 1):
                #     await app_dj.invoke(
                #         pyrogram.raw.functions.phone.EditGroupCallParticipant(
                #             call=call,
                #             participant=peer,
                #             raise_hand=False
                #         )
                #     )
                # else:
                #     await app_dj.invoke(
                #         pyrogram.raw.functions.phone.EditGroupCallParticipant(
                #             call=call,
                #             participant=peer,
                #             muted=False
                #         )
                #     )


try:
    asyncio.get_event_loop().run_until_complete(change_stream(startup_url, who_called=''))
    idle()
except KeyboardInterrupt:
    print('Exiting...')
finally:
    try:
        from time import sleep
        asyncio.get_event_loop().run_until_complete(change_stream(shutdown_url, who_called=''))
        sleep(5)
        app_dj_calls.leave_group_call(
            dot_ch_id
        )
        pass
    except KeyError:
        # странная ошибка из-за того, что я залогинился через канал
        pass
