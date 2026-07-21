from config.debug import disable_radio
from get_hashdict import common_hashdict
from programs.radio_status import RadioPlaybackStatus


_playback_status = RadioPlaybackStatus(common_hashdict)


def current_station_name() -> str | None:
    return _playback_status.current_station_name


if not disable_radio:
    import asyncio
    from pathlib import Path
    from typing import Literal, Optional, Union

    from config.tg_ids import (
        admins,
        dot_ch_id,
        dot_ch_radio_id,
        dot_ch_radio_access_hash,
    )
    from content.content import default_url

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

    from telethon import events
    from telethon.tl.types import InputPeerChannel, UpdateGroupCallParticipants, PeerUser
    from telethon.tl.functions.phone import EditGroupCallParticipantRequest

    import pytgcalls
    from pytgcalls import filters as pytgcalls_filters

    app_dj_calls = pytgcalls.PyTgCalls(app_dj)
    # app_dj_calls.start() — переносим в main.py (нужен запущенный event loop)

    async def start_calls():
        await app_dj_calls.start()

    _prev_lockout = False
    _last_night_target_key: str | None = None
    _last_input_group_call = None
    _stream_end_recovery_lock = asyncio.Lock()
    _last_stream_end_recovery_at = 0.0
    _ADMINS = frozenset(admins)

    # Идентичность, под которой dj-аккаунт заходит в войс (вещает «от канала-радио»).
    _RADIO_JOIN_AS = InputPeerChannel(
        channel_id=dot_ch_radio_id,
        access_hash=dot_ch_radio_access_hash,
    )

    def _is_private(event) -> bool:
        return bool(getattr(event, "is_private", False))

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
            if not media.startswith(("http://", "https://")):
                raise ValueError("radio URL must use HTTP or HTTPS")
            print(f"{who_called} calls change_stream to {media}")
            stream_arg = media
        await app_dj_calls.play(
            dot_ch_id,
            pytgcalls.types.MediaStream(
                str(stream_arg),
                audio_parameters=pytgcalls.types.AudioQuality.HIGH,
                ffmpeg_parameters=ffmpeg_parameters,
            ),
            config=pytgcalls.types.GroupCallConfig(
                join_as=_RADIO_JOIN_AS,
            ),
        )
        _playback_status.record_stream(media)

    async def get_participants(chat_id):
        return await app_dj_calls.get_participants(chat_id)

    async def leave_group_call(chat_id):
        await app_dj_calls.leave_call(chat_id)

    @app_robot.on(events.NewMessage(pattern=r'^/pause(?:\s|$)', func=_is_private))
    @admin_only
    async def pause_handler(event):
        print("admin calls pause")
        result = await app_dj_calls.pause_stream(dot_ch_id)
        await app_robot.send_message(event.sender_id, str(result))

    @app_robot.on(events.NewMessage(pattern=r'^/resume(?:\s|$)', func=_is_private))
    @admin_only
    async def resume_handler(event):
        print("admin calls resume")
        result = await app_dj_calls.resume_stream(dot_ch_id)
        await app_robot.send_message(event.sender_id, str(result))

    @app_robot.on(events.NewMessage(pattern=r'^/time(?:\s|$)', func=_is_private))
    @admin_only
    async def time_handler(event):
        print("admin calls time")
        result = await app_dj_calls.played_time(dot_ch_id)
        await app_robot.send_message(event.sender_id, str(result))

    @app_robot.on(events.NewMessage(pattern=r'^/change_stream\s+(\S+)', func=_is_private))
    @admin_only
    async def change_stream_handler(event):
        url = event.pattern_match.group(1)
        await change_stream(
            url,
            who_called="admin_command"
        )
        await app_robot.send_message(
            event.sender_id,
            "True?!"
        )

    async def _handle_stream_end():
        global _last_stream_end_recovery_at
        async with _stream_end_recovery_lock:
            now = asyncio.get_running_loop().time()
            if now - _last_stream_end_recovery_at < 2.0:
                print("duplicate stream_end ignored")
                return
            _last_stream_end_recovery_at = now
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

    async def _edit_participant_muted(call, participant_id, muted: bool):
        peer = await app_dj.get_input_entity(participant_id)
        await app_dj(
            EditGroupCallParticipantRequest(
                call=call,
                participant=peer,
                muted=muted,
            )
        )

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
            try:
                await _edit_participant_muted(call, p.user_id, True)
            except Exception as e:
                print(f"night mute sweep failed: {type(e).__name__}")

    async def _unmute_sweep_after_night():
        global _last_input_group_call
        call = _last_input_group_call
        if not call:
            return
        parts = await app_dj_calls.get_participants(dot_ch_id)
        if not parts:
            return
        for p in parts:
            try:
                await _edit_participant_muted(call, p.user_id, False)
            except Exception as e:
                print(f"day unmute sweep failed: {type(e).__name__}")

    # главный обработчик событий в войсчате
    @app_dj.on(events.Raw(types=UpdateGroupCallParticipants))
    async def raw(update):
        global _last_input_group_call
        call = update.call
        _last_input_group_call = call
        for participant in update.participants:
            if isinstance(participant.peer, PeerUser):
                participant_id = participant.peer.user_id
            else:
                continue

            if participant.left:
                print("participant left")
                continue

            if is_night_radio_lockout_utc():
                if participant_id in _ADMINS:
                    # Только при входе: иначе при muted=True (слушатель) каждый
                    # UpdateGroupCallParticipants даёт лавину EditGroupCallParticipant и 400 PARTICIPANT_JOIN_MISSING.
                    if participant.just_joined and participant.muted:
                        print("admin participant unmute on join")
                        try:
                            await _edit_participant_muted(call, participant_id, False)
                        except Exception as e:
                            print(f"night admin unmute failed: {type(e).__name__}")
                elif participant.just_joined:
                    print("participant night mute on join")
                    try:
                        await _edit_participant_muted(call, participant_id, True)
                    except Exception as e:
                        print(f"night mute failed: {type(e).__name__}")
            elif participant.just_joined:
                print("participant joined")
                try:
                    await _edit_participant_muted(call, participant_id, False)
                except Exception as e:
                    print(f"day unmute on join failed: {type(e).__name__}")
            if participant.raise_hand_rating:
                print("participant raised hand")
else:
    async def start_calls():
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
