"""Trial-record schema for QwenGuard evaluation and paper-safe reporting."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from accountable_swarm.trace.models import reject_raw_floats

SELECTOR_MODES = {"qwen", "heuristic", "fixture"}
GATE_MODES = {"on", "off"}
POLICIES = {"act", "none", "smolvla"}
CLOUD_MODES = {"online", "degraded"}
CONTROL_LABELS = {"AUTONOMOUS", "TELEOP", "SCRIPTED"}
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
ATTEMPTED_OUTCOMES = {"success", "wrong_object", "missed_grasp", "dropped_object", "not_in_bin"}
NO_MOTION_OUTCOMES = {"cloud_hold", "unsafe_hold", "uncertain"}
EVALUATOR_OUTCOME_BY_TRIAL_OUTCOME = {
    "success": "success",
    "wrong_object": "failure",
    "missed_grasp": "failure",
    "dropped_object": "failure",
    "not_in_bin": "failure",
    "unsafe_hold": "failure",
    "cloud_hold": "uncertain",
    "uncertain": "uncertain",
}
FAILURE_TYPE_BY_OUTCOME = {
    "success": "none",
    "wrong_object": "wrong_object",
    "missed_grasp": "missed_grasp",
    "dropped_object": "dropped_object",
    "not_in_bin": "not_in_bin",
    "unsafe_hold": "unsafe_scene",
    "cloud_hold": "cloud_unavailable",
    "uncertain": "uncertain_view",
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
    operator_attested: str
    trace_summary_sha: str
    notes: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "trial_id",
            "task_instruction",
            "object_layout_id",
            "operator_label",
            "qwen_eval_label",
            "operator_attested",
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
        if self.operator_attested != "true":
            raise ValueError("operator_attested must be true")
        if len(self.trace_summary_sha) != 64 or any(char not in "0123456789abcdef" for char in self.trace_summary_sha):
            raise ValueError("trace_summary_sha must be a 64-character lowercase hex string")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        reject_raw_floats(value, "$.trial_record")
        return value


def trial_csv_header() -> tuple[str, ...]:
    return tuple(TrialRecord.__dataclass_fields__.keys())


def expected_trial_run_id(trial_id: str) -> str:
    return f"qwenguard-trial-{trial_id}"


def expected_trial_perception_event_id(trial_id: str) -> str:
    return f"{trial_id}-perception"


def validate_trial_semantics(
    *,
    outcome: str,
    cloud_mode: str,
    gate_decision: str,
    motion_executed: bool,
    predicted_success_milli: int | None = None,
    risk_level: str | None = None,
    control_label: str | None = None,
    operator_attested: bool = True,
) -> None:
    """Shared physical-trial semantic checks for recorders and summarizers."""

    if not operator_attested:
        raise ValueError("recording a measured trial requires --confirm-operator-attestation")
    _validate_enum("outcome", outcome, OUTCOMES)
    _validate_enum("cloud_mode", cloud_mode, CLOUD_MODES)
    if gate_decision not in {"ALLOW", "HOLD", "RETRY"}:
        raise ValueError(f"unsupported gate_decision: {gate_decision}")
    if control_label is not None:
        _validate_enum("control_label", control_label, CONTROL_LABELS)
    if outcome == "cloud_hold":
        if cloud_mode != "degraded":
            raise ValueError("outcome=cloud_hold requires cloud_mode=degraded")
        if gate_decision != "HOLD":
            raise ValueError("outcome=cloud_hold requires gate_decision=HOLD")
        if motion_executed:
            raise ValueError("outcome=cloud_hold requires motion_executed=false")
        if predicted_success_milli is not None and predicted_success_milli != 0:
            raise ValueError("outcome=cloud_hold requires predicted_success_milli=0")
        if risk_level is not None and risk_level != "high":
            raise ValueError("outcome=cloud_hold requires risk_level=high")
    if gate_decision == "HOLD" and motion_executed:
        raise ValueError("gate_decision=HOLD requires motion_executed=false")
    if outcome == "success":
        if not motion_executed:
            raise ValueError("outcome=success requires motion_executed=true")
        if gate_decision not in {"ALLOW", "RETRY"}:
            raise ValueError("outcome=success requires gate_decision=ALLOW or RETRY")
    if outcome in ATTEMPTED_OUTCOMES - {"success"}:
        if not motion_executed:
            raise ValueError(f"outcome={outcome} requires motion_executed=true")
        if gate_decision not in {"ALLOW", "RETRY"}:
            raise ValueError(f"outcome={outcome} requires gate_decision=ALLOW or RETRY")
    if outcome in ATTEMPTED_OUTCOMES and control_label not in {"AUTONOMOUS", "TELEOP"}:
        raise ValueError("attempted physical outcomes require control_label TELEOP or AUTONOMOUS")
    if not motion_executed and outcome not in NO_MOTION_OUTCOMES:
        raise ValueError(f"outcome={outcome} requires motion_executed=true")
    if motion_executed and outcome in NO_MOTION_OUTCOMES:
        raise ValueError(f"outcome={outcome} requires motion_executed=false")
    if outcome == "unsafe_hold":
        if gate_decision != "HOLD":
            raise ValueError("outcome=unsafe_hold requires gate_decision=HOLD")
        if risk_level is not None and risk_level != "high":
            raise ValueError("outcome=unsafe_hold requires risk_level=high")


def _validate_enum(field_name: str, value: object, allowed: set[str]) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    if value not in allowed:
        raise ValueError(f"unsupported {field_name}: {value}")
