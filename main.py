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
    # Update,
)
import asyncio
# from random import randint
import secret
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

app = pyrogram.Client("secret/my_account", api_id, api_hash)

app_calls = PyTgCalls(app)
app_calls.start()
app_calls.join_group_call(
    dot_ch_id,
    join_as=pyrogram.raw.types.InputPeerChannel(channel_id=dot_ch_radio_id, access_hash=dot_ch_radio_access_hash)
)

print(1)


# USE THIS IF YOU WANT SYNC WAY
def get_youtube_stream():
    # USE THIS IF YOU WANT ASYNC WAY
    async def run_async():
        proc = await asyncio.create_subprocess_exec(
            'yt-dlp',
            '-g',
            '-f',
            # 'best[height<=?720][width<=?1280]',
            'ba',  # best audio
            'https://www.youtube.com/live/jfKfPfyJRdk?si=gSkWIK09MCq5WuT1',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return stdout.decode().split('\n')[0]
    return asyncio.get_event_loop().run_until_complete(run_async())


remote = get_youtube_stream()

app_calls.change_stream(
    dot_ch_id,
    AudioPiped(
        remote,
        audio_parameters=AudioParameters.from_quality(AudioQuality.HIGH),
    )
)


# @app_calls.on_stream_end()
# async def handler(client: PyTgCalls, update: Update):
#     print(update)
#     await app_calls.change_stream(
#         dot_ch_id,
#         AudioPiped(
#             'audio_02.mp3',
#             audio_parameters=AudioParameters.from_quality(AudioQuality.HIGH),
#         )
#     )


# главный обработчик событий в войсчате
@app.on_raw_update()
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
                peer = await app.resolve_peer(participant_id)
                await app.invoke(
                    pyrogram.raw.functions.phone.EditGroupCallParticipant(
                        call=call,
                        participant=peer,
                        muted=False
                    )
                )
            if participant.raise_hand_rating:
                print(f'{participant_type} {participant_id} raise hand with rating {participant.raise_hand_rating}')
                # peer = await app.resolve_peer(participant_id)
                # await asyncio.sleep(5)
                # if randint(0, 1):
                #     await app.invoke(
                #         pyrogram.raw.functions.phone.EditGroupCallParticipant(
                #             call=call,
                #             participant=peer,
                #             raise_hand=False
                #         )
                #     )
                # else:
                #     await app.invoke(
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
        app_calls.leave_group_call(
            dot_ch_id
        )
        pass
    except KeyError:
        # странная ошибка из-за того, что я залогинился через канал
        pass
