import unittest

from libs.content_schema import (
    MAX_BUTTONS_PER_MARKUP,
    normalize_tree,
    validate_aliases,
    validate_button_icon,
    validate_button_style,
    validate_callback_data,
    validate_children_columns,
)


class PrimitiveValidationTests(unittest.TestCase):
    def test_button_style_is_normalized_and_unknown_style_is_rejected(self):
        self.assertEqual(validate_button_style("PRIMARY"), "primary")
        with self.assertRaisesRegex(ValueError, "Unknown button_style"):
            validate_button_style("purple")
        with self.assertRaises(TypeError):
            validate_button_style(1)

    def test_button_icon_is_a_positive_document_id(self):
        self.assertEqual(validate_button_icon("123456"), 123456)
        self.assertEqual(validate_button_icon(987654), 987654)
        for invalid in (0, -1, True, "figure.run", 1.5):
            with self.subTest(invalid=invalid), self.assertRaises((TypeError, ValueError)):
                validate_button_icon(invalid)

    def test_title_icon_is_validated_like_a_button_icon(self):
        tree = normalize_tree({"name": "Page", "title_icon": "123456", "parse_mode": "html"})
        self.assertEqual(tree["title_icon"], 123456)
        with self.assertRaises((TypeError, ValueError)):
            normalize_tree({"name": "Page", "title_icon": 0, "parse_mode": "html"})
        with self.assertRaisesRegex(ValueError, "parse_mode='html'"):
            normalize_tree({"name": "Page", "title_icon": 123456})

    def test_callback_limit_is_counted_in_utf8_bytes(self):
        self.assertEqual(validate_callback_data("🔥" * 16), "🔥" * 16)
        with self.assertRaisesRegex(ValueError, "64-byte"):
            validate_callback_data("🔥" * 17)

    def test_children_columns_must_fit_one_telegram_row(self):
        self.assertEqual(validate_children_columns(1), 1)
        self.assertEqual(validate_children_columns(8), 8)
        for invalid in (0, 9, True, "2"):
            with self.subTest(invalid=invalid), self.assertRaises((TypeError, ValueError)):
                validate_children_columns(invalid)

    def test_aliases_are_non_empty_unique_strings(self):
        self.assertEqual(
            validate_aliases(["invert_picture", "inversion"]),
            ["invert_picture", "inversion"],
        )
        for invalid in ([], "inversion", [""], ["with space"], [1], ["same", "same"]):
            with self.subTest(invalid=invalid), self.assertRaises((TypeError, ValueError)):
                validate_aliases(invalid)


