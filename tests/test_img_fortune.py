import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

from telethon import TelegramClient
from telethon.errors import MessageNotModifiedError
from telethon.sessions import MemorySession

from get_hashdict import alias_dicts, common_hashdicts
from programs.img_fortune import (
    day_picker_view,
    fortune_argument,
    fortune_query,
    fortune_search_url,
    fortune_view,
    handle_fortune_callback,
    month_picker_view,
    parse_fortune_date,
    reply_to_fortune,
)


class FortuneDateTests(unittest.TestCase):
    def test_dates_keep_day_month_order_and_leading_zeroes(self):
        for value, expected in (
            ("21.09", "IMG_2109"),
            (" 1.2 ", "IMG_0102"),
            ("21.09.1990", "IMG_2109"),
            ("29.02", "IMG_2902"),
            ("29.02.2024", "IMG_2902"),
        ):
            with self.subTest(value=value):
                self.assertEqual(fortune_query(parse_fortune_date(value)), expected)

    def test_invalid_dates_and_extraneous_input_are_rejected(self):
        for value in (
            "31.04", "00.01", "01.13", "29.02.2023", "29.02.1900", "01.01.0000",
            "2109", "21/09", "21.09.90", "21.09 extra", "<b>21.09</b>", "", "9" * 5000,
        ):
            with self.subTest(value=value[:30]):
                with self.assertRaises(ValueError):
                    parse_fortune_date(value)

    def test_search_url_quotes_the_exact_filename(self):
        url = urlsplit(fortune_search_url(date(2000, 2, 1)))
        self.assertEqual((url.scheme, url.netloc, url.path), (
            "https", "www.youtube.com", "/results",
        ))
        self.assertEqual(parse_qs(url.query), {"search_query": ['"IMG_0102"']})

    def test_every_day_has_a_distinct_four_digit_query(self):
        dates = [date(2000, 1, 1) + timedelta(days=i) for i in range(366)]
        queries = {fortune_query(value) for value in dates}
        self.assertEqual(len(queries), 366)
        for query in queries:
            self.assertRegex(query, r"^IMG_[0-9]{4}$")

    def test_commands_target_this_bot_and_bare_dates_stay_private(self):
        for text, is_private, expected in (
            ("/fortune", True, ""),
            ("/fortune 21.09", False, "21.09"),
            ("/fortune@dot_ch_bot 21.09", False, "21.09"),
            ("@DOT_CH_BOT /fortune 21.09", False, "21.09"),
            ("/fortune invalid", True, "invalid"),
            ("21.09", True, "21.09"),
            ("31.02", True, "31.02"),
            ("21.09", False, None),
            ("/fortune@another_bot 21.09", True, None),
            ("@another_bot /fortune 21.09", False, None),
            ("/fortuneteller 21.09", True, None),
            ("let's meet 21.09", True, None),
        ):
            with self.subTest(text=text, is_private=is_private):
                self.assertEqual(fortune_argument(
                    text, bot_username="dot_ch_bot", is_private=is_private,
                ), expected)

    def test_calendar_buttons_cover_all_valid_dates_and_serialize(self):
        client = TelegramClient(MemorySession(), 1, "test")
        for locale in ("ru", "en"):
            _, months = month_picker_view(locale=locale)
            self.assertIsNotNone(client.build_reply_markup(months))
            for month in range(1, 13):
                _, rows = day_picker_view(month, locale=locale)
                buttons = [button for row in rows[:-1] for button in row]
                expected = (date(2000 if month < 12 else 2001, month % 12 + 1, 1)
                            - date(2000, month, 1)).days
                self.assertEqual(len(buttons), expected)
                self.assertIsNotNone(client.build_reply_markup(rows))
                for day, button in enumerate(buttons, 1):
                    self.assertEqual(button.data, f"img_fortune:date:{day:02d}{month:02d}".encode())
                    self.assertLessEqual(len(button.data), 64)
                    _, result_buttons = fortune_view(date(2000, month, day), locale=locale)
                    self.assertIsNotNone(client.build_reply_markup(result_buttons))

    def test_deep_links_reach_the_localized_menu(self):
        for locale in ("ru", "en"):
            aliases = alias_dicts[locale]
            self.assertEqual(aliases["img_fortune"], aliases["fortune"])
            page = common_hashdicts[locale][aliases["img_fortune"]]
            self.assertIn("/fortune 21.09", page["description"])


class FortuneHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_private_date_produces_a_result_without_network_lookup(self):
        event = SimpleNamespace(is_private=True, reply=AsyncMock())
        await reply_to_fortune(event, "21.09.1990", bot_username="dot_ch_bot", locale="ru")
        args, kwargs = event.reply.call_args
        self.assertIn("IMG_2109", args[0])
        self.assertNotIn("1990", args[0])
        self.assertEqual(kwargs["parse_mode"], "html")
        self.assertFalse(kwargs["link_preview"])
        self.assertIn("youtube.com/results?", kwargs["buttons"][0][0].url)

    async def test_invalid_input_is_not_echoed_as_html(self):
        event = SimpleNamespace(is_private=True, reply=AsyncMock())
        await reply_to_fortune(event, "<b>bad date</b>", bot_username="dot_ch_bot", locale="en")
        args, kwargs = event.reply.call_args
        self.assertIn("valid date", args[0])
        self.assertNotIn("bad date", args[0])
        self.assertEqual(kwargs["buttons"][0][0].data, b"img_fortune:months")

    async def test_group_replies_have_working_urls_instead_of_private_callbacks(self):
        for argument in ("", "21.09", "31.02"):
            with self.subTest(argument=argument):
                event = SimpleNamespace(is_private=False, reply=AsyncMock())
                await reply_to_fortune(event, argument, bot_username="dot_ch_bot", locale="en")
                buttons = event.reply.call_args.kwargs["buttons"]
                self.assertEqual(buttons[-1][0].url, "https://t.me/dot_ch_bot?start=img_fortune")
                self.assertTrue(all(hasattr(button, "url") for row in buttons for button in row))
                self.assertEqual(len(buttons), 2 if argument == "21.09" else 1)

    async def test_calendar_callbacks_work_using_only_the_payload(self):
        for data, expected in (
            (b"img_fortune:months", "month"),
            (b"img_fortune:month:02", "February"),
            (b"img_fortune:date:2902", "IMG_2902"),
        ):
            with self.subTest(data=data):
                event = SimpleNamespace(data=data, answer=AsyncMock(), edit=AsyncMock())
                await handle_fortune_callback(event, locale="en")
                self.assertIn(expected, event.edit.call_args.args[0])
                event.answer.assert_awaited_once_with()

    async def test_malformed_callbacks_are_acknowledged_without_editing(self):
        for data in (
            b"img_fortune:month:00", b"img_fortune:month:13", b"img_fortune:date:3104",
            b"img_fortune:date:0001", b"img_fortune:date:0100", b"img_fortune:unknown",
        ):
            with self.subTest(data=data):
                event = SimpleNamespace(data=data, answer=AsyncMock(), edit=AsyncMock())
                await handle_fortune_callback(event, locale="en")
                event.edit.assert_not_awaited()
                event.answer.assert_awaited_once()

    async def test_repeated_callback_is_still_acknowledged(self):
        event = SimpleNamespace(
            data=b"img_fortune:months", answer=AsyncMock(),
            edit=AsyncMock(side_effect=MessageNotModifiedError(request=None)),
        )
        await handle_fortune_callback(event, locale="en")
        event.answer.assert_awaited_once_with()


if __name__ == "__main__":
    unittest.main()
