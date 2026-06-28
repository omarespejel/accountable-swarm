from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from accountable_swarm.images import _image_kind, _jpeg_size, image_data_url


class ImageHelperTests(TestCase):
    def test_image_kind_detects_png_and_jpeg_headers(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            png = root / "sample.png"
            jpg = root / "sample.jpg"
            invalid = root / "sample.txt"
            png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 12)
            jpg.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 12)
            invalid.write_bytes(b"not an image")

            self.assertEqual(_image_kind(png), "png")
            self.assertEqual(_image_kind(jpg), "jpeg")
            self.assertIsNone(_image_kind(invalid))

    def test_image_data_url_accepts_only_png_and_jpeg(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            png = root / "sample.png"
            invalid = root / "sample.ppm"
            png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 12)
            invalid.write_bytes(b"P3\n1 1\n255\n0 0 0\n")

            self.assertTrue(image_data_url(png).startswith("data:image/png;base64,"))
            with self.assertRaisesRegex(ValueError, "PNG or JPEG"):
                image_data_url(invalid)

    def test_rejects_invalid_jpeg_segment_length(self) -> None:
        data = BytesIO(b"\xff\xd8\xff\xe0\x00\x01")
        with self.assertRaises(ValueError):
            _jpeg_size(data)

    def test_rejects_truncated_jpeg_sof_dimensions(self) -> None:
        data = BytesIO(b"\xff\xd8\xff\xc0\x00\x11\x08\x00")
        with self.assertRaises(ValueError):
            _jpeg_size(data)
