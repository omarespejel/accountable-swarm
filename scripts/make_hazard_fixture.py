#!/usr/bin/env python3
"""Generate a deterministic PNG hazard marker fixture."""

from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("--size", type=int, default=64)
    args = parser.parse_args()

    if args.size < 8:
        raise SystemExit("--size must be at least 8")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(make_png(args.size, args.size))
    print(f"wrote {args.out}")
    return 0


def make_png(width: int, height: int) -> bytes:
    rows = []
    for y in range(height):
        row = bytearray([0])  # filter type 0
        for x in range(width):
            inside = width // 4 <= x < 3 * width // 4 and height // 4 <= y < 3 * height // 4
            row.extend((255, 0, 0) if inside else (255, 255, 255))
        rows.append(bytes(row))
    raw = b"".join(rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(raw, level=9))
        + _chunk(b"IEND", b"")
    )


def _chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


if __name__ == "__main__":
    raise SystemExit(main())
