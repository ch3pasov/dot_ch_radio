import pyrogram
from pytgcalls import PyTgCalls
from pytgcalls.mtproto.pyrogram_client import PyrogramClient
from pytgcalls import idle
from pytgcalls.types import (
    AudioPiped,
    # AudioVideoPiped,
    AudioParameters,
    AudioQuality,
    # VideoParameters,
    # VideoQuality,
)
import secret

api_id = secret.api_id
api_hash = secret.api_hash

channel_id = secret.channel_id
chat_id = secret.chat_id
join_channel_id = secret.join_channel_id
join_access_hash = secret.join_access_hash

app = pyrogram.Client("my_account", api_id, api_hash)
calls_app_simple = PyTgCalls(app)
calls_app_difficult = PyrogramClient(1, app)
calls_app_simple.start()

# # 1291274978
# # {
# #     "_": "types.InputPeerChannel",
# #     "channel_id": 1291274978,
# #     "access_hash": 1446172399040448336
# # }
# print(app.resolve_peer(1291274978))

calls_app_simple.join_group_call(
    channel_id,
    join_as=pyrogram.raw.types.InputPeerChannel(channel_id=join_channel_id, access_hash=join_access_hash)
)

calls_app_simple.change_stream(
    channel_id,
    AudioPiped(
        'audio.mp3',
        audio_parameters=AudioParameters.from_quality(AudioQuality.HIGH),
    )
)

print(1)


@app.on_raw_update()
async def raw(client, update, users, chats):
    # print(type(update))
    # print(dir(update))
    if type(update) is pyrogram.raw.types.update_group_call_participants.UpdateGroupCallParticipants:
        for participant in update.participants:
            # print(participant)
            match type(participant.peer):
                case pyrogram.raw.types.PeerUser:
                    participant_type = 'user'
                    participant_id = participant.peer.user_id
                case pyrogram.raw.types.PeerChat:
                    participant_type = 'chat'
                    participant_id = participant.peer.chat_id
                case pyrogram.raw.types.PeerChannel:
                    participant_type = 'channel'
                    participant_id = participant.peer.channel_id
                    print(update)
            if participant.left:
                print(f'{participant_type} {participant_id} left')
            if participant.just_joined:
                print(f'{participant_type} {participant_id} just joined')
                if participant_type == 'user':
                    peer = await app.resolve_peer(participant_id)
                    await calls_app_difficult.set_call_status(
                        channel_id,
                        participant=peer,
                        muted_status=False,
                        paused_status=None,
                        stopped_status=None
                    )
            if participant.raise_hand_rating:
                print(f'{participant_type} {participant_id} raise hand with rating {participant.raise_hand_rating}')


try:
    idle()
except KeyboardInterrupt:
    print('Exiting...')
finally:
    try:
        calls_app_simple.leave_group_call(
            channel_id
        )
    except KeyError:
        # странная ошибка из-за того, что я залогинился через канал
        pass
