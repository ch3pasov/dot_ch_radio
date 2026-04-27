from volume.config.debug import disable_radio

if not disable_radio:
    import asyncio
    from pathlib import Path
    from typing import Literal, Optional, Union

    from volume.config.tg_ids import (
        admins,
        dot_ch_id,
        dot_ch_radio_id,
        dot_ch_radio_access_hash,
    )
    from volume.content import default_url

    from decorators import admin_only

    from global_vars import app_robot, app_dj, print

    from programs.night_schedule import (
        NIGHT_LOOP_FIRST_CLIP_SEC,
        is_night_radio_lockout_utc,
        is_night_loop_media_path,
        night_loop_random_first_clip_ffmpeg_parameters_for_path,
        night_loop_has_video_stream,
        scheduled_stream_target,
        stream_after_end_target,
    )

    import pyrogram
    import pytgcalls
    from pytgcalls import filters as pytgcalls_filters
    app_dj_calls = pytgcalls.PyTgCalls(app_dj)
    app_dj_calls.start()

    _prev_lockout = False
    _last_night_target_key: str | None = None
    _last_input_group_call = None
    _ADMINS = frozenset(admins)

    def _media_key(media: Union[str, Path]) -> str:
        if isinstance(media, Path):
            return f"path:{media.resolve()}"
        return f"url:{media}"

    def _night_loop_segment_for_fresh_play(
        target: Union[str, Path], who: str
    ) -> Optional[Literal["random_first"]]:
        """Первый заход в ночной луп при старте/смене источника планировщиком — случайный кусок."""
        if who not in ("startup", "night_scheduler"):
            return None
        if isinstance(target, Path) and is_night_loop_media_path(target.resolve()):
            return "random_first"
        return None

    async def change_stream(
        media: Union[str, Path],
        who_called: str = "",
        *,
        night_loop_segment: Optional[Literal["random_first", "full"]] = None,
    ):
        ffmpeg_parameters = None
        if isinstance(media, Path):
            src = media.resolve()
            if not src.is_file():
                raise FileNotFoundError(f"media file missing: {src}")
            print(f"{who_called} calls change_stream to file {src}")
            stream_arg: Union[str, Path] = src
            if is_night_loop_media_path(src):
                seg = night_loop_segment or "full"
                if seg == "random_first":
                    clip_params = night_loop_random_first_clip_ffmpeg_parameters_for_path(src)
                    if clip_params:
                        ffmpeg_parameters, start_sec = clip_params
                        print(
                            f"{who_called} night_loop: первый фрагмент — с {start_sec:.2f}s, "
                            f"{NIGHT_LOOP_FIRST_CLIP_SEC}s (потом полный ролик с начала)"
                        )
                    else:
                        print(
                            f"{who_called} night_loop: случайный старт не применён (короткий файл?) — "
                            "сразу полный ролик с начала"
                        )
                else:
                    print(f"{who_called} night_loop: полный ролик с начала (луп до stream_end)")
                if not night_loop_has_video_stream(src):
                    print(f"{who_called} warning: в night_loop нет видеодорожки — в стриме не будет картинки")
        else:
            assert media.startswith('http://') or media.startswith('https://'), 'url must be http[s]?://...'
            print(f"{who_called} calls change_stream to {media}")
            stream_arg = media
        await app_dj_calls.play(
            dot_ch_id,
            pytgcalls.types.MediaStream(
                stream_arg,
                pytgcalls.types.AudioQuality.HIGH,
                ffmpeg_parameters=ffmpeg_parameters,
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

    async def _handle_stream_end():
        try:
            nxt = stream_after_end_target(default_url)
            seg: Optional[Literal["random_first", "full"]] = None
            if isinstance(nxt, Path) and is_night_loop_media_path(nxt.resolve()):
                seg = "full"
            await change_stream(nxt, who_called="stream_end", night_loop_segment=seg)
        except Exception as e:
            print(f"stream_end handler: {e}")

    @app_dj_calls.on_update(pytgcalls_filters.stream_end())
    async def handler(client: pytgcalls.PyTgCalls, update: pytgcalls.types.Update):
        print("stream ended, recovering stream")
        await _handle_stream_end()

    async def _night_scheduler_loop():
        global _prev_lockout, _last_night_target_key
        while True:
            now_lock = is_night_radio_lockout_utc()
            entered_night = now_lock and not _prev_lockout
            left_night = (not now_lock) and _prev_lockout
            try:
                if now_lock:
                    target = scheduled_stream_target(default_url)
                    key = _media_key(target)
                    if key != _last_night_target_key:
                        await change_stream(
                            target,
                            who_called="night_scheduler",
                            night_loop_segment=_night_loop_segment_for_fresh_play(
                                target, "night_scheduler"
                            ),
                        )
                        _last_night_target_key = key
                    if entered_night:
                        await _mute_sweep_non_admins()
                else:
                    if _prev_lockout:
                        await change_stream(default_url, who_called='night_end')
                        _last_night_target_key = None
                    if left_night:
                        await _unmute_sweep_after_night()
            except Exception as e:
                print(f"night_scheduler: {e}")
            _prev_lockout = now_lock
            await asyncio.sleep(15)

    async def ensure_startup_stream():
        global _last_night_target_key
        target = scheduled_stream_target(default_url)
        await change_stream(
            target,
            who_called="startup",
            night_loop_segment=_night_loop_segment_for_fresh_play(target, "startup"),
        )
        # Иначе первый тик _night_scheduler_loop сразу снова вызовет change_stream с тем же key (первый кусок дважды).
        _last_night_target_key = _media_key(target)
        asyncio.get_running_loop().create_task(_night_scheduler_loop())

    async def _mute_sweep_non_admins():
        global _last_input_group_call
        call = _last_input_group_call
        if not call:
            print("night mute sweep: нет call в кэше, пропуск")
            return
        parts = await app_dj_calls.get_participants(dot_ch_id)
        if not parts:
            return
        for p in parts:
            if p.user_id in _ADMINS:
                continue
            peer = await app_dj.resolve_peer(p.user_id)
            try:
                await app_dj.invoke(
                    pyrogram.raw.functions.phone.EditGroupCallParticipant(
                        call=call,
                        participant=peer,
                        muted=True,
                    )
                )
            except Exception as e:
                print(f"night mute sweep user {p.user_id}: {e}")

    async def _unmute_sweep_after_night():
        global _last_input_group_call
        call = _last_input_group_call
        if not call:
            return
        parts = await app_dj_calls.get_participants(dot_ch_id)
        if not parts:
            return
        for p in parts:
            peer = await app_dj.resolve_peer(p.user_id)
            try:
                await app_dj.invoke(
                    pyrogram.raw.functions.phone.EditGroupCallParticipant(
                        call=call,
                        participant=peer,
                        muted=False,
                    )
                )
            except Exception as e:
                print(f"day unmute sweep user {p.user_id}: {e}")

    # главный обработчик событий в войсчате
    @app_dj.on_raw_update()
    async def raw(client, update, users, chats):
        global _last_input_group_call
        if type(update) is pyrogram.raw.types.update_group_call_participants.UpdateGroupCallParticipants:
            call = update.call
            _last_input_group_call = call
            for participant in update.participants:
                match type(participant.peer):
                    case pyrogram.raw.types.PeerUser:
                        participant_id = participant.peer.user_id
                    case _:
                        continue

                if participant.left:
                    print(f"user {participant_id} left")
                    continue

                peer = await app_dj.resolve_peer(participant_id)

                if is_night_radio_lockout_utc():
                    if participant_id in _ADMINS:
                        # Только при входе: иначе при muted=True (слушатель) каждый
                        # UpdateGroupCallParticipants даёт лавину EditGroupCallParticipant и 400 PARTICIPANT_JOIN_MISSING.
                        if participant.just_joined and participant.muted:
                            print(f"user {participant_id} admin, unmute on join")
                            try:
                                await app_dj.invoke(
                                    pyrogram.raw.functions.phone.EditGroupCallParticipant(
                                        call=call,
                                        participant=peer,
                                        muted=False,
                                    )
                                )
                            except Exception as e:
                                print(f"night admin unmute user {participant_id}: {e}")
                    elif participant.just_joined:
                        print(f"user {participant_id} night mute on join")
                        try:
                            await app_dj.invoke(
                                pyrogram.raw.functions.phone.EditGroupCallParticipant(
                                    call=call,
                                    participant=peer,
                                    muted=True,
                                )
                            )
                        except Exception as e:
                            print(f"night mute user {participant_id}: {e}")
                elif participant.just_joined:
                    print(f"user {participant_id} just joined")
                    try:
                        await app_dj.invoke(
                            pyrogram.raw.functions.phone.EditGroupCallParticipant(
                                call=call,
                                participant=peer,
                                muted=False,
                            )
                        )
                    except Exception as e:
                        print(f"day unmute on join user {participant_id}: {e}")
                if participant.raise_hand_rating:
                    print(f"user {participant_id} raise hand with rating {participant.raise_hand_rating}")
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

    async def change_stream(url: str, who_called="", *, night_loop_segment=None):
        print("Radio is disabled")
        return None

    async def ensure_startup_stream():
        print("Radio is disabled")
        return None

    async def get_participants(chat_id):
        print("Radio is disabled")
        return []

    async def leave_group_call(chat_id):
        print("Radio is disabled")
        return None
