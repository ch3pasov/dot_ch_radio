import pyrogram
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums.chat_action import ChatAction
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
from random import random
from volume.config.app import api_id, api_hash
from volume.config.tg_ids import dot_ch_id, dot_ch_radio_id, dot_ch_radio_access_hash, beta_testers
from volume.content import default_url, startup_url, shutdown_url, wanted_not_found
from get_hashdict import common_hashdict, alias_dict
from decorators import admin_only

import logging
import sys
import re
import aiohttp

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


async def aiohttp_get(url, type='text'):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            match type:
                case 'text':
                    return await resp.text()
                case 'json':
                    return await resp.json()
                case _:
                    raise ValueError("Unknown type")


async def get_bashkir_haiku():
    return "\n".join(
        (await aiohttp_get('http://nevmenandr.net/cgi-bin/haiku.html', 'text')).split("\n")[119:122]
    ).replace("</span></td></tr>", "").replace('<tr><td></td><td><span style="color: #363636; font: normal 1.8em/1.36 Georgia">', "")


async def get_weather(location):
    lat = location.latitude
    lon = location.longitude
    weather_data = await aiohttp_get(f'https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=metric&lang=ru&appid=OPENWEATHER_API_KEY_REMOVED', 'json')

    temperature = weather_data['main']['temp']
    temperature_feels = weather_data['main']['feels_like']
    wind_speed = weather_data['wind']['speed']

    return f"В {weather_data['name']} {str(temperature)}℃\nОщущается как {temperature_feels}℃\nСкорость ветра {wind_speed}м/с"


async def open_common_hashdict(deep_link, message, user_id):
    # refresh
    if deep_link.startswith("refresh=1=id="):
        message = await app_robot.edit_message_text(
            message.chat.id,
            message.id,
            text="refreshing...",
        )
        await asyncio.sleep(1)
        return await open_common_hashdict(deep_link[10:], message, user_id)

    # id=
    path_hash = deep_link[3:]
    if not deep_link.startswith("id="):
        # aliases
        path_hash = "ERROR"
        if deep_link in alias_dict:
            path_hash = alias_dict[deep_link]

    # error
    if path_hash not in common_hashdict:
        await open_common_hashdict("", message, user_id)
        return "😬 битая кнопка"

    obj = common_hashdict[path_hash]
    # beta access
    if obj.get("beta_access", 0):
        if user_id not in beta_testers:
            await open_common_hashdict("", message, user_id)
            return "🤷‍♂️Не знаю как ты это открыл, но тебе сюда нельзя."

    # common case
    if "radio_url" in obj:
        if user_id in [participant.user_id for participant in await app_dj_calls.get_participants(dot_ch_id)]:
            await change_stream(obj['radio_url'], who_called=message.from_user.id)
            return "▶️"
        return "🤷‍♂️Сначала зайди в радио!"
    buttons = []
    text = ""
    if not obj.get("hide_name", 0):
        text += f'**{obj["name"]}**'
    if "description" in obj:
        text += f'\n{obj["description"]}'
    if "custom" in obj:
        match obj["custom"]:
            case "bashkir_haiku":
                text += f'\n{await get_bashkir_haiku()}'
    if "children" in obj:
        children = obj["children"]
        for child in children:
            if children[child].get("beta_access", 0):
                if user_id not in beta_testers:
                    continue
            kwargs = {"text": children[child]['name']}
            if "url" in children[child]:
                kwargs["url"] = children[child]['url']
            else:
                kwargs["callback_data"] = f"id={child}"
            buttons.append([InlineKeyboardButton(**kwargs)])
    if obj.get("refresh", 0):
        buttons.append(
            [
                InlineKeyboardButton(
                    text="🔄",
                    callback_data=f"refresh=1=id={path_hash}"
                )
            ]
        )
    share_button = InlineKeyboardButton(
        text="🔗",
        switch_inline_query=obj["share"]
    )
    if "parent" in obj:
        parent = obj["parent"]
        buttons.append(
            [
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"id={parent}"
                ),
                share_button
            ]
        )
    else:
        buttons.append(
            [
                share_button
            ]
        )
    reply_markup = InlineKeyboardMarkup(buttons)
    await app_robot.edit_message_text(
        message.chat.id,
        message.id,
        text=text,
        reply_markup=reply_markup
    )
    return None


@app_robot.on_message(pyrogram.filters.command(["start"]) & pyrogram.filters.private)
async def start_handler(client, message):
    user_id = message.from_user.id
    new_message = await app_robot.send_message(
        user_id,
        text="Загрузка"
    )
    deep_link = ""
    if len(message.command) >= 2:
        deep_link = message.command[1]
    return await open_common_hashdict(deep_link, new_message, user_id)


@app_robot.on_callback_query()
async def answer_common_hashdict(client, callback_query, **kwargs):
    answer = await open_common_hashdict(callback_query.data, callback_query.message, callback_query.from_user.id)
    if answer:
        await callback_query.answer(answer)


@app_robot.on_message(pyrogram.filters.private & pyrogram.filters.photo)
async def answer_wanted_search(client, message):
    await asyncio.sleep(1+random())
    await app_robot.send_chat_action(message.chat.id, ChatAction.TYPING)
    await asyncio.sleep(2+6*random())
    await app_robot.send_message(message.chat.id, wanted_not_found)


@app_robot.on_message(pyrogram.filters.private & (pyrogram.filters.location | pyrogram.filters.venue))
async def answer_location(client, message):
    match message.media:
        case pyrogram.enums.MessageMediaType.VENUE:
            location = message.venue.location
        case pyrogram.enums.MessageMediaType.LOCATION:
            location = message.location
        case _:
            raise ValueError("Unknown media type")
    await app_robot.send_message(message.chat.id, await get_weather(location))


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


@app_robot.on_message(pyrogram.filters.command(["test"]) & pyrogram.filters.private)
@admin_only
async def test_handler(client, message):
    # reply_markup = pyrogram.types.ReplyKeyboardMarkup(
    #     [
    #         [
    #             pyrogram.types.KeyboardButton("📍", request_location=True),
    #         ],
    #     ],
    #     resize_keyboard=True,
    #     one_time_keyboard=True,
    #     placeholder="🖖🏻🖖🏻🖖🏻🖖🏻🖖🏻"
    # )
    # reply_markup = pyrogram.types.ForceReply(
    #     selective=True,
    #     placeholder="🖖🏻🖖🏻🖖🏻🖖🏻🖖🏻"
    # )
    # await message.reply_text(
    #     "test",
    #     reply_markup=reply_markup
    # )
    pass


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
