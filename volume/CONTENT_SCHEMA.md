# Content Tree DSL

`volume/content.py` may still use plain dictionaries, but new sections can use helpers from `volume.content_schema`.

```python
from volume.content_schema import folder, link, copy_button, web_app, user_profile

folder(
    "🧪 Beta tools",
    id="beta_tools",
    beta_access=1,
    children_columns=2,
    children=[
        link("Docs", "https://example.com", id="docs", button_color="primary"),
        copy_button("Copy token", "abc123", id="copy_token", button_color="success"),
        web_app("Open app", "https://example.com/app", id="app", custom_emoji_id=123456789),
    ],
)
```

## Node fields

- `id`: stable path segment when children are written as a list.
- `name`: visible title and default button label.
- `description`: message body below the title. Markdown is used by default.
- `parse_mode`: override text parser for this node, for example `"markdown"`, `"html"`, or `None`.
- `children`: either the legacy `{id: node}` dict or a list of nodes with `id`.
- `children_columns`: how many child buttons to place in one row. Defaults to `1`.
- `beta_access`: inherited by descendants; hidden from non-beta users.
- `alias`: stable `/start` deep-link alias.
- `refresh`: adds a refresh button.
- `disable_web_page_preview`: disables link previews for the node message.

## Telegram media

`volume/telegram_assets.json` is a local index of files that are already stored in Telegram. Runtime code never downloads bucket files. It prefers Bot API-style `file_id`, attaches the matching Telegram media, and removes old hidden bucket-preview links from descriptions.

For new media, upload the file to Telegram manually and add its `file_id` to `volume/telegram_assets.json`, or set `telegram_file_id` directly on a content node. Legacy `chat_id` / `message_id` refs may remain as fallback and for one-time migration with `scripts/migrate_telegram_assets_to_file_ids.py`.

## Button fields

- `button_text`: label override for the button while keeping `name` as page title.
- `button_style` / `button_color`: `primary`, `success`, or `danger`.
- `button_icon` / `custom_emoji_id`: custom emoji document id for Telegram clients that support button icons.
- `break_before` / `break_after`: force row breaks around a button.

## Action nodes

- `url`: opens a URL.
- `copy_text`: renders a copy-to-clipboard button.
- `web_app_url`: renders a WebView button.
- `simple_web_app_url`: renders a Simple WebView button.
- `user_id` with `button_type="user_profile"`: opens a user profile.
- `switch_inline_query`: opens inline mode, optionally with `same_peer=1`.
- `switch_inline_query_current_chat`: opens inline mode in the current chat.

Telegram supports semantic button colors via `primary`, `success`, and `danger`; arbitrary RGB colors are not exposed to bot inline keyboards.
