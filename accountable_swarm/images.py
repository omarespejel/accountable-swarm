"""Small image helpers for GO-gate scripts.

This module intentionally uses the standard library only. The first gate should
not depend on heavyweight computer-vision packages.
"""

from __future__ import annotations

from pathlib import Path
import base64
import imghdr
import struct
from typing import BinaryIO


def image_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as f:
        header = f.read(32)
        f.seek(0)
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return _png_size(header)
        if header.startswith(b"P3") or header.startswith(b"P6"):
            return _ppm_size(f)
        if header.startswith(b"\xff\xd8"):
            return _jpeg_size(f)
    raise ValueError(f"unsupported image format for dimension parsing: {path}")


def image_data_url(path: Path) -> str:
    kind = imghdr.what(path)
    if kind not in {"png", "jpeg"}:
        raise ValueError("DashScope mode currently requires a PNG or JPEG image")
    mime = "image/jpeg" if kind == "jpeg" else "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _png_size(header: bytes) -> tuple[int, int]:
    if len(header) < 24:
        raise ValueError("invalid PNG header")
    width, height = struct.unpack(">II", header[16:24])
    return int(width), int(height)


def _ppm_size(f: BinaryIO) -> tuple[int, int]:
    tokens: list[str] = []
    for raw_line in f:
        line = raw_line.decode("ascii").strip()
        if not line or line.startswith("#"):
            continue
        tokens.extend(line.split())
        if len(tokens) >= 4:
            break
    if len(tokens) < 4 or tokens[0] not in {"P3", "P6"}:
        raise ValueError("invalid PPM header")
    return int(tokens[1]), int(tokens[2])


def _jpeg_size(f: BinaryIO) -> tuple[int, int]:
    f.read(2)
    while True:
        marker_start = f.read(1)
        if marker_start != b"\xff":
            raise ValueError("invalid JPEG marker")
        marker = f.read(1)
        while marker == b"\xff":
            marker = f.read(1)
        if marker in {b"\xc0", b"\xc1", b"\xc2", b"\xc3"}:
            f.read(3)
            height, width = struct.unpack(">HH", f.read(4))
            return int(width), int(height)
        segment_len_raw = f.read(2)
        if len(segment_len_raw) != 2:
            raise ValueError("invalid JPEG segment")
        segment_len = struct.unpack(">H", segment_len_raw)[0]
        f.seek(segment_len - 2, 1)
