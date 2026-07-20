import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np

from programs import video_inversion


def reference_maps(width, height, radius_percent=0.2):
    invalid = video_inversion.INVALID_MAP_COORDINATE
    x_map = np.full((height, width), invalid, dtype="<u2")
    y_map = np.full((height, width), invalid, dtype="<u2")
    x0 = width // 2
    y0 = height // 2
    radius = int(min(width, height) * radius_percent)

    for y_new in range(height):
        for x_new in range(width):
            dx = x_new - x0
            dy = y_new - y0
            distance_squared = dx * dx + dy * dy
            if distance_squared == 0:
                x_source, y_source = x0, y0
            else:
                scale = radius * radius / distance_squared
                x_source = int(x0 + dx * scale)
                y_source = int(y0 + dy * scale)
            if 0 <= x_source < width and 0 <= y_source < height:
                x_map[y_new, x_new] = x_source
                y_map[y_new, x_new] = y_source
    return x_map, y_map


class CircleInversionMapTests(unittest.TestCase):
    def test_vectorized_maps_match_the_original_algorithm(self):
        actual_x, actual_y = video_inversion.build_circle_inversion_maps(12, 10)
        expected_x, expected_y = reference_maps(12, 10)

        np.testing.assert_array_equal(actual_x, expected_x)
        np.testing.assert_array_equal(actual_y, expected_y)
        self.assertEqual(actual_x.dtype, np.dtype("<u2"))
        self.assertEqual(actual_y.dtype, np.dtype("<u2"))

    def test_map_validation_rejects_unsafe_dimensions(self):
        with self.assertRaises(ValueError):
            video_inversion.build_circle_inversion_maps(0, 10)
        with self.assertRaises(ValueError):
            video_inversion.build_circle_inversion_maps(
                video_inversion.MAX_VIDEO_DIMENSION + 1,
                10,
            )


class VideoInversionAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_inversion_runs_outside_the_telegram_event_loop(self):
        inverted = io.BytesIO(b"inverted")
        to_thread = AsyncMock(return_value=inverted)

        with patch.object(video_inversion.asyncio, "to_thread", new=to_thread):
            result = await video_inversion.invert_video_note(
                b"original",
                radius_percent=0.25,
            )

        self.assertIs(result, inverted)
        to_thread.assert_awaited_once_with(
            video_inversion.invert_video_note_bytes,
            b"original",
            radius_percent=0.25,
        )


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"),
    "FFmpeg integration requires the container runtime",
)
class VideoInversionIntegrationTests(unittest.TestCase):
    def test_ffmpeg_output_is_a_square_video_note_with_audio(self):
        with tempfile.TemporaryDirectory(prefix="dot-ch-video-test-") as temp_dir:
            workdir = Path(temp_dir)
            input_path = workdir / "input.mp4"
            output_path = workdir / "output.mp4"
            subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-y",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=size=128x128:rate=10",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=1000:sample_rate=48000",
                    "-t",
                    "1",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    str(input_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            result = video_inversion.invert_video_note_bytes(
                input_path.read_bytes()
            )
            self.assertEqual(result.name, "inverted-video-note.mp4")
            self.assertEqual(result.width, 128)
            self.assertEqual(result.height, 128)
            self.assertAlmostEqual(result.duration, 1.0, places=1)
            output_path.write_bytes(result.getvalue())

            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "stream=codec_name,codec_type,width,height",
                    "-of",
                    "json",
                    str(output_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            streams = json.loads(probe.stdout)["streams"]

        video_stream = next(
            stream for stream in streams if stream["codec_type"] == "video"
        )
        audio_stream = next(
            stream for stream in streams if stream["codec_type"] == "audio"
        )
        self.assertEqual(video_stream["codec_name"], "h264")
        self.assertEqual(video_stream["width"], 128)
        self.assertEqual(video_stream["height"], 128)
        self.assertEqual(audio_stream["codec_name"], "aac")


if __name__ == "__main__":
    unittest.main()
