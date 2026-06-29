#!/usr/bin/env python3
"""Summarize measured QwenGuard physical trials from verified traces."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any

from accountable_swarm.qwenguard.trial import OUTCOMES, TrialRecord, trial_csv_header
from accountable_swarm.trace.models import canonical_json, trace_from_dict, verify_trace


REPORT_SCHEMA_VERSION = "qwenguard-trial-summary.v1"
ISSUE_URL = "https://github.com/omarespejel/accountable-swarm/issues/106"
UMBRELLA_ISSUE_URL = "https://github.com/omarespejel/accountable-swarm/issues/95"
DEFAULT_TRIAL_CSV = Path("runs/physical/qwenguard_trials/trial_results.csv")
DEFAULT_TRIAL_TRACE_DIR = Path("runs/physical/qwenguard_trials/traces")
DEFAULT_OUT = Path("runs/physical/qwenguard_trials/trial_summary.json")

ATTEMPTED_OUTCOMES = {"success", "wrong_object", "missed_grasp", "dropped_object", "not_in_bin"}
NO_MOTION_OUTCOMES = {"cloud_hold", "unsafe_hold", "uncertain"}
FAILURE_OUTCOMES = sorted(OUTCOMES - {"success"})
BEARER_TOKEN_RE = re.compile(r"Authorization:[ \t]*Bearer[ \t]+([^\s\"',}]+)", re.IGNORECASE)
TRIAL_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}")
EVALUATOR_BY_TRIAL_OUTCOME = {
    "success": ("success", "none"),
    "wrong_object": ("failure", "wrong_object"),
    "missed_grasp": ("failure", "missed_grasp"),
    "dropped_object": ("failure", "dropped_object"),
    "not_in_bin": ("failure", "not_in_bin"),
    "unsafe_hold": ("failure", "unsafe_scene"),
    "cloud_hold": ("uncertain", "cloud_unavailable"),
    "uncertain": ("uncertain", "uncertain_view"),
}
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ALIBABA_API_KEY[ \t]*=[ \t]*\S+", re.IGNORECASE),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh(?:p|o|u|s|r)_[A-Za-z0-9_]{12,}"),
    re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9._-]{20,}"),
)
RAW_FRAME_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"data:image/[A-Za-z0-9.+-]+;base64,", re.IGNORECASE),
    re.compile(r"base64,[A-Za-z0-9+/]{80,}={0,2}", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{160,}={0,2}(?![A-Za-z0-9+/])"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trial-csv", type=Path, default=DEFAULT_TRIAL_CSV)
    parser.add_argument("--trial-trace-dir", type=Path, default=DEFAULT_TRIAL_TRACE_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--allow-narrow-claim",
        action="store_true",
        help="Write the summary with exit 0 even when evidence remains NARROW_CLAIM.",
    )
    args = parser.parse_args()

    try:
        repo_root = _find_repo_root(Path.cwd())
        trial_csv = _repo_path(repo_root, args.trial_csv)
        trial_trace_dir = _repo_path(repo_root, args.trial_trace_dir)
        out = _repo_path(repo_root, args.out)
        if out.resolve() == trial_csv.resolve():
            raise ValueError("summary output must be distinct from the trial CSV")
        if trial_trace_dir.resolve() == out.resolve() or trial_trace_dir.resolve() in out.resolve().parents:
            raise ValueError("summary output must not be written inside the trace directory")
    except ValueError as exc:
        print(f"qwenguard trial summary failed: {exc}", file=sys.stderr)
        return 2

    report = summarize_trials(repo_root=repo_root, trial_csv=trial_csv, trial_trace_dir=trial_trace_dir, out=out)
    report_text = canonical_json(report) + "\n"
    if _contains_secret_like_material(report_text) or _contains_raw_frame_material(report_text):
        print("qwenguard trial summary failed: report would contain secret-like material", file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report_text, encoding="utf-8")

    print(f"outcome {report['outcome']}")
    print(f"trial_readiness {report['trial_readiness']}")
    print(f"total_trials {report['aggregate']['total_trials']}")
    print(f"success_count {report['aggregate']['success_count']}")
    print(f"report {_display_path(repo_root, out)}")
    if report["outcome"] != "GO" and not args.allow_narrow_claim:
        return 4
    return 0


def summarize_trials(*, repo_root: Path, trial_csv: Path, trial_trace_dir: Path, out: Path) -> dict[str, Any]:
    rows_result = _read_trial_rows(trial_csv)
    bindings: list[dict[str, Any]] = []
    records: list[TrialRecord] = []
    invalid_reasons = list(rows_result.invalid_reasons)
    duplicate_trial_ids = sorted(_duplicates([record.trial_id for record in rows_result.records]))
    if duplicate_trial_ids:
        invalid_reasons.append(f"duplicate trial_id values: {', '.join(duplicate_trial_ids[:5])}")
    if not trial_trace_dir.is_dir():
        invalid_reasons.append("trial trace directory is missing")
    else:
        for record in rows_result.records:
            binding = _verify_trial_binding(repo_root=repo_root, trial_trace_dir=trial_trace_dir, record=record)
            bindings.append(binding)
            if not binding["verified"]:
                invalid_reasons.append(f"{record.trial_id}: {binding['reason']}")
            else:
                records.append(record)
    if rows_result.secret_or_frame_material_detected:
        invalid_reasons.append("trial CSV contains secret-like or raw-frame-like material")

    aggregate = _aggregate(records)
    checks = {
        "trial_csv_present": trial_csv.is_file(),
        "trial_csv_schema_valid": rows_result.header_valid,
        "trial_rows_present": bool(rows_result.records),
        "trial_trace_dir_present": trial_trace_dir.is_dir(),
        "trial_bindings_verify": bool(rows_result.records) and len(records) == len(rows_result.records),
        "no_duplicate_trial_ids": not duplicate_trial_ids,
        "secret_material_absent": not rows_result.secret_or_frame_material_detected,
        "raw_float_free_summary": True,
    }
    outcome = "GO" if all(checks.values()) and not invalid_reasons else "NARROW_CLAIM"
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "outcome": outcome,
        "trial_readiness": "READY" if outcome == "GO" else "NARROW_CLAIM",
        "issue": ISSUE_URL,
        "umbrella_issue": UMBRELLA_ISSUE_URL,
        "inputs": {
            "trial_csv": _display_path(repo_root, trial_csv),
            "trial_trace_dir": _display_path(repo_root, trial_trace_dir),
            "report_path": _display_path(repo_root, out),
        },
        "checks": checks,
        "invalid_reason_count": len(invalid_reasons),
        "invalid_reasons": invalid_reasons[:10],
        "aggregate": aggregate,
        "trial_bindings": bindings,
        "csv_sha256": _file_sha256(trial_csv) if trial_csv.is_file() else "",
        "non_claims": [
            "not a physical success claim when outcome is NARROW_CLAIM",
            "not a safety, latency, or reliability claim",
            "not Qwen motor control",
            "not DimOS physical control",
            "not an ACT generalization claim beyond measured rows",
        ],
    }
    canonical_json(report)
    return report


def _read_trial_rows(path: Path) -> "TrialRowsResult":
    if not path.is_file():
        return TrialRowsResult(records=[], header_valid=False, invalid_reasons=["trial CSV is missing"])
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return TrialRowsResult(records=[], header_valid=False, invalid_reasons=["trial CSV is not UTF-8"])
    secret_or_frame = _contains_secret_like_material(text) or _contains_raw_frame_material(text)
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = tuple(reader.fieldnames or ())
            rows = [dict(row) for row in reader]
    except csv.Error as exc:
        return TrialRowsResult(records=[], header_valid=False, invalid_reasons=[f"trial CSV could not be parsed: {exc}"])
    header_valid = fieldnames == trial_csv_header()
    invalid_reasons: list[str] = []
    records: list[TrialRecord] = []
    if not header_valid:
        invalid_reasons.append("trial CSV header does not match TrialRecord schema")
        return TrialRowsResult(
            records=[],
            header_valid=False,
            invalid_reasons=invalid_reasons,
            secret_or_frame_material_detected=secret_or_frame,
        )
    for index, row in enumerate(rows, start=1):
        if all(not str(value or "").strip() for value in row.values()):
            continue
        try:
            record = TrialRecord(
                trial_id=row.get("trial_id", ""),
                task_instruction=row.get("task_instruction", ""),
                object_layout_id=row.get("object_layout_id", ""),
                selector_mode=row.get("selector_mode", ""),
                gate_mode=row.get("gate_mode", ""),
                policy=row.get("policy", ""),
                cloud_mode=row.get("cloud_mode", ""),
                outcome=row.get("outcome", ""),
                operator_label=row.get("operator_label", ""),
                qwen_eval_label=row.get("qwen_eval_label", ""),
                trace_summary_sha=row.get("trace_summary_sha", ""),
                notes=row.get("notes", ""),
            )
        except ValueError as exc:
            invalid_reasons.append(f"row {index}: {exc}")
        else:
            records.append(record)
    return TrialRowsResult(
        records=records,
        header_valid=header_valid,
        invalid_reasons=invalid_reasons,
        secret_or_frame_material_detected=secret_or_frame,
    )


def _verify_trial_binding(*, repo_root: Path, trial_trace_dir: Path, record: TrialRecord) -> dict[str, Any]:
    if not TRIAL_ID_RE.fullmatch(record.trial_id):
        return {
            "trial_id": record.trial_id,
            "outcome": record.outcome,
            "selector_mode": record.selector_mode,
            "gate_mode": record.gate_mode,
            "policy": record.policy,
            "cloud_mode": record.cloud_mode,
            "trace_path": "",
            "trace_summary_sha": record.trace_summary_sha,
            "verified": False,
            "reason": "trial_id is not a simple trace filename identifier",
        }
    trace_path = trial_trace_dir / f"{record.trial_id}.json"
    binding = {
        "trial_id": record.trial_id,
        "outcome": record.outcome,
        "selector_mode": record.selector_mode,
        "gate_mode": record.gate_mode,
        "policy": record.policy,
        "cloud_mode": record.cloud_mode,
        "trace_path": _display_path(repo_root, trace_path),
        "trace_summary_sha": record.trace_summary_sha,
        "verified": False,
        "reason": "not checked",
    }
    if not trace_path.is_file():
        binding["reason"] = "trace file is missing"
        return binding
    payload = _read_json(trace_path)
    if isinstance(payload, JsonReadError):
        binding["reason"] = payload.reason
        return binding
    if not isinstance(payload, dict):
        binding["reason"] = "trace is not a JSON object"
        return binding
    try:
        trace = trace_from_dict(payload)
        summary_sha = verify_trace(trace)
        _validate_trial_trace_shape(trace)
        metadata = _trial_trace_metadata(trace)
    except (KeyError, TypeError, ValueError) as exc:
        binding["reason"] = f"trace verification failed: {exc.__class__.__name__}"
        return binding
    binding["computed_summary_sha"] = summary_sha
    if summary_sha != record.trace_summary_sha:
        binding["reason"] = "trace summary does not match CSV row"
        return binding
    mismatch_reason = _record_trace_mismatch(record, metadata)
    binding["trace_metadata"] = metadata
    if mismatch_reason:
        binding["reason"] = mismatch_reason
        return binding
    binding["verified"] = True
    binding["reason"] = "trace summary matches CSV row"
    return binding


def _trial_trace_metadata(trace: Any) -> dict[str, str]:
    commands = [event.command for event in trace.events if isinstance(event.command, dict)]
    gate_command = _single_command(commands, "qwenguard_outcome_gate")
    action_command = _single_command(commands, "physical_action_intent")
    eval_command = _single_command(commands, "qwenguard_evaluate_outcome")
    reasons = gate_command.get("reasons")
    if not isinstance(reasons, list):
        raise ValueError("trial trace gate reasons must be a list")
    reason_values = _reason_values(reasons)
    metadata = {
        "selector_mode": _string_reason(reason_values, "selector_mode"),
        "gate_mode": _string_reason(reason_values, "gate_mode"),
        "policy": _string_reason(reason_values, "policy"),
        "cloud_mode": _string_reason(reason_values, "cloud_mode"),
        "gate_decision": _string_command(gate_command, "gate_decision"),
        "action_policy": _string_command(action_command, "policy"),
        "evaluator_outcome": _string_command(eval_command, "outcome"),
        "evaluator_failure_type": _string_command(eval_command, "failure_type"),
    }
    if metadata["action_policy"] != metadata["policy"]:
        raise ValueError("trial trace policy metadata is inconsistent")
    return metadata


def _single_command(commands: list[dict[str, Any]], command_type: str) -> dict[str, Any]:
    matches = [command for command in commands if command.get("type") == command_type]
    if len(matches) != 1:
        raise ValueError(f"trial trace must contain exactly one {command_type} command")
    return matches[0]


def _reason_values(reasons: list[object]) -> dict[str, str]:
    values: dict[str, str] = {}
    for reason in reasons:
        if not isinstance(reason, str) or ":" not in reason:
            continue
        key, value = reason.split(":", 1)
        values.setdefault(key, value)
    return values


def _string_reason(values: dict[str, str], key: str) -> str:
    value = values.get(key)
    if value is None or not value:
        raise ValueError(f"trial trace missing gate reason: {key}")
    return value


def _string_command(command: dict[str, Any], key: str) -> str:
    value = command.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"trial trace command missing string field: {key}")
    return value


def _record_trace_mismatch(record: TrialRecord, metadata: dict[str, str]) -> str:
    for field_name in ("selector_mode", "gate_mode", "policy", "cloud_mode"):
        if getattr(record, field_name) != metadata[field_name]:
            return f"{field_name} does not match trace metadata"
    expected_eval = EVALUATOR_BY_TRIAL_OUTCOME[record.outcome]
    actual_eval = (metadata["evaluator_outcome"], metadata["evaluator_failure_type"])
    if actual_eval != expected_eval:
        return "outcome does not match trace evaluator metadata"
    return ""


def _validate_trial_trace_shape(trace: Any) -> None:
    command_types = {
        event.command.get("type")
        for event in trace.events
        if isinstance(event.command, dict)
    }
    required = {
        "qwenguard_outcome_gate",
        "physical_action_intent",
        "qwenguard_evaluate_outcome",
    }
    missing = sorted(required - command_types)
    if missing:
        raise ValueError(f"trial trace missing required command types: {', '.join(missing)}")


def _aggregate(records: list[TrialRecord]) -> dict[str, Any]:
    outcome_counts = _count_by(records, "outcome", sorted(OUTCOMES))
    attempted_trials = sum(outcome_counts[outcome] for outcome in sorted(ATTEMPTED_OUTCOMES))
    total_trials = len(records)
    success_count = outcome_counts["success"]
    failure_count = sum(outcome_counts[outcome] for outcome in FAILURE_OUTCOMES)
    no_motion_count = sum(outcome_counts[outcome] for outcome in sorted(NO_MOTION_OUTCOMES))
    return {
        "total_trials": total_trials,
        "attempted_trials": attempted_trials,
        "success_count": success_count,
        "failure_count": failure_count,
        "no_motion_count": no_motion_count,
        "cloud_hold_count": outcome_counts["cloud_hold"],
        "unsafe_hold_count": outcome_counts["unsafe_hold"],
        "uncertain_count": outcome_counts["uncertain"],
        "success_rate_all_trials_milli": _rate_milli(success_count, total_trials),
        "success_rate_attempted_milli": _rate_milli(success_count, attempted_trials),
        "outcome_counts": outcome_counts,
        "failure_taxonomy_counts": {outcome: outcome_counts[outcome] for outcome in FAILURE_OUTCOMES},
        "selector_mode_counts": _count_by(records, "selector_mode"),
        "gate_mode_counts": _count_by(records, "gate_mode"),
        "policy_counts": _count_by(records, "policy"),
        "cloud_mode_counts": _count_by(records, "cloud_mode"),
        "object_layout_counts": _count_by(records, "object_layout_id"),
        "qwen_eval_label_counts": _count_by(records, "qwen_eval_label"),
    }


def _rate_milli(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return (numerator * 1000) // denominator


def _count_by(records: list[TrialRecord], field_name: str, keys: list[str] | None = None) -> dict[str, int]:
    counts: dict[str, int] = {key: 0 for key in keys or []}
    for record in records:
        key = str(getattr(record, field_name))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


class TrialRowsResult:
    def __init__(
        self,
        *,
        records: list[TrialRecord],
        header_valid: bool,
        invalid_reasons: list[str],
        secret_or_frame_material_detected: bool = False,
    ) -> None:
        self.records = records
        self.header_valid = header_valid
        self.invalid_reasons = invalid_reasons
        self.secret_or_frame_material_detected = secret_or_frame_material_detected


class JsonReadError:
    def __init__(self, *, reason: str) -> None:
        self.reason = reason


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return JsonReadError(reason="file is missing")
    except json.JSONDecodeError:
        return JsonReadError(reason="file is not valid JSON")
    except UnicodeDecodeError:
        return JsonReadError(reason="file is not valid UTF-8")


def _contains_secret_like_material(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS) or any(
        match.group(1) != "<redacted>" for match in BEARER_TOKEN_RE.finditer(value)
    )


def _contains_raw_frame_material(value: str) -> bool:
    return any(pattern.search(value) for pattern in RAW_FRAME_PATTERNS)


def _find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "pyproject.toml").is_file() and (candidate / "accountable_swarm").is_dir():
            return candidate
    raise ValueError("could not locate repository root")


def _repo_path(repo_root: Path, raw_path: Path) -> Path:
    candidate = raw_path if raw_path.is_absolute() else repo_root / raw_path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError(f"path must stay inside the repository checkout: {raw_path}") from exc
    return resolved


def _display_path(repo_root: Path, path: Path) -> str:
    relative = path.resolve().relative_to(repo_root.resolve())
    return PurePosixPath(relative).as_posix()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
