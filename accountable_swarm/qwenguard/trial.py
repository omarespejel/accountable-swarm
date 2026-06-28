"""Trial-record schema for QwenGuard evaluation and paper-safe reporting."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from accountable_swarm.trace.models import reject_raw_floats

SELECTOR_MODES = {"qwen", "heuristic", "fixture"}
GATE_MODES = {"on", "off"}
POLICIES = {"act", "none", "smolvla"}
CLOUD_MODES = {"online", "degraded"}
OUTCOMES = {
    "success",
    "wrong_object",
    "missed_grasp",
    "dropped_object",
    "not_in_bin",
    "unsafe_hold",
    "cloud_hold",
    "uncertain",
}


@dataclass(frozen=True)
class TrialRecord:
    trial_id: str
    task_instruction: str
    object_layout_id: str
    selector_mode: str
    gate_mode: str
    policy: str
    cloud_mode: str
    outcome: str
    operator_label: str
    qwen_eval_label: str
    trace_summary_sha: str
    notes: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "trial_id",
            "task_instruction",
            "object_layout_id",
            "operator_label",
            "qwen_eval_label",
            "trace_summary_sha",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        _validate_enum("selector_mode", self.selector_mode, SELECTOR_MODES)
        _validate_enum("gate_mode", self.gate_mode, GATE_MODES)
        _validate_enum("policy", self.policy, POLICIES)
        _validate_enum("cloud_mode", self.cloud_mode, CLOUD_MODES)
        _validate_enum("outcome", self.outcome, OUTCOMES)
        if not isinstance(self.notes, str):
            raise ValueError("notes must be a string")
        if len(self.trace_summary_sha) != 64 or any(char not in "0123456789abcdef" for char in self.trace_summary_sha):
            raise ValueError("trace_summary_sha must be a 64-character lowercase hex string")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        reject_raw_floats(value, "$.trial_record")
        return value


def trial_csv_header() -> tuple[str, ...]:
    return tuple(TrialRecord.__dataclass_fields__.keys())


def _validate_enum(field_name: str, value: object, allowed: set[str]) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    if value not in allowed:
        raise ValueError(f"unsupported {field_name}: {value}")
