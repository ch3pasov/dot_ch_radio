import pyrogram
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
from secret import secret
import logging
import sys
import re

formatter = logging.Formatter('%(asctime)s %(levelname)s [%(filename)s:%(lineno)s] %(message)s')
handler_fancy_stdout = logging.StreamHandler(sys.stdout)
handler_logger = logging.FileHandler("logs/common.log", mode='a')
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

api_id = secret.api_id
api_hash = secret.api_hash

dot_ch_id = secret.dot_ch_id
dot_ch_chat_id = secret.dot_ch_chat_id
dot_ch_radio_id = secret.dot_ch_radio_id
dot_ch_radio_access_hash = secret.dot_ch_radio_access_hash

print('login in robot account')
app_robot = pyrogram.Client("secret/robot_account", api_id, api_hash)
app_robot.start()

print('login in dj account')
app_dj = pyrogram.Client("secret/dj_account", api_id, api_hash)
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


remote = asyncio.get_event_loop().run_until_complete(get_youtube_stream("https://youtu.be/miZHa7ZC6Z0"))


app_dj_calls.change_stream(
    dot_ch_id,
    AudioPiped(
        remote,
        audio_parameters=AudioParameters.from_quality(AudioQuality.HIGH),
    )
)


@app_robot.on_message(pyrogram.filters.command(["pause"]) & pyrogram.filters.private)
async def pause_handler(client, message):
    print(f"{message.from_user.id} calls pause")
    await app_robot.send_message(message.from_user.id, await app_dj_calls.pause_stream(dot_ch_id))


@app_robot.on_message(pyrogram.filters.command(["resume"]) & pyrogram.filters.private)
async def resume_handler(client, message):
    print(f"{message.from_user.id} calls resume")
    await app_robot.send_message(message.from_user.id, await app_dj_calls.resume_stream(dot_ch_id))


@app_robot.on_message(pyrogram.filters.command(["time"]) & pyrogram.filters.private)
async def time_handler(client, message):
    print(f"{message.from_user.id} calls time")
    await app_robot.send_message(message.from_user.id, await app_dj_calls.played_time(dot_ch_id))


async def change_stream(url, who_called=''):
    print(f"{who_called} calls change_stream to {url}")
    if re.search(r'http(?:s?):\/\/(?:www\.)?youtu(?:be\.com\/watch\?v=|\.be\/)([\w\-\_]*)(&(amp;)?‌​[\w\?‌​=]*)?', url):
        new_stream = asyncio.get_event_loop().run_until_complete(get_youtube_stream(url=url))
        print(new_stream)
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


@app_robot.on_message(pyrogram.filters.command(["change_stream"]) & pyrogram.filters.private)
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


radio_stations = {
    "lofi-girl": "https://www.youtube.com/watch?v=jfKfPfyJRdk",
    "sa-bounce-fm": "https://play.smolyakov.dev/stream/sa/bounce-fm",
    "sa-csr": "https://play.smolyakov.dev/stream/sa/csr",
    "sa-k-dst": "https://play.smolyakov.dev/stream/sa/k-dst",
    "sa-k-jah": "https://play.smolyakov.dev/stream/sa/k-jah",
    "sa-k-rose": "https://play.smolyakov.dev/stream/sa/k-rose",
    "sa-master-sounds": "https://play.smolyakov.dev/stream/sa/master-sounds",
    "sa-playback-fm": "https://play.smolyakov.dev/stream/sa/playback-fm",
    "sa-radio-los-santos": "https://play.smolyakov.dev/stream/sa/radio-los-santos",
    "sa-radio-x": "https://play.smolyakov.dev/stream/sa/radio-x",
    "sa-sfur": "https://play.smolyakov.dev/stream/sa/sfur",
    "sa-wctr": "https://play.smolyakov.dev/stream/sa/wctr",
    "vc-emotion": "https://play.smolyakov.dev/stream/vc/emotion",
    "vc-espant": "https://play.smolyakov.dev/stream/vc/espant",
    "vc-fever": "https://play.smolyakov.dev/stream/vc/fever",
    "vc-flash": "https://play.smolyakov.dev/stream/vc/flash",
    "vc-kchat": "https://play.smolyakov.dev/stream/vc/kchat",
    "vc-vcpr": "https://play.smolyakov.dev/stream/vc/vcpr",
    "vc-vrock": "https://play.smolyakov.dev/stream/vc/vrock",
    "vc-wave": "https://play.smolyakov.dev/stream/vc/wave",
    "vc-wild": "https://play.smolyakov.dev/stream/vc/wild",
    "3-head": "https://play.smolyakov.dev/stream/3/head",
    "3-class": "https://play.smolyakov.dev/stream/3/class",
    "3-kjah": "https://play.smolyakov.dev/stream/3/kjah",
    "3-rise": "https://play.smolyakov.dev/stream/3/rise",
    "3-lips": "https://play.smolyakov.dev/stream/3/lips",
    "3-game": "https://play.smolyakov.dev/stream/3/game",
    "3-msx": "https://play.smolyakov.dev/stream/3/msx",
    "3-flash": "https://play.smolyakov.dev/stream/3/flash",
    "3-chat": "https://play.smolyakov.dev/stream/3/chat",
    "evangelie-sinod": "https://radio.azbyka.ru/evangelie",
    "evangelie-csya": "https://radio.azbyka.ru/chitaem-evangelie-csya",
    "evangelie-sinod-muz": "https://radio.azbyka.ru/chitaem-evangelie-sinod-muz",
    "psaltir-csya": "https://radio.azbyka.ru/psaltir",
    "psaltir-rus": "https://radio.azbyka.ru/psaltir-rus",
    "psaltir-rus-muz": "https://radio.azbyka.ru/psaltir-rus-muz",
    "dorbrotolubie": "https://radio.azbyka.ru/dobrotolubie",
    "lives": "https://radio.azbyka.ru/lives",
    "azbyka-molitvy": "https://radio.azbyka.ru/azbyka-molitvy",
    "grad-petrov": "https://grad-petrov.ru:8094/aac",
    "radonezh": "https://proxy.radio.azbyka.ru/radonezh",
    "vera": "https://radiovera.hostingradio.ru:8007/radiovera_128",
    "blago": "https://live.radioblago.ru/live-1.mp3",
    "ancient-faith-music": "https://ancientfaith.streamguys1.com/music",
    "ancient-faith-talk": "https://ancientfaith.streamguys1.com/talk",
    "gkpc": "https://proxy.radio.azbyka.ru/gkpc"
}


@app_robot.on_message(pyrogram.filters.command(["radio"]) & pyrogram.filters.private)
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
    remote = await get_youtube_stream(radio_stations['lofi-girl'])
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
    idle()
except KeyboardInterrupt:
    print('Exiting...')
finally:
    try:
        app_dj_calls.leave_group_call(
            dot_ch_id
        )
        pass
    except KeyError:
        # странная ошибка из-за того, что я залогинился через канал
        pass
