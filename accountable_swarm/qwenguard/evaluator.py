"""Before/after Qwen evaluator validation for QwenGuard."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

from accountable_swarm.qwenguard.json_extract import (
    extract_first_json_object,
    int_milli_field,
    reject_unexpected_keys,
    string_field,
)
from accountable_swarm.trace.models import reject_raw_floats

OUTCOMES = {"success", "failure", "uncertain"}
FAILURE_TYPES = {
    "none",
    "wrong_object",
    "missed_grasp",
    "dropped_object",
    "not_in_bin",
    "unsafe_scene",
    "uncertain_view",
    "cloud_unavailable",
}


@dataclass(frozen=True)
class EvaluationResult:
    outcome: str
    failure_type: str
    confidence_milli: int
    evidence: str

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"unsupported outcome: {self.outcome}")
        if self.failure_type not in FAILURE_TYPES:
            raise ValueError(f"unsupported failure_type: {self.failure_type}")
        if self.outcome == "success" and self.failure_type != "none":
            raise ValueError("successful outcome must use failure_type=none")
        if self.outcome != "success" and self.failure_type == "none":
            raise ValueError("non-success outcome requires a failure_type")
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

    def to_command(self) -> dict[str, Any]:
        evidence_bytes = self.evidence.encode("utf-8")
        command = {
            "type": "qwenguard_evaluate_outcome",
            "outcome": self.outcome,
            "failure_type": self.failure_type,
            "confidence_milli": self.confidence_milli,
            "evidence_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
            "evidence_char_count": len(self.evidence),
        }
        reject_raw_floats(command, "$.evaluation_command")
        return command


def parse_evaluator_response(response_text: str) -> EvaluationResult:
    value = extract_first_json_object(response_text)
    reject_unexpected_keys(value, {"outcome", "failure_type", "confidence_milli", "evidence"})
    return EvaluationResult(
        outcome=string_field(value, "outcome"),
        failure_type=string_field(value, "failure_type"),
        confidence_milli=int_milli_field(value, "confidence_milli"),
        evidence=string_field(value, "evidence"),
    )


def degraded_evaluation(reason: str) -> EvaluationResult:
    return EvaluationResult(
        outcome="uncertain",
        failure_type="cloud_unavailable",
        confidence_milli=0,
        evidence=f"Cloud evaluator unavailable: {reason}",
    )
