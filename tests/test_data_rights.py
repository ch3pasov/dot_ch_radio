import unittest
import zipfile
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telethon import TelegramClient
from telethon.sessions import MemorySession
from telethon.tl.types import ReplyInlineMarkup

from content.content import common_tree
from programs import data_rights


DATA_RIGHTS_UI = common_tree["children"]["other"]["children"]["my_data"]


class DataRightsArtifactsTests(unittest.TestCase):
    def test_takeout_contains_one_empty_file_with_generation_mtime(self):
        generated_at = datetime(2026, 7, 18, 12, 34, 59, tzinfo=timezone.utc)
        takeout = data_rights.build_takeout_archive(generated_at=generated_at)

        self.assertEqual(takeout.name, data_rights.TAKEOUT_FILENAME)
        with zipfile.ZipFile(takeout) as archive:
            self.assertEqual(archive.namelist(), ["data.txt"])
            self.assertEqual(archive.read("data.txt"), b"")
            info = archive.getinfo("data.txt")

        self.assertEqual(info.file_size, 0)
        self.assertEqual(info.date_time, (2026, 7, 18, 14, 34, 58))

    def test_takeout_generation_time_must_be_timezone_aware(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            data_rights.build_takeout_archive(
                generated_at=datetime(2026, 7, 18, 14, 34, 58)
            )

    def test_all_callback_payloads_fit_telegram_limit(self):
        callbacks = (
            data_rights.CALLBACK_HOME,
            data_rights.CALLBACK_AUDIT,
            data_rights.CALLBACK_TAKEOUT,
            data_rights.CALLBACK_DELETE,
            data_rights.CALLBACK_DELETE_CONFIRM,
        )
        self.assertTrue(all(len(callback.encode("utf-8")) <= 64 for callback in callbacks))

    def test_performance_button_layouts_build_as_inline_markups(self):
        client = TelegramClient(MemorySession(), 1, "0" * 32)
        for view_name in DATA_RIGHTS_UI["views"]:
            layout = data_rights._view_buttons(DATA_RIGHTS_UI, view_name)
            self.assertIsInstance(client.build_reply_markup(layout), ReplyInlineMarkup)


class DataRightsCallbackTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _event(callback):
        message = SimpleNamespace(edit=AsyncMock(), id=10)
        event = SimpleNamespace(
            data=callback.encode("ascii"),
            chat_id=7,
            answer=AsyncMock(),
            get_message=AsyncMock(return_value=message),
        )
        return event, message

    async def test_home_callback_requests_stateless_menu_navigation(self):
        event, _ = self._event(data_rights.CALLBACK_HOME)
        result = await data_rights.handle_data_rights_callback(
            event,
            object(),
            DATA_RIGHTS_UI,
        )
        self.assertEqual(result, "home")
        event.answer.assert_awaited_once_with()
        event.get_message.assert_not_awaited()

    async def test_audit_callback_is_answered_before_workflow(self):
        event, message = self._event(data_rights.CALLBACK_AUDIT)
        with patch.object(data_rights, "_run_audit", new=AsyncMock()) as run_audit:
            result = await data_rights.handle_data_rights_callback(
                event,
                "client",
                DATA_RIGHTS_UI,
            )

        self.assertEqual(result, "handled")
        event.answer.assert_awaited_once_with("Начинаю аудит")
        run_audit.assert_awaited_once_with("client", 7, message, DATA_RIGHTS_UI)

    async def test_failed_workflow_leaves_retry_ui_without_personal_log_data(self):
        event, message = self._event(data_rights.CALLBACK_TAKEOUT)
        failed = AsyncMock(side_effect=RuntimeError("private payload"))
        with patch.object(data_rights, "_run_takeout", new=failed):
            with self.assertLogs(data_rights._LOGGER, level="ERROR") as captured:
                result = await data_rights.handle_data_rights_callback(
                    event,
                    "client",
                    DATA_RIGHTS_UI,
                )

        self.assertEqual(result, "handled")
        self.assertNotIn("private payload", "\n".join(captured.output))
        message.edit.assert_awaited_once()
        self.assertIn("Операция прервана", message.edit.await_args.args[0])


if __name__ == "__main__":
    unittest.main()
