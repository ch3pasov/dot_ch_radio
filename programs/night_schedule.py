"""Ночной режим радио: полуинтервал [18:15:00Z, 03:00:00Z) по UTC — night_loop.mp4, без смены станций из бота."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Полуинтервал ночного эфира по UTC: [start, end) = [18:15:00Z, 03:00:00Z)
NIGHT_STREAM_START_HOUR = 18
NIGHT_STREAM_START_MINUTE = 15
NIGHT_STREAM_END_HOUR_EXCLUSIVE = 3  # 03:00:00Z уже дневной эфир

# Текст для callback_query.answer (до ~200 символов)
NIGHT_RADIO_SWITCH_BLOCKED = (
    "🌙 Сейчас ночной эфир [18:15, 03:00) UTC. "
    "Обычные станции недоступны — слушайте ночной стрим в канале."
)

# Первый фрагмент ночного лупа: сколько секунд с конца файла (FFmpeg -sseof), затем — полный ролик с начала.
NIGHT_LOOP_BOOTSTRAP_TAIL_SEC = 8


def _utc_now(now: datetime | None) -> datetime:
    t = now or datetime.now(timezone.utc)
    if t.tzinfo is None:
        return t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc)


def is_night_radio_lockout_utc(now: datetime | None = None) -> bool:
    """[18:15:00Z, 03:00:00Z) по UTC — нельзя переключать радиостанции из бота."""
    t = _utc_now(now)
    h, m = t.hour, t.minute
    if h < NIGHT_STREAM_END_HOUR_EXCLUSIVE:
        return True
    if h > NIGHT_STREAM_START_HOUR:
        return True
    if h == NIGHT_STREAM_START_HOUR:
        return m >= NIGHT_STREAM_START_MINUTE
    return False


def is_night_loop_video_window_utc(now: datetime | None = None) -> bool:
    """
    Период проигрывания night_loop.mp4 внутри lockout.
    Последняя минута до конца полуинтервала (02:59 UTC при end=03:00) — обычный default_url, чтобы проверить смену источника.
    """
    if not is_night_radio_lockout_utc(now):
        return False
    t = _utc_now(now)
    if t.hour == NIGHT_STREAM_END_HOUR_EXCLUSIVE - 1 and t.minute == 59:
        return False
    return True


def night_loop_file_path() -> Path:
    """Ночное видео: только volume/config/night_loop.mp4."""
    volume = Path(__file__).resolve().parent.parent / "volume"
    return volume / "config" / "night_loop.mp4"


def night_loop_bootstrap_tail_ffmpeg_parameters() -> str:
    """Только первый заход: последние N секунд файла (до -i). См. pytgcalls.ffmpeg.build_command."""
    sec = NIGHT_LOOP_BOOTSTRAP_TAIL_SEC
    return f"--base ---start -sseof -{sec}"


def night_loop_media_duration_sec(path: Path) -> float | None:
    """Длительность контейнера по ffprobe; None если не удалось (битый/пустой файл)."""
    try:
        r = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if r.returncode != 0:
            return None
        data = json.loads(r.stdout or "{}")
        raw = (data.get("format") or {}).get("duration")
        if raw is None:
            return None
        return float(raw)
    except (json.JSONDecodeError, ValueError, TypeError, subprocess.TimeoutExpired, OSError):
        return None


def night_loop_has_video_stream(path: Path) -> bool:
    try:
        r = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if r.returncode != 0:
            return False
        data = json.loads(r.stdout or "{}")
        streams = data.get("streams") or []
        return any(s.get("codec_type") == "video" for s in streams)
    except (json.JSONDecodeError, subprocess.TimeoutExpired, OSError):
        return False


def night_loop_bootstrap_tail_ffmpeg_parameters_for_path(path: Path) -> str | None:
    """-sseof для хвоста только если файл длиннее хвоста; иначе сразу полный луп с начала."""
    if not path.is_file():
        return None
    dur = night_loop_media_duration_sec(path)
    if dur is None or dur <= NIGHT_LOOP_BOOTSTRAP_TAIL_SEC + 0.5:
        return None
    return night_loop_bootstrap_tail_ffmpeg_parameters()


def is_night_loop_media_path(path: Path) -> bool:
    """Тот же файл, что и ночной луп (по resolve), для выбора FFmpeg / логов."""
    if not path.is_file():
        return False
    canonical = night_loop_file_path()
    if not canonical.is_file():
        return False
    return path.resolve() == canonical.resolve()


def scheduled_stream_target(default_url: str, now: datetime | None = None) -> str | Path:
    """Какой источник должен идти в эфир по расписанию (без учёта ручного выбора днём)."""
    if is_night_loop_video_window_utc(now):
        path = night_loop_file_path()
        if path.is_file():
            return path
    return default_url


def stream_after_end_target(default_url: str) -> str | Path:
    """После stream_end: ночью — по расписанию, иначе как раньше — default_url."""
    if is_night_radio_lockout_utc():
        return scheduled_stream_target(default_url)
    return default_url
