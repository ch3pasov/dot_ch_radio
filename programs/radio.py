from volume.config.debug import disable_radio

if not disable_radio:
    from volume.config.tg_ids import dot_ch_id, dot_ch_radio_id, dot_ch_radio_access_hash
    from volume.content import default_url

    from decorators import admin_only

    from global_vars import app_robot, app_dj, print

    # import asyncio
    import pyrogram
    import pytgcalls
    from pytgcalls import filters as pytgcalls_filters
    app_dj_calls = pytgcalls.PyTgCalls(app_dj)
    app_dj_calls.start()

    async def change_stream(url: str, who_called=''):
        assert url.startswith('http://') or url.startswith('https://'), 'url must be http[s]?://...'
        print(f"{who_called} calls change_stream to {url}")
        await app_dj_calls.play(
            dot_ch_id,
            pytgcalls.types.MediaStream(
                url,
                pytgcalls.types.AudioQuality.HIGH,
            ),
            pytgcalls.types.GroupCallConfig(
                join_as=pyrogram.raw.types.InputPeerChannel(
                    channel_id=dot_ch_radio_id,
                    access_hash=dot_ch_radio_access_hash
                )
            )
        )

    async def get_participants(chat_id):
        return await app_dj_calls.get_participants(chat_id)

    async def leave_group_call(chat_id):
        await app_dj_calls.leave_call(chat_id)

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

    @app_dj_calls.on_update(pytgcalls_filters.stream_end)
    async def handler(client: pytgcalls.PyTgCalls, update: pytgcalls.types.Update):
        print("stream ended, changing to default")
        await change_stream(
            default_url,
            "ending of last stream"
        )

    # главный обработчик событий в войсчате
    @app_dj.on_raw_update()
    async def raw(client, update, users, chats):
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
