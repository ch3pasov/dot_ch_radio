import unittest
from collections import OrderedDict
from hashlib import md5

from telethon import TelegramClient
from telethon.sessions import MemorySession

from content.content import common_tree
from libs.telegram_ui import build_button, build_child_rows


class ContentTreeTests(unittest.TestCase):
    def test_top_level_navigation_and_confirmed_subtrees(self):
        root_children = common_tree["children"]
        self.assertEqual(list(root_children), ["radio", "tools", "games", "other"])
        self.assertEqual(
            list(root_children["tools"]["children"]),
            ["invert_picture", "foreign_languages", "weather", "search_wanted"],
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
            ["my_folder", "about_me", "my_data", "secret_place"],
        )

    def test_author_titles_and_search_copy_are_preserved(self):
        children = common_tree["children"]
        tools = children["tools"]["children"]
        games = children["games"]["children"]
        other = children["other"]["children"]

        self.assertEqual(tools["foreign_languages"]["name"], "🌐 Что-то на иностранном")
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

    def test_every_visible_tree_button_has_an_allowed_style(self):
        allowed_styles = {"primary", "success", "danger"}
        danger_paths = []

        def walk(node, path="root"):
            self.assertNotIn("message_effects", node)
            for child_id, child in node.get("children", {}).items():
                child_path = f"{path}/{child_id}"
                self.assertIn(child.get("button_style"), allowed_styles, child_path)
                if child["button_style"] == "danger":
                    danger_paths.append(child_path)
                walk(child, child_path)

        walk(common_tree)
        self.assertEqual(danger_paths, ["root/other/my_data/delete"])

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
                "receipt": ["👍", "🎉"],
            },
        )

    def test_navigation_is_primary_and_dead_nadezhdin_node_is_gone(self):
        for action in common_tree["navigation_ui"].values():
            self.assertEqual(action["button_style"], "primary")
            self.assertIsInstance(action.get("button_icon"), int)

        def all_ids(node):
            for child_id, child in node.get("children", {}).items():
                yield child_id
                yield from all_ids(child)

        self.assertNotIn("nadezhdin", set(all_ids(common_tree)))

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
