import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from programs.radio_socket_guard import (
    count_open_socket_descriptors,
    should_recycle_socket_connection,
)


class RadioSocketGuardTests(unittest.TestCase):
    def test_counts_only_socket_descriptors(self):
        with TemporaryDirectory() as temporary_directory:
            descriptors = Path(temporary_directory)
            (descriptors / "socket").symlink_to("socket:[123]")
            (descriptors / "pipe").symlink_to("pipe:[456]")
            (descriptors / "file").symlink_to("/tmp/example")

            self.assertEqual(count_open_socket_descriptors(descriptors), 1)

    def test_missing_procfs_disables_counting_safely(self):
        self.assertIsNone(
            count_open_socket_descriptors(Path("/definitely/missing/fd-directory"))
        )

    def test_recycles_at_threshold_or_while_reconnect_is_pending(self):
        self.assertFalse(
            should_recycle_socket_connection(
                255,
                reconnect_pending=False,
                threshold=256,
            )
        )
        self.assertTrue(
            should_recycle_socket_connection(
                256,
                reconnect_pending=False,
                threshold=256,
            )
        )
        self.assertTrue(
            should_recycle_socket_connection(
                3,
                reconnect_pending=True,
                threshold=256,
            )
        )

    def test_rejects_non_positive_threshold(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            should_recycle_socket_connection(
                0,
                reconnect_pending=False,
                threshold=0,
            )


if __name__ == "__main__":
    unittest.main()
