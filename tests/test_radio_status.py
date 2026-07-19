import unittest
from pathlib import Path

from content.content import default_url
from get_hashdict import common_hashdict
from programs.radio_status import RadioPlaybackStatus


class RadioPlaybackStatusTests(unittest.TestCase):
    def test_known_content_url_resolves_to_its_declarative_station_name(self):
        status = RadioPlaybackStatus(common_hashdict)

        status.record_stream(default_url)

        self.assertEqual(status.current_station_name, "🎧 LoFi Girl")

    def test_night_media_and_unknown_urls_do_not_invent_station_names(self):
        status = RadioPlaybackStatus(common_hashdict)

        status.record_stream(Path("night_loop.mp4"))
        self.assertIsNone(status.current_station_name)

        status.record_stream("https://example.com/admin-stream")
        self.assertIsNone(status.current_station_name)

    def test_conflicting_names_for_one_url_are_rejected(self):
        routes = {
            "one": {"name": "Station One", "radio_url": "https://example.com/live"},
            "two": {"name": "Station Two", "radio_url": "https://example.com/live"},
        }

        with self.assertRaisesRegex(ValueError, "conflicting names"):
            RadioPlaybackStatus(routes)


if __name__ == "__main__":
    unittest.main()
