import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telethon.errors import MessageNotModifiedError, ReplyMarkupTooLongError

from libs.telegram_delivery import deliver_message


class TelegramDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_sends_only_the_fully_rendered_message(self):
        send_message = AsyncMock(return_value="sent")
        client = SimpleNamespace(send_message=send_message)

        result = await deliver_message(
            client,
            None,
            123,
            "Final page",
            buttons=[["button"]],
            link_preview=False,
            file="media",
            parse_mode="html",
        )

        self.assertEqual(result, "sent")
        send_message.assert_awaited_once_with(
            123,
            "Final page",
            buttons=[["button"]],
            link_preview=False,
            file="media",
            parse_mode="html",
        )

    async def test_existing_menu_is_edited_once_with_final_content(self):
        client = SimpleNamespace(send_message=AsyncMock())
        message = SimpleNamespace(edit=AsyncMock(return_value="edited"))

        result = await deliver_message(client, message, 123, "Updated page")

        self.assertEqual(result, "edited")
        client.send_message.assert_not_awaited()
        message.edit.assert_awaited_once_with(
            "Updated page",
            buttons=None,
            link_preview=True,
            file=None,
            parse_mode=(),
        )

    async def test_unchanged_edit_is_a_successful_refresh(self):
        client = SimpleNamespace(send_message=AsyncMock())
        message = SimpleNamespace(
            edit=AsyncMock(side_effect=MessageNotModifiedError(None))
        )

        result = await deliver_message(client, message, 123, "Same page")

        self.assertIs(result, message)
        client.send_message.assert_not_awaited()

    async def test_oversized_markup_falls_back_without_placeholder_or_media(self):
        send_message = AsyncMock(
            side_effect=(ReplyMarkupTooLongError(None), "fallback")
        )
        client = SimpleNamespace(send_message=send_message)

        result = await deliver_message(
            client,
            None,
            123,
            "Final page",
            buttons=[["too many"]],
            file="media",
        )

        self.assertEqual(result, "fallback")
        self.assertEqual(send_message.await_count, 2)
        fallback_call = send_message.await_args_list[1]
        self.assertIn("Telegram отклонил", fallback_call.args[1])
        self.assertIsNone(fallback_call.kwargs["buttons"])
        self.assertIsNone(fallback_call.kwargs["file"])

    async def test_unchanged_oversized_markup_fallback_is_a_successful_refresh(self):
        client = SimpleNamespace(send_message=AsyncMock())
        message = SimpleNamespace(
            edit=AsyncMock(
                side_effect=(
                    ReplyMarkupTooLongError(None),
                    MessageNotModifiedError(None),
                )
            )
        )

        result = await deliver_message(
            client,
            message,
            123,
            "Final page",
            buttons=[["too many"]],
        )

        self.assertIs(result, message)
        self.assertEqual(message.edit.await_count, 2)
        client.send_message.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
