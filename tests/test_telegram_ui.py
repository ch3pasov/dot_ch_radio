import unittest
from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telethon import TelegramClient
from telethon.sessions import MemorySession
from telethon.tl.types import ReplyInlineMarkup, ReplyKeyboardMarkup

from libs import message_effects
from libs.message_effects import MessageEffectCatalog, send_with_effect_retry
from libs.telegram_ui import build_button, build_child_rows, build_view_rows


class TelegramButtonBuilderTests(unittest.TestCase):
    def setUp(self):
        self.client = TelegramClient(MemorySession(), 1, "0" * 32)

    def assertBuildsMarkup(self, spec, **defaults):
        button = build_button(spec, **defaults)
        markup = self.client.build_reply_markup([[button]])
        self.assertIsInstance(markup, (ReplyInlineMarkup, ReplyKeyboardMarkup))
        return button

    def test_all_supported_button_kinds_build_offline(self):
        specs = (
            {"text": "URL", "url": "https://example.com", "button_style": "primary", "button_icon": 42},
            {"text": "Copy", "copy_text": "value", "button_style": "success"},
            {"text": "Web", "web_app_url": "https://example.com/app"},
            {"text": "Simple", "simple_web_app_url": "https://example.com/simple"},
            {"text": "Callback", "callback_data": "do:thing", "button_style": "danger"},
            {"text": "Profile", "button_type": "user_profile", "user_id": 123},
            {"text": "Inline", "switch_inline_query": "query", "same_peer": False},
            {"text": "Here", "switch_inline_query_current_chat": "query"},
        )
        for spec in specs:
            with self.subTest(kind=spec["text"]):
                self.assertBuildsMarkup(spec)

        self.assertBuildsMarkup({"text": "Route"}, default_callback_data="id=abc")
        self.assertBuildsMarkup({"text": "Share"}, default_url="https://t.me/share/url")

    def test_custom_icon_removes_one_redundant_leading_symbol_cluster(self):
        cases = (
            ("↩️ В центр данных", "В центр данных"),
            ("🗑 Удалить", "Удалить"),
            ("🛠 Инструменты", "Инструменты"),
            ("👨‍👩‍👧‍👦 Семья", "Семья"),
            ("🇩🇪 Германия", "Германия"),
            ("1️⃣ Первый", "Первый"),
            ("‼️ Срочно", "Срочно"),
            ("🗑 🔥 Удалить", "🔥 Удалить"),
        )
        for label, expected in cases:
            with self.subTest(label=label):
                button = build_button(
                    {"name": label, "button_icon": 42},
                    default_callback_data="id=test",
                )
                self.assertEqual(button.text, expected)

    def test_custom_icon_preserves_textual_prefix_and_unseparated_symbol(self):
        for label in ("SF7 эмодзипаки", "# Раздел", "🛠Инструменты"):
            with self.subTest(label=label):
                button = build_button(
                    {"name": label, "button_icon": 42},
                    default_callback_data="id=test",
                )
                self.assertEqual(button.text, label)

    def test_label_is_unchanged_without_icon_or_with_explicit_override(self):
        without_icon = build_button(
            {"name": "🗑 Удалить"},
            default_callback_data="id=without-icon",
        )
        explicit_override = build_button(
            {
                "name": "🗑 Удалить",
                "button_text": "🗑 Оставить как написано",
                "button_icon": 42,
            },
            default_callback_data="id=override",
        )

        self.assertEqual(without_icon.text, "🗑 Удалить")
        self.assertEqual(explicit_override.text, "🗑 Оставить как написано")

    def test_child_rows_honor_columns_breaks_filter_and_route_factory(self):
        children = OrderedDict(
            (
                ("one", {"name": "One"}),
                ("skip", {"name": "Skip"}),
                ("two", {"name": "Two", "break_before": True}),
                ("docs", {"name": "Docs", "url": "https://example.com", "break_after": True}),
                ("three", {"name": "Three"}),
            )
        )
        rows = build_child_rows(
            children,
            columns=2,
            callback_data_for=lambda key, _item: f"open:{key}",
            include=lambda key, _item: key != "skip",
        )

        self.assertEqual([len(row) for row in rows], [1, 2, 1])
        self.assertEqual(rows[0][0].data, b"open:one")
        self.assertEqual(rows[1][0].data, b"open:two")
        self.assertEqual(rows[1][1].url, "https://example.com")
        self.assertIsInstance(self.client.build_reply_markup(rows), ReplyInlineMarkup)

    def test_view_rows_resolve_named_and_inline_actions(self):
        actions = {
            "save": {"text": "Save", "callback_data": "save", "message_effects": ["🎉"]},
            "copy": {"text": "Copy", "copy_text": "summary"},
        }
        rows = build_view_rows(
            {"rows": [["save", "copy"], [{"text": "Docs", "url": "https://example.com"}]]},
            actions,
        )
        self.assertEqual([len(row) for row in rows], [2, 1])
        self.assertIsInstance(self.client.build_reply_markup(rows), ReplyInlineMarkup)

    def test_builder_rechecks_callback_and_markup_limits(self):
        with self.assertRaisesRegex(ValueError, "64-byte"):
            build_button({"text": "Bad", "callback_data": "🔥" * 17})
        with self.assertRaisesRegex(ValueError, "between 1 and 8"):
            build_child_rows({"one": {"name": "One"}}, columns=9)
        with self.assertRaisesRegex(ValueError, "100-button"):
            build_child_rows(
                {f"n{i}": {"name": str(i)} for i in range(101)},
                columns=8,
            )
        with self.assertRaisesRegex(ValueError, "unknown action"):
            build_view_rows({"rows": [["missing"]]}, {})


