"""Shared strict-ish JSON extraction for QwenGuard validators."""

from __future__ import annotations

import json
from typing import Any


def extract_first_json_object(text: str) -> dict[str, Any]:
    """Extract the first JSON object from a model response."""

    decoder = json.JSONDecoder()
    starts = [idx for idx, char in enumerate(text) if char == "{"]
    for start in starts:
        try:
            value, _ = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("no valid JSON object found")


def string_field(value: dict[str, Any], key: str) -> str:
    raw = value.get(key)
    if not isinstance(raw, str):
        raise ValueError(f"{key} must be a string")
    stripped = raw.strip()
    if not stripped:
        raise ValueError(f"{key} must be non-empty")
    return stripped


def string_list_field(value: dict[str, Any], key: str, *, required: bool = False) -> tuple[str, ...]:
    raw = value.get(key)
    if raw is None and not required:
        return ()
    if not isinstance(raw, list):
        raise ValueError(f"{key} must be a list of strings")
    items: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{key}[{index}] must be a non-empty string")
        items.append(item.strip())
    return tuple(items)


def int_milli_field(value: dict[str, Any], key: str, *, default: int | None = None) -> int:
    raw = value.get(key, default)
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError(f"{key} must be an integer in 0-1000")
    if raw < 0 or raw > 1000:
        raise ValueError(f"{key} must be within 0-1000")
    return raw


def reject_unexpected_keys(value: dict[str, Any], allowed: set[str]) -> None:
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise ValueError(f"unexpected keys: {', '.join(unexpected)}")
