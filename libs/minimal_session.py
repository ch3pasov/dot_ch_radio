"""Telethon sessions without persistent peer or uploaded-file caches.

Telethon needs a session file to keep the service account authorized and to
resume receiving updates.  Its optional ``entities`` and ``sent_files``
tables are not required for that purpose and may contain user-related data.
"""

from telethon.sessions import SQLiteSession


class MinimalSQLiteSession(SQLiteSession):
    """Keep only the state Telethon needs to authenticate and receive updates."""

    def __init__(self, session_id):
        super().__init__(session_id)
        self.save_entities = False
        self._clear_optional_caches()

    def _clear_optional_caches(self):
        # These tables are part of Telethon's own SQLite schema.  Clearing them
        # preserves the auth key and update state while removing cached peers,
        # names, usernames, phone numbers and sent-file fingerprints.
        self._execute("delete from entities")
        self._execute("delete from sent_files")
        self.save()

    def cache_file(self, md5_digest, file_size, instance):
        """Deliberately avoid persisting fingerprints of uploaded files."""

        return None
