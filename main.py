from pytgcalls import PyTgCalls
from pytgcalls import idle
from pytgcalls.types import (
    # AudioPiped,
    AudioVideoPiped,
    AudioParameters,
    AudioQuality,
    VideoParameters,
    VideoQuality,
)
import pyrogram
import secret

api_id = secret.api_id
api_hash = secret.api_hash

channel_id = secret.channel_id
chat_id = secret.chat_id

app = pyrogram.Client("my_account", api_id, api_hash)
calls_app = PyTgCalls(app)
calls_app.start()

app.send_message(chat_id, 'Playing...')

calls_app.join_group_call(
    channel_id
)

calls_app.change_stream(
    channel_id,
    AudioVideoPiped(
        'video.webm',
        audio_parameters=AudioParameters.from_quality(AudioQuality.LOW),
        video_parameters=VideoParameters.from_quality(VideoQuality.SD_360p)
    )
)

# calls_app.change_stream(
#     channel_id,
#     AudioPiped(
#         'audio.mp3',
#         audio_parameters=AudioParameters.from_quality(AudioQuality.HIGH),
#     )
# )

idle()