class MessageEffectCatalogTests(unittest.IsolatedAsyncioTestCase):
    async def test_catalog_loads_non_premium_effects_and_resolves_in_priority_order(self):
        catalog = MessageEffectCatalog()
        client = AsyncMock(
            return_value=SimpleNamespace(
                effects=(
                    SimpleNamespace(emoticon="👍", id=10, premium_required=False),
                    SimpleNamespace(emoticon="🎉", id=20, premium_required=False),
                    SimpleNamespace(emoticon="🔥", id=30, premium_required=True),
                )
            )
        )

        self.assertEqual(await catalog.load(client), 2)
        self.assertEqual(catalog.resolve(["🔥", "🎉", "👍"]), 20)
        self.assertIsNone(catalog.resolve(["🔥"]))
        self.assertEqual(catalog.snapshot(), {"👍": 10, "🎉": 20})
        client.assert_awaited_once()

    async def test_failed_refresh_clears_stale_catalog(self):
        catalog = MessageEffectCatalog()
        good_client = AsyncMock(
            return_value=SimpleNamespace(
                effects=(SimpleNamespace(emoticon="👍", id=10, premium_required=False),)
            )
        )
        await catalog.load(good_client)
        self.assertEqual(catalog.size, 1)

        self.assertEqual(await catalog.load(AsyncMock(side_effect=RuntimeError("offline"))), 0)
        self.assertEqual(catalog.size, 0)

    async def test_retry_only_handles_effect_specific_rpc_errors(self):
        class FakeRPCError(Exception):
            pass

        attempted = []

        async def send(effect_id):
            attempted.append(effect_id)
            if len(attempted) == 1:
                raise FakeRPCError("MESSAGE_EFFECT_INVALID")
            return "sent"

        with patch.object(message_effects, "RPCError", FakeRPCError):
            self.assertEqual(await send_with_effect_retry(send, 20), "sent")
        self.assertEqual(attempted, [20, None])

        async def unrelated(_effect_id):
            raise FakeRPCError("FLOOD_WAIT")

        with patch.object(message_effects, "RPCError", FakeRPCError):
            with self.assertRaisesRegex(FakeRPCError, "FLOOD_WAIT"):
                await send_with_effect_retry(unrelated, 20)


if __name__ == "__main__":
    unittest.main()