class TreeNormalizationTests(unittest.TestCase):
    def test_alias_field_was_replaced_by_aliases(self):
        tree = normalize_tree({"name": "root", "aliases": ["root", "home"]})
        self.assertEqual(tree["aliases"], ["root", "home"])

        with self.assertRaisesRegex(ValueError, "renamed to aliases"):
            normalize_tree({"name": "root", "alias": "root"})

    def test_parent_default_style_applies_only_to_direct_children(self):
        tree = normalize_tree(
            {
                "name": "root",
                "children_button_style": "PRIMARY",
                "children": {
                    "folder": {
                        "name": "Folder",
                        "children": {"leaf": {"name": "Leaf"}},
                    },
                    "explicit": {"name": "Explicit", "button_style": "success"},
                    "legacy": {"name": "Legacy", "button_color": "danger"},
                },
            }
        )

        self.assertEqual(tree["children"]["folder"]["button_style"], "primary")
        self.assertNotIn("button_style", tree["children"]["folder"]["children"]["leaf"])
        self.assertEqual(tree["children"]["explicit"]["button_style"], "success")
        self.assertEqual(tree["children"]["legacy"]["button_style"], "danger")
        self.assertNotIn("button_color", tree["children"]["legacy"])

    def test_actions_views_and_root_navigation_are_normalized(self):
        tree = normalize_tree(
            {
                "name": "root",
                "navigation_ui": {
                    "back": {"text": "Back", "button_style": "PRIMARY"},
                    "share": {"text": "Share", "custom_emoji_id": "42"},
                    "refresh": {"text": "Refresh"},
                },
                "actions": {
                    "send": {
                        "text": "Send",
                        "callback_data": "data:send",
                        "message_effects": ["🎉", "👍"],
                    },
                    "copy": {"text": "Copy", "copy_text": "zero", "button_style": "success"},
                },
                "views": {
                    "result": {
                        "rows": [
                            ["copy"],
                            ["send", {"text": "Docs", "url": "https://example.com"}],
                        ]
                    }
                },
            }
        )

        self.assertEqual(tree["navigation_ui"]["back"]["button_style"], "primary")
        self.assertEqual(tree["navigation_ui"]["share"]["button_icon"], 42)
        self.assertEqual(tree["actions"]["send"]["message_effects"], ["🎉", "👍"])
        self.assertEqual(tree["views"]["result"]["rows"][0], ["copy"])

    def test_message_effects_are_restricted_to_named_actions(self):
        with self.assertRaisesRegex(ValueError, "only allowed"):
            normalize_tree({"name": "root", "message_effects": ["🎉"]})
        with self.assertRaisesRegex(ValueError, "only allowed"):
            normalize_tree(
                {
                    "name": "root",
                    "actions": {"ok": {"text": "OK", "callback_data": "ok"}},
                    "views": {
                        "bad": {"rows": [[{"text": "Bad", "callback_data": "bad", "message_effects": ["🎉"]}]]}
                    },
                }
            )

    def test_invalid_action_and_view_references_fail_early(self):
        with self.assertRaisesRegex(ValueError, "Telegram action target"):
            normalize_tree({"name": "root", "actions": {"noop": {"text": "No-op"}}})
        with self.assertRaisesRegex(ValueError, "unknown action"):
            normalize_tree(
                {
                    "name": "root",
                    "actions": {},
                    "views": {"bad": {"rows": [["missing"]]}},
                }
            )

    def test_view_enforces_row_and_markup_limits(self):
        actions = {
            f"a{number}": {"text": str(number), "callback_data": f"a:{number}"}
            for number in range(MAX_BUTTONS_PER_MARKUP + 1)
        }
        with self.assertRaisesRegex(ValueError, "8-button"):
            normalize_tree(
                {
                    "name": "root",
                    "actions": actions,
                    "views": {"wide": {"rows": [[f"a{i}" for i in range(9)]]}},
                }
            )
        with self.assertRaisesRegex(ValueError, "100-button"):
            normalize_tree(
                {
                    "name": "root",
                    "actions": actions,
                    "views": {
                        "large": {
                            "rows": [
                                [f"a{i}" for i in range(start, min(start + 8, len(actions)))]
                                for start in range(0, len(actions), 8)
                            ]
                        }
                    },
                }
            )

    def test_navigation_ui_is_root_only_and_has_known_entries(self):
        with self.assertRaisesRegex(ValueError, "only allowed on the root"):
            normalize_tree(
                {
                    "name": "root",
                    "children": {
                        "nested": {"name": "Nested", "navigation_ui": {"back": {"text": "Back"}}}
                    },
                }
            )
        with self.assertRaisesRegex(ValueError, "Unknown navigation_ui"):
            normalize_tree({"name": "root", "navigation_ui": {"home": {"text": "Home"}}})
        with self.assertRaisesRegex(ValueError, "Missing navigation_ui"):
            normalize_tree(
                {
                    "name": "root",
                    "navigation_ui": {
                        "back": {"text": "Back"},
                        "share": {"text": "Share"},
                    },
                }
            )

    def test_callback_and_layout_validation_runs_for_content_nodes(self):
        with self.assertRaisesRegex(ValueError, "64-byte"):
            normalize_tree(
                {
                    "name": "root",
                    "children": {"bad": {"name": "Bad", "callback_data": "🔥" * 17}},
                }
            )
        with self.assertRaisesRegex(ValueError, "between 1 and 8"):
            normalize_tree({"name": "root", "children_columns": 10})
        with self.assertRaisesRegex(TypeError, "break_before"):
            normalize_tree({"name": "root", "break_before": 1})


if __name__ == "__main__":
    unittest.main()
