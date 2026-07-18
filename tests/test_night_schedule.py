import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from programs.night_schedule import radio_now_playing_text


class RadioNowPlayingTests(unittest.TestCase):
    def test_status_describes_the_stream_scheduled_right_now(self):
        cases = (
            (
                datetime(2026, 7, 19, 18, 14, tzinfo=timezone.utc),
                "**Сейчас играет:** обычный эфир.",
            ),
            (
                datetime(2026, 7, 19, 18, 15, tzinfo=timezone.utc),
                "**Сейчас играет:** ночной эфир.",
            ),
            (
                datetime(2026, 7, 20, 2, 58, tzinfo=timezone.utc),
                "**Сейчас играет:** ночной эфир.",
            ),
            (
                datetime(2026, 7, 20, 2, 59, tzinfo=timezone.utc),
                "**Сейчас играет:** обычный эфир.",
            ),
            (
                datetime(2026, 7, 20, 3, 0, tzinfo=timezone.utc),
                "**Сейчас играет:** обычный эфир.",
            ),
        )

        with TemporaryDirectory() as temporary_directory:
            night_media = Path(temporary_directory) / "night_loop.mp4"
            night_media.touch()
            with patch(
                "programs.night_schedule.night_loop_file_path",
                return_value=night_media,
            ):
                for now, expected in cases:
                    with self.subTest(now=now):
                        self.assertEqual(radio_now_playing_text(now), expected)

    def test_status_falls_back_to_ordinary_when_night_media_is_missing(self):
        with TemporaryDirectory() as temporary_directory:
            missing_media = Path(temporary_directory) / "night_loop.mp4"
            with patch(
                "programs.night_schedule.night_loop_file_path",
                return_value=missing_media,
            ):
                self.assertEqual(
                    radio_now_playing_text(
                        datetime(2026, 7, 19, 23, 0, tzinfo=timezone.utc)
                    ),
                    "**Сейчас играет:** обычный эфир.",
                )


if __name__ == "__main__":
    unittest.main()
