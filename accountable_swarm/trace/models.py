"""Deterministic DecisionTrace data model.

The trace format deliberately avoids wall-clock timestamps and host-specific
paths. Event hashes are computed from canonical JSON with sorted keys and no
whitespace, so replay can recompute the same bytes on another machine.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Any

GENESIS_SHA = "0" * 64
TRACE_SCHEMA_VERSION = "decisiontrace.v1"


def canonical_json(value: Any) -> str:
    """Return byte-stable JSON for trace hashing."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_canonical(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PerceptionEvent:
    """Validated semantic perception result for one frame/keyframe."""

    event_id: str
    source: str
    image_width: int
    image_height: int
    label: str
    bbox_2d_norm_1000: tuple[int, int, int, int]
    bbox_2d_px: tuple[int, int, int, int]
    model: str
    coordinate_frame: str = "qwen3_vl_norm_0_1000"

    def __post_init__(self) -> None:
        if self.image_width <= 0 or self.image_height <= 0:
            raise ValueError("image dimensions must be positive")
        if self.coordinate_frame != "qwen3_vl_norm_0_1000":
            raise ValueError(f"unsupported coordinate frame: {self.coordinate_frame}")
        _validate_bbox(self.bbox_2d_norm_1000, 0, 1000, "normalized bbox")
        _validate_bbox(self.bbox_2d_px, 0, max(self.image_width, self.image_height), "pixel bbox")
        x1, y1, x2, y2 = self.bbox_2d_px
        if x2 > self.image_width or y2 > self.image_height:
            raise ValueError("pixel bbox exceeds image bounds")
        if not self.label.strip():
            raise ValueError("label must be non-empty")
        if not self.model.strip():
            raise ValueError("model must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return _freeze_tuples(asdict(self))


@dataclass(frozen=True)
class DecisionEvent:
    """One local decision backed by optional Qwen perception evidence."""

    tick: int
    actor_id: str
    mode: str
    intent: str
    decision: str
    reason: str
    command: dict[str, Any]
    perception: PerceptionEvent
    prev_sha: str
    sha256: str = field(default="")

    def __post_init__(self) -> None:
        if self.tick < 0:
            raise ValueError("tick must be non-negative")
        if not self.actor_id.strip():
            raise ValueError("actor_id must be non-empty")
        if self.mode not in {"fixture", "cloud", "edge", "degraded"}:
            raise ValueError(f"unsupported mode: {self.mode}")
        if self.decision not in {"MOVE", "VETO", "HOLD", "REROUTE"}:
            raise ValueError(f"unsupported decision: {self.decision}")
        if len(self.prev_sha) != 64:
            raise ValueError("prev_sha must be a 64-character hex string")

    def body_for_hash(self) -> dict[str, Any]:
        body = self.to_dict()
        body.pop("sha256", None)
        return body

    def compute_sha(self) -> str:
        return sha256_canonical(self.body_for_hash())

    def with_computed_sha(self) -> "DecisionEvent":
        computed = self.compute_sha()
        return DecisionEvent(
            tick=self.tick,
            actor_id=self.actor_id,
            mode=self.mode,
            intent=self.intent,
            decision=self.decision,
            reason=self.reason,
            command=self.command,
            perception=self.perception,
            prev_sha=self.prev_sha,
            sha256=computed,
        )

    def to_dict(self) -> dict[str, Any]:
        return _freeze_tuples(asdict(self))


@dataclass(frozen=True)
class DecisionTrace:
    """Hash-chained trace for one run."""

    run_id: str
    events: tuple[DecisionEvent, ...]
    schema_version: str = TRACE_SCHEMA_VERSION
    genesis_sha: str = GENESIS_SHA
    summary_sha: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != TRACE_SCHEMA_VERSION:
            raise ValueError(f"unsupported schema version: {self.schema_version}")
        if self.genesis_sha != GENESIS_SHA:
            raise ValueError("unexpected genesis sha")
        if not self.run_id.strip():
            raise ValueError("run_id must be non-empty")
        if not self.events:
            raise ValueError("trace must contain at least one event")

    def with_computed_summary(self) -> "DecisionTrace":
        checked = verify_events(self.events)
        summary = sha256_canonical(
            {
                "events": [event.to_dict() for event in checked],
                "genesis_sha": self.genesis_sha,
                "run_id": self.run_id,
                "schema_version": self.schema_version,
            }
        )
        return DecisionTrace(
            run_id=self.run_id,
            events=tuple(checked),
            schema_version=self.schema_version,
            genesis_sha=self.genesis_sha,
            summary_sha=summary,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "events": [event.to_dict() for event in self.events],
            "genesis_sha": self.genesis_sha,
            "run_id": self.run_id,
            "schema_version": self.schema_version,
            "summary_sha": self.summary_sha,
        }

    def to_canonical_json(self) -> str:
        return canonical_json(self.to_dict())


def build_single_event_trace(
    *,
    run_id: str,
    actor_id: str,
    perception: PerceptionEvent,
    intent: str,
    decision: str,
    reason: str,
    command: dict[str, Any],
    mode: str = "fixture",
) -> DecisionTrace:
    event = DecisionEvent(
        tick=0,
        actor_id=actor_id,
        mode=mode,
        intent=intent,
        decision=decision,
        reason=reason,
        command=command,
        perception=perception,
        prev_sha=GENESIS_SHA,
    ).with_computed_sha()
    return DecisionTrace(run_id=run_id, events=(event,)).with_computed_summary()


def verify_events(events: tuple[DecisionEvent, ...]) -> tuple[DecisionEvent, ...]:
    prev_sha = GENESIS_SHA
    checked: list[DecisionEvent] = []
    for event in events:
        if event.prev_sha != prev_sha:
            raise ValueError("trace hash chain is broken")
        computed = event.compute_sha()
        if event.sha256 and event.sha256 != computed:
            raise ValueError("event sha mismatch")
        checked_event = event if event.sha256 else event.with_computed_sha()
        checked.append(checked_event)
        prev_sha = checked_event.sha256
    return tuple(checked)


def verify_trace(trace: DecisionTrace) -> str:
    recomputed = trace.with_computed_summary()
    if trace.summary_sha and trace.summary_sha != recomputed.summary_sha:
        raise ValueError("trace summary sha mismatch")
    return recomputed.summary_sha


def trace_from_dict(value: dict[str, Any]) -> DecisionTrace:
    events = []
    for item in value["events"]:
        perception = PerceptionEvent(
            event_id=item["perception"]["event_id"],
            source=item["perception"]["source"],
            image_width=item["perception"]["image_width"],
            image_height=item["perception"]["image_height"],
            label=item["perception"]["label"],
            bbox_2d_norm_1000=tuple(item["perception"]["bbox_2d_norm_1000"]),
            bbox_2d_px=tuple(item["perception"]["bbox_2d_px"]),
            model=item["perception"]["model"],
            coordinate_frame=item["perception"]["coordinate_frame"],
        )
        events.append(
            DecisionEvent(
                tick=item["tick"],
                actor_id=item["actor_id"],
                mode=item["mode"],
                intent=item["intent"],
                decision=item["decision"],
                reason=item["reason"],
                command=item["command"],
                perception=perception,
                prev_sha=item["prev_sha"],
                sha256=item["sha256"],
            )
        )
    return DecisionTrace(
        run_id=value["run_id"],
        events=tuple(events),
        schema_version=value["schema_version"],
        genesis_sha=value["genesis_sha"],
        summary_sha=value["summary_sha"],
    )


def _validate_bbox(bbox: tuple[int, int, int, int], lower: int, upper: int, name: str) -> None:
    x1, y1, x2, y2 = bbox
    if not all(isinstance(v, int) for v in bbox):
        raise TypeError(f"{name} values must be integers")
    if x1 < lower or y1 < lower or x2 < lower or y2 < lower:
        raise ValueError(f"{name} values must be >= {lower}")
    if x1 >= x2 or y1 >= y2:
        raise ValueError(f"{name} must have positive area")
    if x2 > upper or y2 > upper:
        raise ValueError(f"{name} values must be <= {upper}")


def _freeze_tuples(value: Any) -> Any:
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, list):
        return [_freeze_tuples(item) for item in value]
    if isinstance(value, dict):
        return {key: _freeze_tuples(item) for key, item in value.items()}
    return value
