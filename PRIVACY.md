# Application-side user data

`dot_ch_radio` has no database, user profiles, request history, per-user
settings, navigation state or analytics store.

The two Telethon accounts still require SQLite session files under
`volume/sessions/`. `MinimalSQLiteSession` preserves only authentication and
update cursors. Telethon's optional persistent entity cache (peer IDs, names,
usernames and phone numbers) and sent-file cache are disabled and cleared at
every process start.

Handlers may use the sender/chat ID from the current Telegram update to answer
that update. They must not write it, message text, media or derived identifiers
to application logs or files. User-supplied media processing stays in memory;
uploads must use `allow_cache=False`.

The takeout ZIP and deletion receipt are deterministic in-memory artifacts.
They contain no user ID, name or request timestamp and are not written to the
bot filesystem.

Telegram itself transports and retains chats, documents and service data under
Telegram's own settings and policies. The bot's application-side takeout and
deletion flow does not claim to delete Telegram's copy of a conversation.
