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
    score_milli: int = 1000


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
    score_milli = _score_milli_from_item(item)

    return QwenGrounding(
        label=label,
        bbox_2d_norm_1000=norm_bbox,
        bbox_2d_px=rescale_norm_1000_bbox(norm_bbox, image_width=image_width, image_height=image_height),
        score_milli=score_milli,
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
    px_x1, px_x2 = _rescale_positive_interval(x1, x2, image_width)
    px_y1, px_y2 = _rescale_positive_interval(y1, y2, image_height)
    return (px_x1, px_y1, px_x2, px_y2)


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


def _score_milli_from_item(item: dict[str, Any]) -> int:
    for key in ("score_milli", "confidence_milli"):
        if key in item:
            return _as_direct_score_milli(item[key], field_name=key)
    for key in ("score", "confidence"):
        if key in item:
            return _as_unit_score_milli(item[key], field_name=key)
    return 1000


def _as_direct_score_milli(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer in 0-1000")
    _validate_score_milli(value, field_name=field_name)
    return value


def _as_unit_score_milli(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric in 0-1")
    if value < 0 or value > 1:
        raise ValueError(f"{field_name} must be within 0-1")
    return round(value * 1000)


def _validate_score_milli(value: int, *, field_name: str) -> None:
    if value < 0 or value > 1000:
        raise ValueError(f"{field_name} must be within 0-1000")


def _rescale_positive_interval(start_norm: int, end_norm: int, size_px: int) -> tuple[int, int]:
    start_px = round(start_norm / 1000 * size_px)
    end_px = round(end_norm / 1000 * size_px)
    start_px = min(max(start_px, 0), size_px)
    end_px = min(max(end_px, 0), size_px)
    if start_px < end_px:
        return start_px, end_px
    if start_px < size_px:
        return start_px, min(size_px, start_px + 1)
    return max(0, size_px - 1), size_px


def _validate_norm_bbox(bbox: tuple[int, int, int, int]) -> None:
    x1, y1, x2, y2 = bbox
    if min(bbox) < 0 or max(bbox) > 1000:
        raise ValueError("normalized bbox coordinates must be within 0-1000")
    if x1 >= x2 or y1 >= y2:
        raise ValueError("bbox must have positive area")
