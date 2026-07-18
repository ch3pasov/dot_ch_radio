import io
import unittest
from unittest.mock import AsyncMock, patch

from programs import other


class ImageProcessingTests(unittest.IsolatedAsyncioTestCase):
    async def test_inversion_runs_outside_the_telegram_event_loop(self):
        inverted = io.BytesIO(b"inverted")
        to_thread = AsyncMock(return_value=inverted)

        with patch.object(other.asyncio, "to_thread", new=to_thread):
            result = await other.invert_picture(b"original")

        self.assertIs(result, inverted)
        self.assertEqual(result.name, "inverted.jpg")
        to_thread.assert_awaited_once()
        function, source = to_thread.await_args.args
        self.assertIs(function, other.circle_inversion_bytes)
        self.assertIsInstance(source, io.BytesIO)
        self.assertEqual(source.getvalue(), b"original")
        self.assertEqual(source.name, "photo.jpg")
        self.assertEqual(to_thread.await_args.kwargs, {"version": 2})


if __name__ == "__main__":
    unittest.main()
