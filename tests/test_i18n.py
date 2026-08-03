import re
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from content.content import (
    common_trees,
    search_sf7_custom_emoji_html,
    wanted_not_found_text,
)
from get_hashdict import alias_dicts, common_hashdicts
from libs.i18n import EN, RU, locale_from_event, normalize_locale


CYRILLIC = re.compile(r"[А-Яа-яЁё]")


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)


class LocaleSelectionTests(unittest.IsolatedAsyncioTestCase):
    def test_only_russian_telegram_locales_select_russian(self):
        self.assertEqual(normalize_locale("ru"), RU)
        self.assertEqual(normalize_locale("RU-ru"), RU)
        self.assertEqual(normalize_locale("ru_RU"), RU)

    def test_english_is_the_fallback_for_every_other_language(self):
        for language_code in ("en", "en-US", "de", "sr", "", None):
            with self.subTest(language_code=language_code):
                self.assertEqual(normalize_locale(language_code), EN)

    async def test_event_locale_is_read_from_the_current_sender(self):
        russian_event = SimpleNamespace(
            get_sender=AsyncMock(return_value=SimpleNamespace(lang_code="ru"))
        )
        fallback_event = SimpleNamespace(
            get_sender=AsyncMock(return_value=SimpleNamespace(lang_code=None))
        )

        self.assertEqual(await locale_from_event(russian_event), RU)
        self.assertEqual(await locale_from_event(fallback_event), EN)


class LocalizedContentTests(unittest.TestCase):
    def test_locales_keep_identical_routes_aliases_and_deep_link_hashes(self):
        self.assertEqual(set(common_hashdicts[RU]), set(common_hashdicts[EN]))
        self.assertEqual(alias_dicts[RU], alias_dicts[EN])

    def test_english_tree_has_no_untranslated_cyrillic_interface_text(self):
        untranslated = [
            text for text in _strings(common_trees[EN]) if CYRILLIC.search(text)
        ]
        self.assertEqual(untranslated, [])

    def test_language_page_explains_telegram_setting_without_a_switch(self):
        russian_page = common_trees[RU]["children"]["other"]["children"]["language"]
        english_page = common_trees[EN]["children"]["other"]["children"]["language"]

        self.assertEqual(russian_page["aliases"], ["language"])
        self.assertIn("Telegram → Настройки → Язык", russian_page["description"])
        self.assertIn("Telegram → Settings → Language", english_page["description"])
        self.assertNotIn("callback_data", russian_page)

    def test_dynamic_content_is_localized(self):
        self.assertIn(
            "Use a longer query",
            search_sf7_custom_emoji_html("regular", "x", locale=EN),
        )
        self.assertIn("Check complete", wanted_not_found_text(EN))


if __name__ == "__main__":
    unittest.main()
