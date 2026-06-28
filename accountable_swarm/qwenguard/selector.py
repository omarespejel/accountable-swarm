"""Set-of-Mark selector validation for QwenGuard.

Qwen selects a local mark identifier. It does not directly create motor
commands or trusted 3D grasp poses.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from typing import Any

from accountable_swarm.qwenguard.json_extract import (
    extract_first_json_object,
    int_milli_field,
    reject_unexpected_keys,
    string_field,
    string_list_field,
)
from accountable_swarm.trace.models import reject_raw_floats

RELATIONS = {
    "left_of",
    "right_of",
    "between",
    "nearest_bin",
    "marked",
    "odd_one_out",
    "named_target",
}


@dataclass(frozen=True)
class CandidateMark:
    mark_id: str
    label: str
    bbox_2d_norm_1000: tuple[int, int, int, int]

    def __post_init__(self) -> None:
        if not self.mark_id.strip():
            raise ValueError("mark_id must be non-empty")
        if not self.mark_id.isascii():
            raise ValueError("mark_id must be ASCII")
        if not self.label.strip():
            raise ValueError("label must be non-empty")
        _validate_norm_bbox(self.bbox_2d_norm_1000, "candidate bbox")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["bbox_2d_norm_1000"] = list(self.bbox_2d_norm_1000)
        return value


@dataclass(frozen=True)
class SelectorResult:
    target_mark_id: str
    target_label: str
    bbox_2d_norm_1000: tuple[int, int, int, int]
    relation: str
    reference_mark_ids: tuple[str, ...]
    confidence_milli: int
    evidence: str

    def __post_init__(self) -> None:
        if not self.target_mark_id.strip():
            raise ValueError("target_mark_id must be non-empty")
        if not self.target_label.strip():
            raise ValueError("target_label must be non-empty")
        if self.relation not in RELATIONS:
            raise ValueError(f"unsupported relation: {self.relation}")
        if isinstance(self.confidence_milli, bool) or not isinstance(self.confidence_milli, int):
            raise TypeError("confidence_milli must be an integer")
        if self.confidence_milli < 0 or self.confidence_milli > 1000:
            raise ValueError("confidence_milli must be within 0-1000")
        if not self.evidence.strip():
            raise ValueError("evidence must be non-empty")
        if len(self.evidence) > 512:
            raise ValueError("evidence must be 512 characters or fewer")
        if any(ord(char) < 32 and char not in "\n\r\t" for char in self.evidence):
            raise ValueError("evidence contains control characters")
        _validate_norm_bbox(self.bbox_2d_norm_1000, "selector bbox")

    def to_command(self) -> dict[str, Any]:
        evidence_bytes = self.evidence.encode("utf-8")
        command = {
            "type": "qwenguard_select_target",
            "target_mark_id": self.target_mark_id,
            "target_label": self.target_label,
            "bbox_2d_norm_1000": list(self.bbox_2d_norm_1000),
            "relation": self.relation,
            "reference_mark_ids": list(self.reference_mark_ids),
            "confidence_milli": self.confidence_milli,
            "evidence_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
            "evidence_char_count": len(self.evidence),
        }
        reject_raw_floats(command, "$.selector_command")
        return command


def parse_selector_response(response_text: str, *, candidates: tuple[CandidateMark, ...]) -> SelectorResult:
    """Parse and validate Qwen's marked-candidate selection."""

    if not candidates:
        raise ValueError("at least one candidate mark is required")
    candidate_by_id = {candidate.mark_id: candidate for candidate in candidates}
    if len(candidate_by_id) != len(candidates):
        raise ValueError("candidate mark IDs must be unique")

    value = extract_first_json_object(response_text)
    reject_unexpected_keys(
        value,
        {
            "target_mark_id",
            "target_id",
            "target_label",
            "relation",
            "reference_mark_ids",
            "reference_objects",
            "confidence_milli",
            "evidence",
        },
    )
    mark_id = value.get("target_mark_id", value.get("target_id"))
    if not isinstance(mark_id, str) or not mark_id.strip():
        raise ValueError("target_mark_id must be a non-empty string")
    mark_id = mark_id.strip()
    if mark_id not in candidate_by_id:
        raise ValueError(f"unknown target_mark_id: {mark_id}")
    candidate = candidate_by_id[mark_id]

    relation = string_field(value, "relation")
    if relation not in RELATIONS:
        raise ValueError(f"unsupported relation: {relation}")
    confidence_milli = int_milli_field(value, "confidence_milli")
    evidence = string_field(value, "evidence")
    target_label = candidate.label.strip()
    raw_target_label = value.get("target_label")
    if raw_target_label is not None:
        if not isinstance(raw_target_label, str) or raw_target_label.strip() != target_label:
            raise ValueError("target_label must match the selected candidate label")

    references = _reference_mark_ids(value)
    for reference in references:
        if reference not in candidate_by_id:
            raise ValueError(f"unknown reference mark ID: {reference}")
    if relation == "between" and (len(references) != 2 or len(set(references)) != 2):
        raise ValueError("relation between requires exactly two distinct reference marks")
    if relation in {"left_of", "right_of", "nearest_bin"} and not references:
        raise ValueError(f"relation {relation} requires at least one reference mark")

    return SelectorResult(
        target_mark_id=mark_id,
        target_label=target_label,
        bbox_2d_norm_1000=candidate.bbox_2d_norm_1000,
        relation=relation,
        reference_mark_ids=references,
        confidence_milli=confidence_milli,
        evidence=evidence,
    )


def fixture_cube_candidates() -> tuple[CandidateMark, ...]:
    """Return a deterministic marked-cube scene for no-hardware tests."""

    return (
        CandidateMark(mark_id="A", label="red cube left of green cube", bbox_2d_norm_1000=(150, 390, 315, 690)),
        CandidateMark(mark_id="B", label="green cube", bbox_2d_norm_1000=(405, 390, 570, 690)),
        CandidateMark(mark_id="C", label="red cube right of green cube", bbox_2d_norm_1000=(660, 390, 825, 690)),
    )


def _reference_mark_ids(value: dict[str, Any]) -> tuple[str, ...]:
    direct = string_list_field(value, "reference_mark_ids")
    if direct:
        return direct
    raw_objects = value.get("reference_objects")
    if raw_objects is None:
        return ()
    if not isinstance(raw_objects, list):
        raise ValueError("reference_objects must be a list")
    references: list[str] = []
    for index, item in enumerate(raw_objects):
        if not isinstance(item, dict):
            raise ValueError(f"reference_objects[{index}] must be an object")
        raw = item.get("mark_id", item.get("object_id"))
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError(f"reference_objects[{index}] must include mark_id")
        references.append(raw.strip())
    return tuple(references)


def _validate_norm_bbox(bbox: tuple[int, int, int, int], name: str) -> None:
    if len(bbox) != 4:
        raise ValueError(f"{name} must have four coordinates")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in bbox):
        raise TypeError(f"{name} coordinates must be integers")
    x1, y1, x2, y2 = bbox
    if min(bbox) < 0 or max(bbox) > 1000:
        raise ValueError(f"{name} coordinates must be within 0-1000")
    if x1 >= x2 or y1 >= y2:
        raise ValueError(f"{name} must have positive area")
