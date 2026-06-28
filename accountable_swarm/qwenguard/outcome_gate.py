"""Deterministic local outcome gate for QwenGuard.

This is the hackathon-scale "world model" surface: it predicts whether a
candidate action is worth attempting from bounded local state. V0 is
rule-based; learned predictors can replace the scoring function only after real
SO-101 attempts are collected.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from accountable_swarm.physical.contract import PhysicalNodeSafety
from accountable_swarm.qwenguard.selector import SelectorResult
from accountable_swarm.trace.models import reject_raw_floats

GATE_DECISIONS = {"ALLOW", "HOLD", "RETRY"}
RISK_LEVELS = {"low", "medium", "high"}


@dataclass(frozen=True)
class OutcomeGateInput:
    selector: SelectorResult | None
    safety: PhysicalNodeSafety
    policy_available: bool = False
    cloud_available: bool = True
    workspace_ok: bool = True
    recent_failure_count: int = 0
    min_confidence_milli: int = 700

    def __post_init__(self) -> None:
        if isinstance(self.policy_available, bool) is False:
            raise TypeError("policy_available must be bool")
        if isinstance(self.cloud_available, bool) is False:
            raise TypeError("cloud_available must be bool")
        if isinstance(self.workspace_ok, bool) is False:
            raise TypeError("workspace_ok must be bool")
        if isinstance(self.recent_failure_count, bool) or not isinstance(self.recent_failure_count, int):
            raise TypeError("recent_failure_count must be int")
        if self.recent_failure_count < 0:
            raise ValueError("recent_failure_count must be non-negative")
        if isinstance(self.min_confidence_milli, bool) or not isinstance(self.min_confidence_milli, int):
            raise TypeError("min_confidence_milli must be int")
        if self.min_confidence_milli < 0 or self.min_confidence_milli > 1000:
            raise ValueError("min_confidence_milli must be within 0-1000")


@dataclass(frozen=True)
class GateDecision:
    gate_decision: str
    candidate_action: str
    predicted_success_milli: int
    risk_level: str
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.gate_decision not in GATE_DECISIONS:
            raise ValueError(f"unsupported gate_decision: {self.gate_decision}")
        if not self.candidate_action.strip():
            raise ValueError("candidate_action must be non-empty")
        if isinstance(self.predicted_success_milli, bool) or not isinstance(self.predicted_success_milli, int):
            raise TypeError("predicted_success_milli must be int")
        if self.predicted_success_milli < 0 or self.predicted_success_milli > 1000:
            raise ValueError("predicted_success_milli must be within 0-1000")
        if self.risk_level not in RISK_LEVELS:
            raise ValueError(f"unsupported risk_level: {self.risk_level}")
        if not self.reasons:
            raise ValueError("reasons must be non-empty")
        for reason in self.reasons:
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError("reasons must be non-empty strings")

    def to_command(self) -> dict[str, Any]:
        command = {
            "type": "qwenguard_outcome_gate",
            "gate_decision": self.gate_decision,
            "candidate_action": self.candidate_action,
            "predicted_success_milli": self.predicted_success_milli,
            "risk_level": self.risk_level,
            "reasons": list(self.reasons),
        }
        reject_raw_floats(command, "$.gate_command")
        return command

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["reasons"] = list(self.reasons)
        return value


def evaluate_outcome_gate(inputs: OutcomeGateInput) -> GateDecision:
    """Return a deterministic gate decision for one candidate pick/place."""

    reasons: list[str] = []
    if not inputs.cloud_available:
        reasons.append("cloud_unavailable")
        return _hold(predicted_success_milli=0, risk_level="high", reasons=reasons)
    if inputs.selector is None:
        reasons.append("selector_missing")
        return _hold(predicted_success_milli=0, risk_level="high", reasons=reasons)
    below_threshold = inputs.selector.confidence_milli < inputs.min_confidence_milli
    if below_threshold:
        reasons.append("selector_confidence_below_threshold")
    else:
        reasons.append("selector_confidence_ok")
    if not inputs.workspace_ok:
        reasons.append("workspace_rejected")
    else:
        reasons.append("workspace_ok")
    if not inputs.policy_available:
        reasons.append("policy_unavailable")
    else:
        reasons.append("policy_available")

    safety_error = _safety_error(inputs.safety)
    if safety_error:
        reasons.append(f"safety_rejected:{safety_error}")
    else:
        reasons.append("safety_ok")

    predicted = _predict_success_milli(inputs)
    risk_level = _risk_level(predicted, inputs.recent_failure_count)
    if (
        not below_threshold
        and predicted >= inputs.min_confidence_milli
        and not safety_error
        and inputs.workspace_ok
        and inputs.policy_available
    ):
        return GateDecision(
            gate_decision="ALLOW",
            candidate_action="pick_place",
            predicted_success_milli=predicted,
            risk_level=risk_level,
            reasons=tuple(reasons),
        )
    if (
        not below_threshold
        and inputs.recent_failure_count == 1
        and inputs.policy_available
        and inputs.workspace_ok
        and not safety_error
    ):
        reasons.append("bounded_retry_available")
        return GateDecision(
            gate_decision="RETRY",
            candidate_action="retry_pick_place",
            predicted_success_milli=max(0, predicted - 100),
            risk_level="medium",
            reasons=tuple(reasons),
        )
    return _hold(predicted_success_milli=predicted, risk_level=risk_level, reasons=reasons)


def _predict_success_milli(inputs: OutcomeGateInput) -> int:
    if inputs.selector is None or not inputs.cloud_available:
        return 0
    score = inputs.selector.confidence_milli
    if not inputs.workspace_ok:
        score -= 300
    if not inputs.policy_available:
        score -= 250
    score -= min(400, inputs.recent_failure_count * 150)
    if _safety_error(inputs.safety):
        score -= 300
    return min(1000, max(0, score))


def _risk_level(predicted_success_milli: int, recent_failure_count: int) -> str:
    if predicted_success_milli < 500 or recent_failure_count >= 2:
        return "high"
    if predicted_success_milli < 750 or recent_failure_count == 1:
        return "medium"
    return "low"


def _hold(*, predicted_success_milli: int, risk_level: str, reasons: list[str]) -> GateDecision:
    return GateDecision(
        gate_decision="HOLD",
        candidate_action="hold",
        predicted_success_milli=predicted_success_milli,
        risk_level=risk_level,
        reasons=tuple(reasons),
    )


def _safety_error(safety: PhysicalNodeSafety) -> str:
    try:
        safety.assert_safe_for_motion()
    except RuntimeError as exc:
        return str(exc)
    return ""
