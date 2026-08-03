import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from programs.night_schedule import radio_now_playing_text


class RadioNowPlayingTests(unittest.TestCase):
    def test_status_describes_the_stream_scheduled_right_now(self):
        station_name = "🎧 LoFi Girl"
        cases = (
            (
                datetime(2026, 7, 19, 18, 14, tzinfo=timezone.utc),
                "**Сейчас играет:** 🎧 LoFi Girl.",
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
                "**Сейчас играет:** 🎧 LoFi Girl.",
            ),
            (
                datetime(2026, 7, 20, 3, 0, tzinfo=timezone.utc),
                "**Сейчас играет:** 🎧 LoFi Girl.",
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
                        self.assertEqual(
                            radio_now_playing_text(now, station_name=station_name),
                            expected,
                        )

    def test_status_falls_back_to_ordinary_when_night_media_is_missing(self):
        with TemporaryDirectory() as temporary_directory:
            missing_media = Path(temporary_directory) / "night_loop.mp4"
            with patch(
                "programs.night_schedule.night_loop_file_path",
                return_value=missing_media,
            ):
                self.assertEqual(
                    radio_now_playing_text(
                        datetime(2026, 7, 19, 23, 0, tzinfo=timezone.utc),
                        station_name="🎧 LoFi Girl",
                    ),
                    "**Сейчас играет:** 🎧 LoFi Girl.",
                )

    def test_status_keeps_generic_daytime_fallback_when_station_is_unknown(self):
        with TemporaryDirectory() as temporary_directory:
            missing_media = Path(temporary_directory) / "night_loop.mp4"
            with patch(
                "programs.night_schedule.night_loop_file_path",
                return_value=missing_media,
            ):
                self.assertEqual(
                    radio_now_playing_text(
                        datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)
                    ),
                    "**Сейчас играет:** обычный эфир.",
                )

    def test_status_has_an_english_variant(self):
        with TemporaryDirectory() as temporary_directory:
            missing_media = Path(temporary_directory) / "night_loop.mp4"
            with patch(
                "programs.night_schedule.night_loop_file_path",
                return_value=missing_media,
            ):
                self.assertEqual(
                    radio_now_playing_text(
                        datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc),
                        locale="en",
                    ),
                    "**Now playing:** regular broadcast.",
                )


if __name__ == "__main__":
    unittest.main()
