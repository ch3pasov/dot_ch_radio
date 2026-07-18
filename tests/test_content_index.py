import unittest
from unittest.mock import patch

from content.content import common_tree
from libs.content_schema import normalize_tree
from libs.content_index import build_content_index, stable_hash


class ContentIndexTests(unittest.TestCase):
    def test_builds_paths_parents_shares_and_aliases(self):
        tree = {
            "name": "Root",
            "alias": "root",
            "children": {
                "folder": {
                    "name": "Folder",
                    "alias": "folder",
                    "children": {
                        "page": {"name": "Page"},
                    },
                }
            },
        }

        index, aliases = build_content_index(tree, "example_bot")
        root_hash = stable_hash("")
        folder_hash = stable_hash("/folder")
        page_hash = stable_hash("/folder/page")

        self.assertEqual(aliases, {"root": root_hash, "folder": folder_hash})
        self.assertEqual(index[folder_hash]["parent"], root_hash)
        self.assertEqual(index[page_hash]["parent"], folder_hash)
        self.assertEqual(index[page_hash]["share"], f"t.me/example_bot?start=id={page_hash}")
        self.assertEqual(index[folder_hash]["share"], "t.me/example_bot?start=folder")

    def test_inherits_beta_access_and_copies_button_and_view_fields(self):
        tree = normalize_tree({
            "name": "Root",
            "children": {
                "private": {
                    "name": "Private",
                    "beta_access": 1,
                    "actions": {
                        "celebrate": {
                            "text": "Celebrate",
                            "callback_data": "do:thing",
                            "button_style": "success",
                            "message_effects": ["🎉"],
                        },
                    },
                    "views": {"done": {"rows": [["celebrate"]]}},
                    "children": {
                        "action": {
                            "name": "Action",
                            "callback_data": "do:thing",
                            "button_style": "success",
                            "button_icon": 42,
                        }
                    },
                }
            },
        })

        index, _ = build_content_index(tree, "example_bot")
        private = index[stable_hash("/private")]
        action_hash = stable_hash("/private/action")
        action_summary = private["children"][action_hash]

        self.assertEqual(action_summary["beta_access"], 1)
        self.assertEqual(action_summary["callback_data"], "do:thing")
        self.assertEqual(action_summary["button_style"], "success")
        self.assertEqual(action_summary["button_icon"], 42)
        self.assertEqual(private["actions"]["celebrate"]["message_effects"], ["🎉"])
        self.assertEqual(private["views"]["done"]["rows"], [["celebrate"]])

    def test_rejects_duplicate_aliases(self):
        tree = {
            "name": "Root",
            "children": {
                "one": {"name": "One", "alias": "same"},
                "two": {"name": "Two", "alias": "same"},
            },
        }

        with self.assertRaisesRegex(ValueError, "Duplicate content alias"):
            build_content_index(tree, "example_bot")

    def test_rejects_a_path_hash_collision(self):
        tree = {
            "name": "Root",
            "children": {"child": {"name": "Child"}},
        }

        with patch("libs.content_index.stable_hash", return_value="collision"):
            with self.assertRaisesRegex(ValueError, "hash collision"):
                build_content_index(tree, "example_bot")

    def test_current_tree_uses_only_fresh_paths_and_keeps_current_aliases(self):
        index, aliases = build_content_index(common_tree, "example_bot")

        expected_root_paths = ["/radio", "/tools", "/games", "/other"]
        root = index[stable_hash("")]
        self.assertEqual(list(root["children"]), [stable_hash(path) for path in expected_root_paths])
        self.assertEqual(aliases["my_data"], stable_hash("/other/my_data"))
        self.assertEqual(aliases["life_grid"], stable_hash("/games/roblox/life_grid"))
        self.assertNotIn(stable_hash("/my_data"), index)
        self.assertNotIn(stable_hash("/web_games"), index)

        nda = index[stable_hash("/other/secret_place")]
        minecraft = index[stable_hash("/other/secret_place/minecraft_server")]
        self.assertEqual(nda["beta_access"], 1)
        self.assertEqual(minecraft["beta_access"], 1)

        for node in index.values():
            if "parent" in node:
                self.assertIn(node["parent"], index)


if __name__ == "__main__":
    unittest.main()
