import tempfile
import unittest
from pathlib import Path

from telethon.tl.types import InputDocument

from libs.minimal_session import MinimalSQLiteSession


class MinimalSessionTests(unittest.TestCase):
    def test_optional_entity_and_sent_file_caches_are_cleared(self):
        with tempfile.TemporaryDirectory() as tmp:
            session_path = str(Path(tmp) / "test_session")
            seed = MinimalSQLiteSession(session_path)
            seed._execute(
                "insert into entities values (?, ?, ?, ?, ?, ?)",
                42,
                99,
                "some_user",
                12345,
                "Some User",
                1,
            )
            seed.save()
            seed.close()

            hardened = MinimalSQLiteSession(session_path)
            self.assertFalse(hardened.save_entities)
            self.assertEqual(hardened._execute("select count(*) from entities")[0], 0)
            self.assertEqual(hardened._execute("select count(*) from sent_files")[0], 0)

            hardened.cache_file(b"digest", 1, InputDocument(1, 2, b""))
            self.assertEqual(hardened._execute("select count(*) from sent_files")[0], 0)
            hardened.close()


if __name__ == "__main__":
    unittest.main()
