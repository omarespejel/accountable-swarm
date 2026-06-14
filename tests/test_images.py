from io import BytesIO
from unittest import TestCase

from accountable_swarm.images import _jpeg_size


class ImageHelperTests(TestCase):
    def test_rejects_invalid_jpeg_segment_length(self) -> None:
        data = BytesIO(b"\xff\xd8\xff\xe0\x00\x01")
        with self.assertRaises(ValueError):
            _jpeg_size(data)
