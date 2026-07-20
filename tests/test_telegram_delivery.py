import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from telethon.errors import (
    MessageNotModifiedError,
    ReplyMarkupTooLongError,
    VoiceMessagesForbiddenError,
)

from libs.telegram_delivery import (
    DeliveryResult,
    VideoNoteDeliveryResult,
    deliver_message,
    deliver_video_note_with_fallback,
)


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

        self.assertEqual(result, DeliveryResult("sent", changed=True))
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

        self.assertEqual(result, DeliveryResult("edited", changed=True))
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

        self.assertIs(result.message, message)
        self.assertFalse(result.changed)
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

        self.assertEqual(result, DeliveryResult("fallback", changed=True))
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

        self.assertIs(result.message, message)
        self.assertFalse(result.changed)
        self.assertEqual(message.edit.await_count, 2)
        client.send_message.assert_not_awaited()


class VideoNoteDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_video_note_is_used_when_telegram_accepts_it(self):
        media = SimpleNamespace(seek=AsyncMock())
        send_video_note = AsyncMock(return_value="round-message")
        send_video = AsyncMock()

        result = await deliver_video_note_with_fallback(
            media,
            send_video_note=send_video_note,
            send_video=send_video,
        )

        self.assertEqual(
            result,
            VideoNoteDeliveryResult("round-message", as_video_note=True),
        )
        send_video_note.assert_awaited_once_with()
        send_video.assert_not_awaited()

    async def test_privacy_rejection_rewinds_and_sends_regular_video(self):
        media = SimpleNamespace(seek=Mock())
        send_video_note = AsyncMock(
            side_effect=VoiceMessagesForbiddenError(None)
        )
        send_video = AsyncMock(return_value="regular-video")

        result = await deliver_video_note_with_fallback(
            media,
            send_video_note=send_video_note,
            send_video=send_video,
        )

        self.assertEqual(
            result,
            VideoNoteDeliveryResult("regular-video", as_video_note=False),
        )
        media.seek.assert_called_once_with(0)
        send_video.assert_awaited_once_with()

    async def test_unrelated_delivery_errors_are_not_hidden(self):
        media = SimpleNamespace(seek=Mock())
        send_video_note = AsyncMock(side_effect=RuntimeError("network failure"))
        send_video = AsyncMock()

        with self.assertRaisesRegex(RuntimeError, "network failure"):
            await deliver_video_note_with_fallback(
                media,
                send_video_note=send_video_note,
                send_video=send_video,
            )

        media.seek.assert_not_called()
        send_video.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
