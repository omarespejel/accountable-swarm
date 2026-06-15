"""Qwen3-VL bbox parsing and coordinate normalization."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


@dataclass(frozen=True)
class QwenGrounding:
    label: str
    bbox_2d_norm_1000: tuple[int, int, int, int]
    bbox_2d_px: tuple[int, int, int, int]


def parse_qwen_bbox_response(response_text: str, *, image_width: int, image_height: int) -> QwenGrounding:
    """Parse Qwen-style bbox JSON from a response.

    Expected shape:

    ```json
    [{"bbox_2d":[x1,y1,x2,y2],"label":"hazard"}]
    ```

    The bbox is interpreted as Qwen3-VL normalized 0-1000 coordinates and
    rescaled to pixels. Prose-wrapped JSON is accepted; malformed JSON is not.
    """

    parsed = _extract_first_json(response_text)
    if isinstance(parsed, dict):
        item = parsed
    elif isinstance(parsed, list) and parsed:
        item = parsed[0]
    else:
        raise ValueError("Qwen response must be a JSON object or non-empty array")

    if not isinstance(item, dict):
        raise ValueError("Qwen bbox item must be an object")
    if "bbox_2d" not in item:
        raise ValueError("Qwen bbox item missing bbox_2d")
    if "label" not in item:
        raise ValueError("Qwen bbox item missing label")

    label_raw = item["label"]
    if not isinstance(label_raw, str):
        raise ValueError("Qwen label must be a string")
    label = label_raw.strip()
    if not label:
        raise ValueError("Qwen label must be non-empty")

    bbox = item["bbox_2d"]
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise ValueError("bbox_2d must be a list of four numbers")
    norm_bbox = tuple(_as_int_coordinate(value) for value in bbox)
    _validate_norm_bbox(norm_bbox)

    return QwenGrounding(
        label=label,
        bbox_2d_norm_1000=norm_bbox,
        bbox_2d_px=rescale_norm_1000_bbox(norm_bbox, image_width=image_width, image_height=image_height),
    )


def parse_qwen_bbox_optional_response(
    response_text: str, *, image_width: int, image_height: int
) -> QwenGrounding | None:
    """Parse Qwen bbox JSON where an empty array explicitly means no detection."""

    parsed = _extract_first_json(response_text)
    if isinstance(parsed, list) and not parsed:
        return None
    return parse_qwen_bbox_response(response_text, image_width=image_width, image_height=image_height)


def rescale_norm_1000_bbox(
    bbox: tuple[int, int, int, int], *, image_width: int, image_height: int
) -> tuple[int, int, int, int]:
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image dimensions must be positive")
    _validate_norm_bbox(bbox)
    x1, y1, x2, y2 = bbox
    return (
        round(x1 / 1000 * image_width),
        round(y1 / 1000 * image_height),
        round(x2 / 1000 * image_width),
        round(y2 / 1000 * image_height),
    )


def _extract_first_json(text: str) -> Any:
    decoder = json.JSONDecoder()
    starts = [idx for idx, char in enumerate(text) if char in "[{"]
    for start in starts:
        try:
            value, _ = decoder.raw_decode(text[start:])
            return value
        except json.JSONDecodeError:
            continue
    raise ValueError("no valid JSON object or array found in Qwen response")


def _as_int_coordinate(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("bbox coordinate must be numeric")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ValueError("bbox coordinate must be an integer in normalized 0-1000 space")


def _validate_norm_bbox(bbox: tuple[int, int, int, int]) -> None:
    x1, y1, x2, y2 = bbox
    if min(bbox) < 0 or max(bbox) > 1000:
        raise ValueError("normalized bbox coordinates must be within 0-1000")
    if x1 >= x2 or y1 >= y2:
        raise ValueError("bbox must have positive area")
