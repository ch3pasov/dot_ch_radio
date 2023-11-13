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


# USE THIS IF YOU WANT SYNC WAY
def get_youtube_stream(url='https://www.youtube.com/watch?v=jfKfPfyJRdk'):
    # USE THIS IF YOU WANT ASYNC WAY
    async def run_async(url=url):
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
    return asyncio.get_event_loop().run_until_complete(run_async())


app_dj_calls.change_stream(
    dot_ch_id,
    AudioPiped(
        get_youtube_stream(),
        audio_parameters=AudioParameters.from_quality(AudioQuality.HIGH),
    )
)


@app_robot.on_message(pyrogram.filters.command(["pause"]) & pyrogram.filters.private)
async def pause_handler(client, message):
    await app_robot.send_message(message.from_user.id, await app_dj_calls.pause_stream(dot_ch_id))


@app_robot.on_message(pyrogram.filters.command(["resume"]) & pyrogram.filters.private)
async def resume_handler(client, message):
    await app_robot.send_message(message.from_user.id, await app_dj_calls.resume_stream(dot_ch_id))


@app_robot.on_message(pyrogram.filters.command(["time"]) & pyrogram.filters.private)
async def time_handler(client, message):
    await app_robot.send_message(message.from_user.id, await app_dj_calls.played_time(dot_ch_id))


@app_robot.on_message(pyrogram.filters.command(["change_stream"]) & pyrogram.filters.private)
async def change_stream_handler(client, message):
    await app_dj_calls.change_stream(
        dot_ch_id,
        AudioPiped(
            get_youtube_stream(url=message.command[1]),
            audio_parameters=AudioParameters.from_quality(AudioQuality.HIGH),
        )
    )
    await app_robot.send_message(
        message.from_user.id,
        "True?!"
    )


# сюда буду писать кастомную вещь
@app_robot.on_message(pyrogram.filters.command(["please"]) & pyrogram.filters.private)
async def please_handler(client, message):
    print(asyncio.get_event_loop())


@app_dj_calls.on_stream_end()
async def handler(client: PyTgCalls, update: Update):
    print(update)
    await app_dj_calls.change_stream(
        dot_ch_id,
        AudioPiped(
            get_youtube_stream(url='https://www.youtube.com/watch?v=jfKfPfyJRdk'),
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
