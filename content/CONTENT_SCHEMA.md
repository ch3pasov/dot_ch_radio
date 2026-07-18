# Content Tree DSL

`content/content.py` may use plain dictionaries or helpers from
`libs.content_schema`. `normalize_tree()` copies and validates the complete
tree at import time; handlers render the normalized data without keeping a
user's current page or any other navigation state.

```python
from libs.content_schema import folder, link, copy_button, web_app, user_profile

folder(
    "🧪 Beta tools",
    id="beta_tools",
    beta_access=1,
    children_columns=2,
    children=[
        link("Docs", "https://example.com", id="docs"),
        copy_button("Copy token", "abc123", id="copy_token", button_style="success"),
        web_app(
            "Open app",
            "https://example.com/app",
            id="app",
            button_style="primary",
            button_icon=123456789,
        ),
    ],
)
```

## Node fields

- `id`: path segment when `children` is written as a list. It is removed from
  the normalized node; route hashes still derive from the actual tree path.
- `name`: visible title and default button label.
- `description`: message body below the title. Markdown is used by default.
- `parse_mode`: text parser override such as `"markdown"`, `"html"`, or `None`.
- `children`: legacy `{id: node}` mapping or a list of nodes with `id`.
- `children_columns`: number of child buttons in a row, from 1 through 8.
- `children_button_style`: default style for immediate children that do not
  specify their own style. It does not flow through grandchildren.
- `beta_access`: inherited visibility restriction.
- `alias`: `/start` deep-link alias.
- `refresh`: adds the configured refresh navigation button.
- `disable_web_page_preview`: disables the node's link preview.

## Telegram media

Use `telegram_file_id` to attach media already uploaded to Telegram. Runtime
code does not download archive-chat files or keep `chat_id` / `message_id`
references. Upload new media manually and store only its Bot API-style
`file_id` in the node.

## Button presentation

- `button_text`: label override; `name` remains the page title. Standalone UI
  specs may use `text` instead.
- `button_style`: `primary`, `success`, or `danger`. The legacy alias
  `button_color` is normalized to this field.
- `button_icon`: positive custom-emoji document ID. The legacy alias
  `custom_emoji_id` is normalized to this field.
- `break_before` / `break_after`: boolean forced row breaks for content
  children.

When `button_icon` is present, the renderer removes one redundant leading
emoji or symbol cluster plus its following whitespace from the `name`/`text`
label. This keeps a fallback title such as `"🗑 Удалить"` readable without a
custom icon while rendering it as `"Удалить"` beside the custom icon. Textual
prefixes such as `"SF7"` are not removed. An explicitly supplied
`button_text` is always rendered verbatim and disables this de-duplication.

Color is optional and intentionally sparse in the production tree. Leave
folders, navigation, catalogs, and groups of equal choices neutral. Use
`primary` for the page's main call to action, `success` for a safe action that
delivers a positive result, and `danger` only for destructive flows.
`children_button_style` remains available for deliberately homogeneous groups,
but should not be used merely to color every child.

Invalid styles, non-positive icons, `children_columns` outside 1–8, rows wider
than 8, markups larger than 100 buttons, and callback payloads larger than 64
UTF-8 bytes are rejected before rendering.

## Telegram actions

A button may define one action target:

- `url`: open an external URL.
- `copy_text`: copy text to the clipboard.
- `web_app_url`: open a WebView.
- `simple_web_app_url`: open a Simple WebView.
- `user_id` with `button_type="user_profile"`: open a user profile.
- `switch_inline_query`: open inline mode; `same_peer=True` keeps the peer.
- `switch_inline_query_current_chat`: open inline mode in the current chat.
- `callback_data`: dispatch a stateless application callback, at most 64 bytes.

Content children without an explicit target receive their generated
`id=<route-hash>` callback from the renderer.

## Hidden actions and named views

Workflow UI that is not part of the route tree lives next to its page:

```python
{
    "name": "My data",
    "actions": {
        "takeout": {
            "text": "Takeout",
            "callback_data": "data_rights:takeout",
            "button_style": "success",
            "message_effects": ["🎉", "👍"],
        },
        "copy_result": {
            "text": "Copy result",
            "copy_text": "stored: 0 B",
        },
    },
    "views": {
        "result": {
            "rows": [
                ["copy_result"],
                ["takeout", {"text": "Docs", "url": "https://example.com"}],
            ],
        },
    },
}
```

- `actions` is an `{action_id: button spec}` mapping. Actions do not create
  routes and do not appear unless a page or workflow chooses a view.
- `views` is `{view_id: {rows: [[...]]}}`. Each cell is an action ID from the
  same node or a complete inline button spec. Unknown IDs fail normalization.
- `message_effects` is a non-empty priority-ordered `list[str]`. It is allowed
  only on named actions that send a new message or document. Page edits and
  inline view specs cannot request an effect.
- Effect IDs are resolved from Telegram's catalogue in process memory. If the
  catalogue is unavailable, no effect is sent. Only an effect-specific RPC
  rejection is retried without the effect.

## Shared navigation UI

The root may define common presentation once:

```python
"navigation_ui": {
    "back": {"text": "⬅️ Назад", "button_icon": 123},
    "share": {"text": "🔗 Поделиться", "button_icon": 456},
    "refresh": {"text": "🔄 Обновить", "button_icon": 789},
}
```

Only `back`, `share`, and `refresh` are accepted. These specs intentionally
omit action targets; the renderer supplies the current parent callback, share
URL, or refresh callback. `navigation_ui` is root-only and is copied into the
route renderer as common static configuration.

## Renderer API

`libs.telegram_ui` provides the common Telethon 1.43.2 implementation:

- `build_button(spec, default_callback_data=..., default_url=...)`;
- `build_child_rows(children, columns=..., callback_data_for=..., include=...)`;
- `build_view_rows(view, actions)`.

The functions return Telethon button objects/rows and repeat Telegram limit
checks at the rendering boundary. Tests use `MemorySession` and never connect
to Telegram.
