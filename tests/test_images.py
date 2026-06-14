from io import BytesIO
from unittest import TestCase

from accountable_swarm.images import _jpeg_size


class ImageHelperTests(TestCase):
    def test_rejects_invalid_jpeg_segment_length(self) -> None:
        data = BytesIO(b"\xff\xd8\xff\xe0\x00\x01")
        with self.assertRaises(ValueError):
            _jpeg_size(data)

    def test_rejects_truncated_jpeg_sof_dimensions(self) -> None:
        data = BytesIO(b"\xff\xd8\xff\xc0\x00\x11\x08\x00")
        with self.assertRaises(ValueError):
            _jpeg_size(data)
