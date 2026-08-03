import unittest
import unicodedata
from collections import OrderedDict
from hashlib import md5

from telethon import TelegramClient
from telethon.sessions import MemorySession

from content.content import common_tree
from libs.telegram_ui import build_button, build_child_rows


class ContentTreeTests(unittest.TestCase):
    def test_route_aliases_use_only_the_plural_field(self):
        def walk(node, path="root"):
            self.assertNotIn("alias", node, path)
            if "aliases" in node:
                self.assertIsInstance(node["aliases"], list, path)
            for child_id, child in node.get("children", {}).items():
                walk(child, f"{path}/{child_id}")

        walk(common_tree)

    def test_top_level_navigation_and_confirmed_subtrees(self):
        root_children = common_tree["children"]
        self.assertEqual(list(root_children), ["radio", "tools", "games", "other"])
        self.assertEqual(
            list(root_children["tools"]["children"]),
            [
                "invert_picture",
                "foreign_languages",
                "is_this_true",
                "weather",
                "search_wanted",
            ],
        )
        self.assertEqual(
            list(root_children["games"]["children"]),
            ["vasilii_game", "telegram", "roblox"],
        )
        self.assertEqual(
            list(root_children["games"]["children"]["roblox"]["children"]),
            ["life_grid"],
        )
        self.assertEqual(
            list(root_children["other"]["children"]),
            ["my_folder", "about_me", "language", "my_data", "secret_place"],
        )

    def test_radio_places_night_broadcast_last_and_enables_live_refresh(self):
        radio = common_tree["children"]["radio"]

        self.assertEqual(next(reversed(radio["children"])), "night_radio")
        self.assertEqual(radio["custom"], "radio_now_playing")
        self.assertEqual(radio["refresh"], 1)

    def test_author_titles_and_search_copy_are_preserved(self):
        children = common_tree["children"]
        tools = children["tools"]["children"]
        games = children["games"]["children"]
        other = children["other"]["children"]

        self.assertEqual(tools["foreign_languages"]["name"], "🌐 Что-то на иностранном")
        self.assertEqual(tools["is_this_true"]["name"], "Is this true?")
        self.assertEqual(games["telegram"]["name"], "📱 Телеграм веб-игры")
        self.assertEqual(other["my_folder"]["name"], "📂 Моя папка")
        self.assertEqual(other["about_me"]["name"], "🔗 Ссылки на меня")
        self.assertEqual(other["secret_place"]["name"], "🔒 NDA папка")
        self.assertEqual(
            tools["search_wanted"]["description"],
            "👤 Инструмент для проверки нахождения людей в розыске. "
            "Обратите внимание: точность результатов не гарантируется, и данная "
            "система не должна использоваться как единственный источник информации "
            "при принятии важных решений.",
        )

    def test_circle_inversion_copy_covers_photos_and_video_notes(self):
        tools = common_tree["children"]["tools"]
        inversion = tools["children"]["invert_picture"]

        self.assertIn("фотографий и видеокружков", tools["description"])
        self.assertIn("фотографии и видеокружки", inversion["description"])
        self.assertIn("относительно окружности", inversion["description"])
        self.assertIn("**Фотографии**", inversion["description"])
        self.assertIn("**Видеокружки**", inversion["description"])
        self.assertIn("`@dot_ch_bot`", inversion["description"])
        self.assertEqual(inversion["aliases"], ["inversion", "invert_picture"])
        self.assertEqual(list(inversion["children"]), ["invert_picture_command"])

    def test_group_mention_mechanics_are_documented(self):
        tools = common_tree["children"]["tools"]["children"]
        inversion_description = tools["invert_picture"]["description"]
        katakana_description = tools["foreign_languages"]["children"]["katakana_racism"]["description"]
        truth_description = tools["is_this_true"]["description"]

        self.assertIn("приложи фотографию к сообщению с `@dot_ch_bot`", inversion_description)
        self.assertIn("ответь `@dot_ch_bot` на нужную фотографию", inversion_description)
        self.assertIn("`@dot_ch_bot текст`", katakana_description)
        self.assertIn("ответь `@dot_ch_bot` на сообщение", katakana_description)
        self.assertIn("`@dot_ch_bot is this true?`", truth_description)

    def test_about_page_offers_the_agpl_source(self):
        about = common_tree["children"]["other"]["children"]["about_me"]

        self.assertEqual(
            about["children"]["source_code"],
            {
                "name": "⌨️ Исходный код · AGPL-3.0",
                "url": "https://github.com/ch3pasov/dot_ch_radio",
            },
        )

    def test_data_center_uses_an_sf_icon_in_its_message_title(self):
        my_data = common_tree["children"]["other"]["children"]["my_data"]

        self.assertEqual(my_data["name"], "Мои данные")
        self.assertEqual(my_data["parse_mode"], "html")
        self.assertIsInstance(my_data["title_icon"], int)
        self.assertNotIn("🗄", my_data["name"])

    def test_tree_colors_are_reserved_for_semantic_calls_to_action(self):
        expected_styles = {
            "root/radio/go_to_radio": "success",
            "root/tools/invert_picture/invert_picture_command": "primary",
            "root/tools/foreign_languages/katakana_racism/rus_to_katakana_command": "primary",
            "root/tools/search_wanted/search_wanted_command": "primary",
            "root/games/roblox/life_grid/go_to_life_grid": "primary",
            "root/other/my_data/audit": "primary",
            "root/other/my_data/takeout": "success",
            "root/other/my_data/delete": "danger",
        }
        sf7_path = "root/other/my_folder/emojis_and_stickers/sf7_emoji_packs"
        for weight in (
            "ultralight",
            "thin",
            "light",
            "regular",
            "medium",
            "semibold",
            "bold",
            "heavy",
            "black",
        ):
            expected_styles[f"{sf7_path}/{weight}/search"] = "primary"

        actual_styles = {}

        def walk(node, path="root"):
            self.assertNotIn("message_effects", node)
            self.assertNotIn("children_button_style", node, path)
            for child_id, child in node.get("children", {}).items():
                child_path = f"{path}/{child_id}"
                if "button_style" in child:
                    actual_styles[child_path] = child["button_style"]
                walk(child, child_path)

        walk(common_tree)
        self.assertEqual(actual_styles, expected_styles)

    def test_data_action_colors_match_workflow_semantics(self):
        actions = common_tree["children"]["other"]["children"]["my_data"]["actions"]
        actual_styles = {
            action_id: action["button_style"]
            for action_id, action in actions.items()
            if "button_style" in action
        }
        self.assertEqual(
            actual_styles,
            {
                "audit": "primary",
                "takeout": "success",
                "delete": "danger",
                "delete_confirm": "danger",
                "retry_delete": "danger",
                "retry_delete_confirm": "danger",
            },
        )
        for action_id, action in actions.items():
            if action.get("button_style") == "danger":
                self.assertIn(
                    action["callback_data"],
                    {"data_rights:delete", "data_rights:delete_confirm"},
                    action_id,
                )

    def test_only_data_actions_carry_effect_preferences(self):
        my_data = common_tree["children"]["other"]["children"]["my_data"]
        actions = my_data["actions"]
        effect_actions = {
            action_id: action["message_effects"]
            for action_id, action in actions.items()
            if "message_effects" in action
        }
        self.assertEqual(
            effect_actions,
            {
                "takeout": ["🎉", "👍"],
                "delete_confirm": ["🎉", "🔥", "👍"],
            },
        )

    def test_navigation_is_neutral_and_dead_nadezhdin_node_is_gone(self):
        for action in common_tree["navigation_ui"].values():
            self.assertNotIn("button_style", action)
            self.assertIsInstance(action.get("button_icon"), int)

        def all_ids(node):
            for child_id, child in node.get("children", {}).items():
                yield child_id
                yield from all_ids(child)

        self.assertNotIn("nadezhdin", set(all_ids(common_tree)))

    def test_root_buttons_use_custom_icons_without_duplicate_emoji(self):
        rows = build_child_rows(common_tree["children"])
        self.assertEqual(
            [button.text for row in rows for button in row],
            ["Радио", "Инструменты и генераторы", "Игры", "Другое"],
        )

        share = build_button(
            common_tree["navigation_ui"]["share"],
            default_url="https://t.me/share/url",
        )
        self.assertEqual(share.text, "Поделиться")

    def test_every_runtime_custom_icon_label_is_deduplicated(self):
        specs = []

        def collect(node, path="root"):
            specs.extend(
                (f"{path}/action:{action_id}", action)
                for action_id, action in node.get("actions", {}).items()
            )
            for child_id, child in node.get("children", {}).items():
                child_path = f"{path}/{child_id}"
                specs.append((child_path, child))
                collect(child, child_path)

        collect(common_tree)
        specs.extend(
            (f"navigation:{action_id}", action)
            for action_id, action in common_tree["navigation_ui"].items()
        )

        icon_count = 0
        stripped_count = 0
        for path, spec in specs:
            if "button_icon" not in spec:
                continue
            icon_count += 1
            original = spec.get("button_text") or spec.get("text") or spec.get("name")
            button = build_button(spec, default_callback_data="id=icon-test")
            starts_with_symbol = unicodedata.category(original[0]).startswith("S")
            if starts_with_symbol and "button_text" not in spec:
                stripped_count += 1
                self.assertNotEqual(button.text, original, path)
            else:
                self.assertEqual(button.text, original, path)

        self.assertEqual(icon_count, 77)
        self.assertEqual(stripped_count, 28)

    def test_every_tree_markup_builds_offline_with_telegram_limits(self):
        client = TelegramClient(MemorySession(), 1, "0" * 32)

        def walk(node, path=""):
            children = node.get("children", {})
            if children:
                indexed_children = OrderedDict(
                    (
                        md5(f"{path}/{child_id}".encode()).hexdigest(),
                        child,
                    )
                    for child_id, child in children.items()
                )
                rows = build_child_rows(
                    indexed_children,
                    columns=node.get("children_columns", 1),
                )
                self.assertIsNotNone(client.build_reply_markup(rows), path)
            for child_id, child in children.items():
                with self.subTest(path=f"{path}/{child_id}"):
                    walk(child, f"{path}/{child_id}")

        walk(common_tree)

        navigation = common_tree["navigation_ui"]
        navigation_rows = [[
            build_button(navigation["back"], default_callback_data="id=parent"),
            build_button(
                navigation["share"],
                default_url="https://t.me/share/url?url=example",
            ),
        ], [
            build_button(
                navigation["refresh"],
                default_callback_data="refresh=1=id=page",
            ),
        ]]
        self.assertIsNotNone(client.build_reply_markup(navigation_rows))


if __name__ == "__main__":
    unittest.main()
