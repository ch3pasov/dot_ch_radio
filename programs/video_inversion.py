"""Geometric circle inversion for Telegram video notes.

The feature was originally proposed by Evgenii Novikov (@enovikov11). This
implementation uses the existing NumPy and FFmpeg runtime instead of OpenCV.
"""

from __future__ import annotations

import asyncio
import io
import json
import math
import os
import shutil
import subprocess
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from typing import BinaryIO

import numpy as np


DEFAULT_RADIUS_PERCENT = 0.2
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_VIDEO_DIMENSION = 1024
PROBE_TIMEOUT_SECONDS = 15
TRANSCODE_TIMEOUT_SECONDS = 180
INVALID_MAP_COORDINATE = np.iinfo(np.uint16).max


class VideoInversionError(RuntimeError):
    """Raised when a video note cannot be safely transformed."""


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    duration: float


class InvertedVideoNote(io.BytesIO):
    """In-memory MP4 with metadata needed by Telethon's upload API."""

    def __init__(self, data: bytes, *, info: VideoInfo):
        super().__init__(data)
        self.name = "inverted-video-note.mp4"
        self.width = info.width
        self.height = info.height
        self.duration = info.duration


def _source_bytes(source: bytes | bytearray | BinaryIO) -> bytes:
    if isinstance(source, bytes):
        return source
    if isinstance(source, bytearray):
        return bytes(source)
    if hasattr(source, "getvalue"):
        return bytes(source.getvalue())
    return bytes(source.read())


def _validated_radius(
    width: int,
    height: int,
    radius_percent: float,
) -> int:
    if width <= 0 or height <= 0:
        raise ValueError("Video dimensions must be positive.")
    if width > MAX_VIDEO_DIMENSION or height > MAX_VIDEO_DIMENSION:
        raise ValueError(
            f"Video dimensions must not exceed {MAX_VIDEO_DIMENSION}px."
        )
    if not 0 < radius_percent <= 1:
        raise ValueError("radius_percent must be between 0 and 1.")

    radius = int(min(width, height) * radius_percent)
    if radius < 1:
        raise ValueError("The inversion radius is too small for this video.")
    return radius


def build_circle_inversion_maps(
    width: int,
    height: int,
    *,
    radius_percent: float = DEFAULT_RADIUS_PERCENT,
) -> tuple[np.ndarray, np.ndarray]:
    """Build FFmpeg remap coordinates for geometric circle inversion."""

    x0 = width // 2
    y0 = height // 2
    radius = _validated_radius(width, height, radius_percent)

    y_new, x_new = np.indices((height, width), dtype=np.float64)
    dx = x_new - x0
    dy = y_new - y0
    distance_squared = dx * dx + dy * dy

    x_source = np.full((height, width), x0, dtype=np.float64)
    y_source = np.full((height, width), y0, dtype=np.float64)
    away_from_center = distance_squared != 0
    scale = np.zeros_like(distance_squared)
    scale[away_from_center] = (
        radius * radius / distance_squared[away_from_center]
    )
    x_source[away_from_center] = (
        x0 + dx[away_from_center] * scale[away_from_center]
    )
    y_source[away_from_center] = (
        y0 + dy[away_from_center] * scale[away_from_center]
    )

    # Match the original C++ implementation: truncate coordinates toward zero.
    x_integer = x_source.astype(np.int64)
    y_integer = y_source.astype(np.int64)
    valid = (
        (x_integer >= 0)
        & (x_integer < width)
        & (y_integer >= 0)
        & (y_integer < height)
    )

    x_map = np.where(
        valid,
        x_integer,
        INVALID_MAP_COORDINATE,
    ).astype("<u2")
    y_map = np.where(
        valid,
        y_integer,
        INVALID_MAP_COORDINATE,
    ).astype("<u2")
    return x_map, y_map


def _run_process(
    command: list[str],
    *,
    timeout: int,
    operation: str,
    pass_fds: tuple[int, ...] = (),
) -> bytes:
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            pass_fds=pass_fds,
        )
    except FileNotFoundError as error:
        raise VideoInversionError(
            f"{operation} is unavailable in this runtime."
        ) from error
    except subprocess.TimeoutExpired as error:
        raise VideoInversionError(f"{operation} timed out.") from error

    if completed.returncode != 0:
        raise VideoInversionError(f"{operation} failed.")
    return completed.stdout


