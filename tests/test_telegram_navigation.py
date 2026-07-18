import unittest

from libs.telegram_navigation import is_refresh_callback, unwrap_refresh_callback


class TelegramNavigationTests(unittest.TestCase):
    def test_refresh_callback_is_unwrapped_without_intermediate_page(self):
        callback = "refresh=1=id=0123456789abcdef"

        self.assertTrue(is_refresh_callback(callback))
        self.assertEqual(
            unwrap_refresh_callback(callback),
            "id=0123456789abcdef",
        )

    def test_regular_navigation_callback_is_unchanged(self):
        callback = "id=0123456789abcdef"

        self.assertFalse(is_refresh_callback(callback))
        self.assertEqual(unwrap_refresh_callback(callback), callback)


if __name__ == "__main__":
    unittest.main()
