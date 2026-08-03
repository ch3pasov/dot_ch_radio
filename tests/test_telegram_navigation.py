import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from libs.telegram_delivery import DeliveryResult
from libs.telegram_navigation import (
    answer_refresh_callback,
    is_refresh_callback,
    refresh_feedback_text,
    unwrap_refresh_callback,
)


class TelegramNavigationTests(unittest.IsolatedAsyncioTestCase):
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

    def test_refresh_feedback_describes_changed_and_current_pages(self):
        self.assertIsNone(refresh_feedback_text(changed=True))
        self.assertEqual(
            refresh_feedback_text(changed=False),
            "Обновлено (ничего не изменилось)",
        )
        self.assertEqual(
            refresh_feedback_text(changed=False, locale="en"),
            "Refreshed (nothing changed)",
        )

    async def test_refresh_callback_answers_once_after_a_changed_page(self):
        event = SimpleNamespace(answer=AsyncMock())

        await answer_refresh_callback(
            event,
            DeliveryResult(message="edited", changed=True),
        )

        event.answer.assert_awaited_once_with(cache_time=0)

    async def test_refresh_callback_answers_once_after_an_unchanged_page(self):
        event = SimpleNamespace(answer=AsyncMock())

        await answer_refresh_callback(
            event,
            DeliveryResult(message="same", changed=False),
        )

        event.answer.assert_awaited_once_with(
            "Обновлено (ничего не изменилось)",
            cache_time=0,
        )

    async def test_refresh_callback_preserves_router_errors(self):
        event = SimpleNamespace(answer=AsyncMock())

        await answer_refresh_callback(event, "😬 битая кнопка")

        event.answer.assert_awaited_once_with("😬 битая кнопка", cache_time=0)


if __name__ == "__main__":
    unittest.main()
