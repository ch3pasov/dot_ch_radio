import hashlib
import json
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telethon import TelegramClient
from telethon.sessions import MemorySession
from telethon.tl.types import ReplyInlineMarkup

from programs import data_rights


class DataRightsArtifactsTests(unittest.TestCase):
    def test_takeout_is_deterministic_and_contains_zero_personal_records(self):
        first = data_rights.build_takeout_archive().getvalue()
        second = data_rights.build_takeout_archive().getvalue()
        self.assertEqual(hashlib.sha256(first).digest(), hashlib.sha256(second).digest())

        with zipfile.ZipFile(data_rights.build_takeout_archive()) as archive:
            self.assertEqual(sorted(archive.namelist()), ["README.txt", "manifest.json"])
            manifest = json.loads(archive.read("manifest.json"))

        self.assertEqual(manifest["totals"], {"records": 0, "bytes": 0})
        self.assertTrue(manifest["artifact"]["built_in_memory"])
        self.assertFalse(manifest["artifact"]["saved_by_bot"])
        self.assertFalse(manifest["artifact"]["personal_identifiers_included"])
        self.assertTrue(all(dataset["records"] == 0 for dataset in manifest["datasets"]))

    def test_receipt_contains_no_dynamic_identifier_or_timestamp(self):
        receipt = data_rights.build_deletion_receipt().getvalue().decode("utf-8")
        self.assertIn("Найдено объектов: 0", receipt)
        self.assertIn("Telegram ID", receipt)
        self.assertNotIn("2026-", receipt)

    def test_all_callback_payloads_fit_telegram_limit(self):
        callbacks = (
            data_rights.CALLBACK_HOME,
            data_rights.CALLBACK_AUDIT,
            data_rights.CALLBACK_TAKEOUT,
            data_rights.CALLBACK_DELETE,
            data_rights.CALLBACK_DELETE_CONFIRM,
            data_rights.CALLBACK_RECEIPT,
        )
        self.assertTrue(all(len(callback.encode("utf-8")) <= 64 for callback in callbacks))

    def test_performance_button_layouts_build_as_inline_markups(self):
        client = TelegramClient(MemorySession(), 1, "0" * 32)
        layouts = (
            data_rights._result_buttons(),
            data_rights._delete_confirmation_buttons(),
            data_rights._deletion_result_buttons(),
        )
        for layout in layouts:
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
        result = await data_rights.handle_data_rights_callback(event, object())
        self.assertEqual(result, "home")
        event.answer.assert_awaited_once_with()
        event.get_message.assert_not_awaited()

    async def test_audit_callback_is_answered_before_workflow(self):
        event, message = self._event(data_rights.CALLBACK_AUDIT)
        with patch.object(data_rights, "_run_audit", new=AsyncMock()) as run_audit:
            result = await data_rights.handle_data_rights_callback(event, "client")

        self.assertEqual(result, "handled")
        event.answer.assert_awaited_once_with("Начинаю аудит")
        run_audit.assert_awaited_once_with("client", 7, message)

    async def test_failed_workflow_leaves_retry_ui_without_personal_log_data(self):
        event, message = self._event(data_rights.CALLBACK_TAKEOUT)
        failed = AsyncMock(side_effect=RuntimeError("private payload"))
        with patch.object(data_rights, "_run_takeout", new=failed):
            with self.assertLogs(data_rights._LOGGER, level="ERROR") as captured:
                result = await data_rights.handle_data_rights_callback(event, "client")

        self.assertEqual(result, "handled")
        self.assertNotIn("private payload", "\n".join(captured.output))
        message.edit.assert_awaited_once()
        self.assertIn("Операция прервана", message.edit.await_args.args[0])


if __name__ == "__main__":
    unittest.main()