@contextmanager
def _memory_file(name: str, data: bytes = b""):
    if not hasattr(os, "memfd_create"):
        raise VideoInversionError(
            "Anonymous in-memory files are unavailable in this runtime."
        )

    fd = os.memfd_create(name, flags=getattr(os, "MFD_CLOEXEC", 0))
    try:
        remaining = memoryview(data)
        while remaining:
            written = os.write(fd, remaining)
            remaining = remaining[written:]
        os.lseek(fd, 0, os.SEEK_SET)
        yield fd
    finally:
        os.close(fd)


def _fd_path(fd: int) -> str:
    return f"/proc/self/fd/{fd}"


def _read_memory_file(fd: int) -> bytes:
    os.lseek(fd, 0, os.SEEK_SET)
    with os.fdopen(os.dup(fd), "rb") as memory_file:
        return memory_file.read()


def _probe_video(input_fd: int) -> VideoInfo:
    probe_output = _run_process(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,duration:format=duration",
            "-of",
            "json",
            _fd_path(input_fd),
        ],
        timeout=PROBE_TIMEOUT_SECONDS,
        operation="Video inspection",
        pass_fds=(input_fd,),
    )

    try:
        probe_data = json.loads(probe_output)
        streams = probe_data["streams"]
        width = int(streams[0]["width"])
        height = int(streams[0]["height"])
        duration_value = (
            probe_data.get("format", {}).get("duration")
            or streams[0].get("duration")
        )
        duration = float(duration_value)
    except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise VideoInversionError("The video has no readable metadata.") from error

    if not math.isfinite(duration) or duration <= 0:
        raise VideoInversionError("The video has no readable duration.")

    try:
        _validated_radius(width, height, DEFAULT_RADIUS_PERCENT)
    except ValueError as error:
        raise VideoInversionError(str(error)) from error
    return VideoInfo(width=width, height=height, duration=duration)


def invert_video_note_bytes(
    source: bytes | bytearray | BinaryIO,
    *,
    radius_percent: float = DEFAULT_RADIUS_PERCENT,
) -> InvertedVideoNote:
    """Invert a video note with the existing NumPy and FFmpeg runtime."""

    raw = _source_bytes(source)
    if not raw:
        raise VideoInversionError("The downloaded video note is empty.")
    if len(raw) > MAX_INPUT_BYTES:
        raise VideoInversionError("The video note is too large to process safely.")
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise VideoInversionError("FFmpeg is unavailable in this runtime.")

    with ExitStack() as memory_files:
        input_fd = memory_files.enter_context(
            _memory_file("dot-ch-video-input", raw)
        )
        info = _probe_video(input_fd)
        try:
            x_map, y_map = build_circle_inversion_maps(
                info.width,
                info.height,
                radius_percent=radius_percent,
            )
        except ValueError as error:
            raise VideoInversionError(str(error)) from error

        x_map_fd = memory_files.enter_context(
            _memory_file("dot-ch-video-x-map", x_map.tobytes(order="C"))
        )
        y_map_fd = memory_files.enter_context(
            _memory_file("dot-ch-video-y-map", y_map.tobytes(order="C"))
        )
        output_fd = memory_files.enter_context(
            _memory_file("dot-ch-video-output")
        )

        video_size = f"{info.width}x{info.height}"
        filter_graph = (
            "[0:v:0][1:v:0][2:v:0]"
            "remap=format=color,format=yuv420p[v]"
        )
        _run_process(
            [
                "ffmpeg",
                "-nostdin",
                "-y",
                "-loglevel",
                "error",
                "-i",
                _fd_path(input_fd),
                "-f",
                "rawvideo",
                "-pixel_format",
                "gray16le",
                "-video_size",
                video_size,
                "-i",
                _fd_path(x_map_fd),
                "-f",
                "rawvideo",
                "-pixel_format",
                "gray16le",
                "-video_size",
                video_size,
                "-i",
                _fd_path(y_map_fd),
                "-filter_complex",
                filter_graph,
                "-map",
                "[v]",
                "-map",
                "0:a?",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                "-shortest",
                "-f",
                "mp4",
                _fd_path(output_fd),
            ],
            timeout=TRANSCODE_TIMEOUT_SECONDS,
            operation="Video inversion",
            pass_fds=(input_fd, x_map_fd, y_map_fd, output_fd),
        )

        output_data = _read_memory_file(output_fd)
        if not output_data:
            raise VideoInversionError("Video inversion produced no output.")
        output = InvertedVideoNote(output_data, info=info)

    return output


async def invert_video_note(
    source: bytes | bytearray | BinaryIO,
    *,
    radius_percent: float = DEFAULT_RADIUS_PERCENT,
) -> InvertedVideoNote:
    """Run video-note inversion outside Telegram's event loop."""

    return await asyncio.to_thread(
        invert_video_note_bytes,
        source,
        radius_percent=radius_percent,
    )
