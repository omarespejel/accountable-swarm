#!/usr/bin/env python3
"""Audit whether QwenGuard has enough evidence for Track 5 submission readiness."""

from __future__ import annotations

import argparse
import csv
from datetime import date
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any
from urllib.parse import urlparse

from accountable_swarm.qwenguard.trial import TrialRecord
from accountable_swarm.trace.models import canonical_json, trace_from_dict, verify_trace


REPORT_SCHEMA_VERSION = "qwenguard-submission-readiness-report.v1"
DEFAULT_OUT = Path("runs/submission/qwenguard-readiness-report.json")
DEFAULT_SUBMISSION_MANIFEST = Path("runs/submission/qwenguard-pack/manifest.json")
DEFAULT_SO101_CAMERA_REPORT = Path("runs/physical/qwenguard_physical_go/so101_capture_report.json")
DEFAULT_FIXTURE_TRACE = Path("runs/physical/qwenguard_physical_go/fixture_trace.json")
DEFAULT_DEGRADED_TRACE = Path("runs/physical/qwenguard_physical_go/degraded_trace.json")
DEFAULT_TRIAL_CSV = Path("runs/physical/qwenguard_trials/trial_results.csv")
DEFAULT_TRIAL_TRACE_DIR = Path("runs/physical/qwenguard_trials/traces")
DEFAULT_TRIAL_SUMMARY = Path("runs/physical/qwenguard_trials/trial_summary.json")
DEFAULT_ECS_REPORT = Path("runs/ecs/ecs_smoke_report.json")
DEFAULT_VIDEO_REVIEW = Path("runs/submission/final_video_review.md")
TRIAL_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}")

SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Authorization:[ \t]*Bearer[ \t]+(?!<redacted>(?:$|[ \t]))\S+", re.IGNORECASE),
    re.compile(r"ALIBABA_API_KEY[ \t]*=[ \t]*\S+", re.IGNORECASE),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh(?:p|o|u|s|r)_[A-Za-z0-9_]{12,}"),
    re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9._-]{20,}"),
)
VIDEO_REVIEW_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VIDEO_REVIEW_REQUIRED_PHRASES = [
    "Qwen never controls motors",
    "SO-101",
    "Alibaba ECS",
    "AUTONOMOUS",
    "TELEOP",
    "SCRIPTED",
]
VIDEO_REVIEW_REQUIRED_FIELDS = [
    "Reviewed-by",
    "Review-date",
    "Video-artifact",
    "Privacy-reviewed",
    "Claim-boundary-reviewed",
    "Mode-labels-reviewed",
    "ECS-proof-reviewed",
    "SO-101-footage-reviewed",
    "Secrets-reviewed",
]
VIDEO_REVIEW_YES_FIELDS = [
    "Privacy-reviewed",
    "Claim-boundary-reviewed",
    "Mode-labels-reviewed",
    "ECS-proof-reviewed",
    "SO-101-footage-reviewed",
    "Secrets-reviewed",
]
VIDEO_REVIEW_PLACEHOLDER_TERMS = (
    "todo",
    "tbd",
    "placeholder",
    "replace",
    "example",
    "your ",
    "n/a",
    "none",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--submission-manifest", type=Path, default=DEFAULT_SUBMISSION_MANIFEST)
    parser.add_argument("--so101-camera-report", type=Path, default=DEFAULT_SO101_CAMERA_REPORT)
    parser.add_argument("--fixture-trace", type=Path, default=DEFAULT_FIXTURE_TRACE)
    parser.add_argument("--degraded-trace", type=Path, default=DEFAULT_DEGRADED_TRACE)
    parser.add_argument("--trial-csv", type=Path, default=DEFAULT_TRIAL_CSV)
    parser.add_argument("--trial-trace-dir", type=Path, default=DEFAULT_TRIAL_TRACE_DIR)
    parser.add_argument("--trial-summary", type=Path, default=DEFAULT_TRIAL_SUMMARY)
    parser.add_argument("--ecs-report", type=Path, default=DEFAULT_ECS_REPORT)
    parser.add_argument("--video-review", type=Path, default=DEFAULT_VIDEO_REVIEW)
    parser.add_argument(
        "--allow-narrow-claim",
        action="store_true",
        help="Write the report with exit 0 even when submission readiness is still NARROW_CLAIM.",
    )
    args = parser.parse_args()

    try:
        repo_root = _find_repo_root(Path.cwd())
        paths = {
            "out": _repo_path(repo_root, args.out),
            "submission_manifest": _repo_path(repo_root, args.submission_manifest),
            "so101_camera_report": _repo_path(repo_root, args.so101_camera_report),
            "fixture_trace": _repo_path(repo_root, args.fixture_trace),
            "degraded_trace": _repo_path(repo_root, args.degraded_trace),
            "trial_csv": _repo_path(repo_root, args.trial_csv),
            "trial_trace_dir": _repo_path(repo_root, args.trial_trace_dir),
            "trial_summary": _repo_path(repo_root, args.trial_summary),
            "ecs_report": _repo_path(repo_root, args.ecs_report),
            "video_review": _repo_path(repo_root, args.video_review),
        }
    except ValueError as exc:
        print(f"qwenguard submission readiness audit failed: {exc}", file=sys.stderr)
        return 2

    report = audit_readiness(repo_root=repo_root, paths=paths)
    paths["out"].parent.mkdir(parents=True, exist_ok=True)
    paths["out"].write_text(canonical_json(report) + "\n", encoding="utf-8")

    print(f"outcome {report['outcome']}")
    print(f"submission_readiness {report['submission_readiness']}")
    print(f"report {_display_path(repo_root, paths['out'])}")
    if report["outcome"] != "GO" and not args.allow_narrow_claim:
        return 4
    return 0


def audit_readiness(*, repo_root: Path, paths: dict[str, Path]) -> dict[str, Any]:
    fixture_trace_check = _check_trace(repo_root, paths["fixture_trace"], mode="fixture", expected_gate_decision="ALLOW")
    degraded_trace_check = _check_trace(repo_root, paths["degraded_trace"], mode="degraded", expected_gate_decision="HOLD")
    trial_trace_check = _check_trial_trace_dir(repo_root, paths["trial_trace_dir"])
    verified_trial_trace_summaries = (
        set(trial_trace_check["evidence"].get("summary_shas", []))
        if trial_trace_check["ok"]
        else set()
    )
    trial_csv_check = _check_trial_csv(repo_root, paths["trial_csv"], verified_trace_summaries=verified_trial_trace_summaries)
    checks = [
        _check_submission_manifest(repo_root, paths["submission_manifest"]),
        _check_camera_report(repo_root, paths["so101_camera_report"]),
        fixture_trace_check,
        degraded_trace_check,
        trial_trace_check,
        trial_csv_check,
        _check_trial_summary(
            repo_root,
            paths["trial_summary"],
            trial_csv=paths["trial_csv"],
            trial_trace_dir=paths["trial_trace_dir"],
            valid_row_count=int(trial_csv_check["evidence"].get("valid_row_count", 0)),
            verified_trace_summaries=verified_trial_trace_summaries,
        ),
        _check_ecs_report(repo_root, paths["ecs_report"]),
        _check_video_review(repo_root, paths["video_review"]),
    ]
    pass_conditions = {check["name"]: check["ok"] for check in checks}
    outcome = "GO" if all(pass_conditions.values()) else "NARROW_CLAIM"
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "outcome": outcome,
        "submission_readiness": "READY" if outcome == "GO" else "NARROW_CLAIM",
        "checks": checks,
        "pass_conditions": pass_conditions,
        "non_claims": [
            "not a physical success claim when outcome is NARROW_CLAIM",
            "not an Alibaba ECS proof unless ecs_report_is_public_go passes",
            "not a safety, latency, or reliability claim",
            "not Qwen motor control",
            "not DimOS physical control",
        ],
    }


def _check_submission_manifest(repo_root: Path, path: Path) -> dict[str, Any]:
    check = _base_check("submission_pack_manifest_go", repo_root, path)
    payload = _read_json(path)
    if isinstance(payload, JsonReadError):
        return _fail(check, payload.reason)
    if not isinstance(payload, dict):
        return _fail(check, "manifest is not a JSON object")
    required = payload.get("required_before_submit")
    ok = (
        payload.get("schema_version") == "qwenguard-submission-pack.v1"
        and payload.get("outcome") == "GO"
        and payload.get("submission_readiness") == "NARROW_CLAIM"
        and isinstance(required, list)
        and len(required) >= 5
    )
    check["ok"] = ok
    check["reason"] = "submission pack generated and still claim-safe" if ok else "submission pack manifest is incomplete"
    check["evidence"] = {
        "schema_version": payload.get("schema_version"),
        "outcome": payload.get("outcome"),
        "submission_readiness": payload.get("submission_readiness"),
        "required_before_submit_count": len(required) if isinstance(required, list) else 0,
    }
    return check


def _check_camera_report(repo_root: Path, path: Path) -> dict[str, Any]:
    check = _base_check("so101_camera_report_go", repo_root, path)
    payload = _read_json(path)
    if isinstance(payload, JsonReadError):
        return _fail(check, payload.reason)
    if not isinstance(payload, dict):
        return _fail(check, "camera report is not a JSON object")
    pass_conditions = payload.get("pass_conditions")
    capture = payload.get("capture")
    output_name = payload.get("output_path")
    if isinstance(capture, dict) and isinstance(capture.get("output_path"), str):
        output_name = capture["output_path"]
    frame_path, frame_error = _neighbor_artifact_path(repo_root=repo_root, anchor=path, raw_value=output_name)
    frame_sha = _file_sha256(frame_path) if frame_path is not None and frame_path.is_file() else ""
    ok = (
        payload.get("schema_version") == "so101-camera-capture-report.v1"
        and payload.get("outcome") == "GO"
        and isinstance(pass_conditions, dict)
        and pass_conditions.get("dependencies_available") is True
        and pass_conditions.get("frame_captured") is True
        and pass_conditions.get("trace_only_motion_boundary_preserved") is True
        and frame_path is not None
        and frame_path.is_file()
    )
    check["ok"] = ok
    check["reason"] = (
        "SO-101 camera frame captured through trace-only path"
        if ok
        else frame_error or "SO-101 camera report is not GO"
    )
    check["evidence"] = {
        "schema_version": payload.get("schema_version"),
        "outcome": payload.get("outcome"),
        "camera_name": payload.get("camera_name"),
        "pass_conditions": pass_conditions if isinstance(pass_conditions, dict) else {},
        "frame_path": _display_path(repo_root, frame_path) if frame_path is not None and frame_path.is_file() else "",
        "frame_sha256": frame_sha,
        "frame_error": frame_error,
    }
    return check


def _check_trace(repo_root: Path, path: Path, *, mode: str, expected_gate_decision: str) -> dict[str, Any]:
    check = _base_check(f"{mode}_decisiontrace_verifies", repo_root, path)
    payload = _read_json(path)
    if isinstance(payload, JsonReadError):
        return _fail(check, payload.reason)
    if not isinstance(payload, dict):
        return _fail(check, "trace is not a JSON object")
    try:
        trace = trace_from_dict(payload)
        summary_sha = verify_trace(trace)
    except (KeyError, TypeError, ValueError) as exc:
        check["evidence"] = {"error_type": exc.__class__.__name__}
        return _fail(check, "trace verification failed")
    commands = [event.command for event in trace.events]
    gate_commands = [command for command in commands if command.get("type") == "qwenguard_outcome_gate"]
    action_commands = [command for command in commands if command.get("type") == "physical_action_intent"]
    gate_decision = gate_commands[0].get("gate_decision") if gate_commands else None
    no_motion = bool(action_commands) and all(command.get("motion_executed") is False for command in action_commands)
    ok = gate_decision == expected_gate_decision and no_motion
    check["ok"] = ok
    check["reason"] = (
        f"{mode} trace verifies with {expected_gate_decision} and no executed motion"
        if ok
        else f"{mode} trace did not match expected gate/no-motion boundary"
    )
    check["evidence"] = {
        "schema_version": trace.schema_version,
        "summary_sha": summary_sha,
        "gate_decision": gate_decision,
        "event_count": len(trace.events),
        "no_motion_executed": no_motion,
    }
    return check


def _check_trial_trace_dir(repo_root: Path, path: Path) -> dict[str, Any]:
    check = _base_check("measured_trial_traces_verify", repo_root, path)
    if not path.is_dir():
        return _fail(check, "measured trial trace directory is missing")
    trace_paths = sorted(path.glob("*.json"))
    if not trace_paths:
        return _fail(check, "measured trial trace directory has no JSON traces")
    summary_shas: list[str] = []
    invalid_reasons: list[str] = []
    for trace_path in trace_paths:
        payload = _read_json(trace_path)
        display_path = _display_path(repo_root, trace_path)
        if isinstance(payload, JsonReadError):
            invalid_reasons.append(f"{display_path}: {payload.reason}")
            continue
        if not isinstance(payload, dict):
            invalid_reasons.append(f"{display_path}: trace is not a JSON object")
            continue
        try:
            trace = trace_from_dict(payload)
            summary_sha = verify_trace(trace)
            _validate_trial_trace_shape(trace)
        except (KeyError, TypeError, ValueError) as exc:
            invalid_reasons.append(f"{display_path}: {exc.__class__.__name__}")
        else:
            summary_shas.append(summary_sha)
    ok = bool(summary_shas) and not invalid_reasons
    check["ok"] = ok
    check["reason"] = "measured trial traces verify" if ok else "measured trial traces did not all verify"
    check["evidence"] = {
        "trace_count": len(trace_paths),
        "verified_trace_count": len(summary_shas),
        "summary_shas": summary_shas,
        "invalid_reason_count": len(invalid_reasons),
        "invalid_reasons": invalid_reasons[:5],
    }
    return check


def _check_trial_csv(repo_root: Path, path: Path, *, verified_trace_summaries: set[str]) -> dict[str, Any]:
    check = _base_check("measured_trial_csv_has_rows", repo_root, path)
    if not path.is_file():
        return _fail(check, "trial CSV is missing")
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (csv.Error, UnicodeDecodeError) as exc:
        return _fail(check, f"trial CSV could not be parsed: {exc}")
    valid_rows = 0
    invalid_reasons: list[str] = []
    for index, row in enumerate(rows, start=1):
        if all(not str(value or "").strip() for value in row.values()):
            continue
        try:
            TrialRecord(
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
            trace_summary_sha = str(row.get("trace_summary_sha", ""))
            if trace_summary_sha not in verified_trace_summaries:
                invalid_reasons.append(f"row {index}: trace_summary_sha is not bound to an audited trace")
            else:
                valid_rows += 1
    ok = valid_rows > 0
    check["ok"] = ok
    check["reason"] = "trial CSV contains validated measured rows" if ok else "trial CSV has no validated measured rows"
    check["evidence"] = {
        "row_count": len(rows),
        "valid_row_count": valid_rows,
        "invalid_row_count": len(invalid_reasons),
        "invalid_reasons": invalid_reasons[:5],
        "verified_trace_summary_count": len(verified_trace_summaries),
        "trace_dependency_satisfied": bool(verified_trace_summaries),
    }
    return check


def _check_trial_summary(
    repo_root: Path,
    path: Path,
    *,
    trial_csv: Path,
    trial_trace_dir: Path,
    valid_row_count: int,
    verified_trace_summaries: set[str],
) -> dict[str, Any]:
    check = _base_check("measured_trial_summary_go", repo_root, path)
    payload = _read_json(path)
    if isinstance(payload, JsonReadError):
        return _fail(check, payload.reason)
    if not isinstance(payload, dict):
        return _fail(check, "trial summary is not a JSON object")
    inputs = payload.get("inputs")
    checks = payload.get("checks")
    aggregate = payload.get("aggregate")
    bindings = payload.get("trial_bindings")
    expected_csv_path = _display_path(repo_root, trial_csv)
    expected_trace_dir = _display_path(repo_root, trial_trace_dir)
    expected_csv_sha = _file_sha256(trial_csv) if trial_csv.is_file() else ""
    total_trials = aggregate.get("total_trials") if isinstance(aggregate, dict) else None
    required_summary_checks = {
        "trial_csv_present",
        "trial_csv_schema_valid",
        "trial_rows_present",
        "trial_trace_dir_present",
        "trial_bindings_verify",
        "no_duplicate_trial_ids",
        "secret_material_absent",
        "raw_float_free_summary",
    }
    summary_check_keys = set(checks) if isinstance(checks, dict) else set()
    missing_summary_checks = sorted(required_summary_checks - summary_check_keys)
    summary_checks_ok = (
        isinstance(checks, dict)
        and not missing_summary_checks
        and all(checks.get(key) is True for key in required_summary_checks)
    )
    binding_errors = _trial_summary_binding_errors(
        repo_root=repo_root,
        trial_trace_dir=trial_trace_dir,
        bindings=bindings,
        verified_trace_summaries=verified_trace_summaries,
    )
    bindings_ok = (
        isinstance(bindings, list)
        and len(bindings) == total_trials
        and not binding_errors
    )
    ok = (
        payload.get("schema_version") == "qwenguard-trial-summary.v1"
        and payload.get("outcome") == "GO"
        and payload.get("trial_readiness") == "READY"
        and isinstance(inputs, dict)
        and inputs.get("trial_csv") == expected_csv_path
        and inputs.get("trial_trace_dir") == expected_trace_dir
        and payload.get("csv_sha256") == expected_csv_sha
        and isinstance(aggregate, dict)
        and isinstance(total_trials, int)
        and total_trials > 0
        and total_trials == valid_row_count
        and bindings_ok
        and summary_checks_ok
        and payload.get("invalid_reason_count") == 0
    )
    check["ok"] = ok
    check["reason"] = "measured trial summary is GO and bound to CSV/traces" if ok else "trial summary is not GO or not bound to audited trial evidence"
    check["evidence"] = {
        "schema_version": payload.get("schema_version"),
        "outcome": payload.get("outcome"),
        "trial_readiness": payload.get("trial_readiness"),
        "total_trials": total_trials,
        "valid_row_count": valid_row_count,
        "binding_count": len(bindings) if isinstance(bindings, list) else 0,
        "verified_binding_count": (
            sum(1 for binding in bindings if isinstance(binding, dict) and binding.get("verified") is True)
            if isinstance(bindings, list)
            else 0
        ),
        "binding_error_count": len(binding_errors),
        "binding_errors": binding_errors[:5],
        "csv_sha256_matches": payload.get("csv_sha256") == expected_csv_sha,
        "input_trial_csv": inputs.get("trial_csv") if isinstance(inputs, dict) else None,
        "input_trial_trace_dir": inputs.get("trial_trace_dir") if isinstance(inputs, dict) else None,
        "missing_summary_checks": missing_summary_checks,
        "summary_checks_ok": summary_checks_ok,
        "invalid_reason_count": payload.get("invalid_reason_count"),
    }
    return check


def _trial_summary_binding_errors(
    *,
    repo_root: Path,
    trial_trace_dir: Path,
    bindings: object,
    verified_trace_summaries: set[str],
) -> list[str]:
    if not isinstance(bindings, list):
        return ["trial_bindings is not a list"]
    errors: list[str] = []
    for index, binding in enumerate(bindings):
        if not isinstance(binding, dict):
            errors.append(f"binding {index}: not an object")
            continue
        trial_id = binding.get("trial_id")
        trace_path_value = binding.get("trace_path")
        trace_summary_sha = binding.get("trace_summary_sha")
        computed_summary_sha = binding.get("computed_summary_sha")
        if binding.get("verified") is not True:
            errors.append(f"binding {index}: verified is not true")
        if not isinstance(trial_id, str) or not TRIAL_ID_RE.fullmatch(trial_id):
            errors.append(f"binding {index}: invalid trial_id")
        if not isinstance(trace_summary_sha, str) or not _is_hex_64(trace_summary_sha):
            errors.append(f"binding {index}: invalid trace_summary_sha")
        elif trace_summary_sha not in verified_trace_summaries:
            errors.append(f"binding {index}: trace_summary_sha not verified by audit")
        if computed_summary_sha is not None and computed_summary_sha != trace_summary_sha:
            errors.append(f"binding {index}: computed_summary_sha mismatch")
        trace_path_error = _trial_summary_trace_path_error(
            repo_root=repo_root,
            trial_trace_dir=trial_trace_dir,
            raw_value=trace_path_value,
        )
        if trace_path_error:
            errors.append(f"binding {index}: {trace_path_error}")
    return errors


def _trial_summary_trace_path_error(*, repo_root: Path, trial_trace_dir: Path, raw_value: object) -> str:
    if not isinstance(raw_value, str) or not raw_value:
        return "trace_path missing"
    raw_path = Path(raw_value)
    if raw_path.is_absolute() or ".." in raw_path.parts:
        return "trace_path must be repo-relative"
    if raw_path.suffix != ".json":
        return "trace_path must be a JSON trace"
    try:
        resolved = _repo_path(repo_root, raw_path)
    except ValueError:
        return "trace_path must stay inside repository"
    try:
        resolved.relative_to(trial_trace_dir.resolve())
    except ValueError:
        return "trace_path is outside audited trial trace directory"
    if not resolved.is_file():
        return "trace_path file is missing"
    return ""


def _is_hex_64(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", value))


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


def _check_ecs_report(repo_root: Path, path: Path) -> dict[str, Any]:
    check = _base_check("ecs_report_is_public_go", repo_root, path)
    payload = _read_json(path)
    if isinstance(payload, JsonReadError):
        return _fail(check, payload.reason)
    if not isinstance(payload, dict):
        return _fail(check, "ECS report is not a JSON object")
    pass_conditions = payload.get("pass_conditions")
    deployment = payload.get("deployment")
    checks = payload.get("checks")
    required_pass_conditions = {
        "healthz",
        "readyz",
        "camera-fixture",
        "swarm-demo",
        "swarm-demo_summary.json",
        "deployed_commit_recorded",
        "proof_mode_is_ecs_public",
        "ecs_region_recorded",
        "ecs_instance_id_recorded",
        "ecs_public_ip_is_global",
        "base_url_is_public_endpoint",
        "base_url_matches_public_ip_when_ip_literal",
    }
    pass_condition_keys = set(pass_conditions) if isinstance(pass_conditions, dict) else set()
    required_check_names = {
        "healthz",
        "readyz",
        "camera-fixture",
        "swarm-demo",
        "swarm-demo_summary.json",
    }
    check_names = {
        str(item.get("name"))
        for item in checks
        if isinstance(item, dict) and item.get("ok") is True
    } if isinstance(checks, list) else set()
    required_conditions_ok = (
        isinstance(pass_conditions, dict)
        and required_pass_conditions.issubset(pass_condition_keys)
        and all(pass_conditions.get(key) is True for key in required_pass_conditions)
        and required_check_names.issubset(check_names)
        and any(
            key.startswith("qwen-ping_model_") and value is True
            for key, value in pass_conditions.items()
        )
    )
    ok = (
        payload.get("schema_version") == "ecs-smoke-report.v1"
        and payload.get("outcome") == "GO"
        and payload.get("proof_mode") == "ecs-public"
        and required_conditions_ok
        and isinstance(deployment, dict)
        and deployment.get("deployment_context_verified") is True
    )
    check["ok"] = ok
    check["reason"] = "Alibaba ECS public endpoint proof is GO" if ok else "ECS report is not public GO proof"
    check["evidence"] = {
        "schema_version": payload.get("schema_version"),
        "outcome": payload.get("outcome"),
        "proof_mode": payload.get("proof_mode"),
        "deployed_commit": payload.get("deployed_commit"),
        "missing_pass_conditions": sorted(required_pass_conditions - pass_condition_keys),
        "missing_endpoint_checks": sorted(required_check_names - check_names),
        "qwen_ping_condition_present": any(
            key.startswith("qwen-ping_model_") and value is True
            for key, value in pass_conditions.items()
        )
        if isinstance(pass_conditions, dict)
        else False,
        "deployment_context_verified": (
            deployment.get("deployment_context_verified") if isinstance(deployment, dict) else None
        ),
    }
    return check


def _check_video_review(repo_root: Path, path: Path) -> dict[str, Any]:
    if not path.is_file():
        check = _base_check("human_video_review_present", repo_root, path)
        return _fail(check, "final video review note is missing")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        check = _base_check("human_video_review_present", repo_root, path)
        return _fail(check, f"final video review note is not UTF-8: {exc}")
    return check_video_review_text(repo_root=repo_root, path=path, text=text)


def check_video_review_text(*, repo_root: Path, path: Path, text: str) -> dict[str, Any]:
    check = _base_check("human_video_review_present", repo_root, path)
    missing_phrases = [phrase for phrase in VIDEO_REVIEW_REQUIRED_PHRASES if phrase not in text]
    fields, duplicate_fields = _parse_review_fields(text)
    missing_fields = [field for field in VIDEO_REVIEW_REQUIRED_FIELDS if field.lower() not in fields]
    invalid_fields = _invalid_review_fields(fields, repo_root=repo_root)
    for field in _duplicate_required_review_fields(duplicate_fields):
        invalid_fields[field] = "duplicate field"
    if _contains_secret_like_material(text):
        invalid_fields["Secrets-reviewed"] = "review note contains secret-like material"
    ok = not missing_phrases and not missing_fields and not invalid_fields
    check["ok"] = ok
    check["reason"] = (
        "human video review records explicit reviewer, artifact, and claim checks"
        if ok
        else "human video review lacks required signoff fields or labels"
    )
    check["evidence"] = {
        "byte_count": len(text.encode("utf-8")),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "missing_phrases": missing_phrases,
        "missing_fields": missing_fields,
        "invalid_fields": invalid_fields,
        "duplicate_fields": duplicate_fields,
        "video_artifact": _video_artifact_evidence(repo_root=repo_root, raw_value=fields.get("video-artifact", "")),
    }
    return check


def _parse_review_fields(text: str) -> tuple[dict[str, str], dict[str, int]]:
    fields: dict[str, str] = {}
    duplicate_fields: dict[str, int] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized_key = key.strip().lower()
        if normalized_key:
            if normalized_key in fields:
                duplicate_fields[normalized_key] = duplicate_fields.get(normalized_key, 1) + 1
                continue
            fields[normalized_key] = value.strip()
    return fields, duplicate_fields


def _duplicate_required_review_fields(duplicate_fields: dict[str, int]) -> list[str]:
    canonical_names = {field.lower(): field for field in VIDEO_REVIEW_REQUIRED_FIELDS}
    return [canonical_names[key] for key in sorted(duplicate_fields) if key in canonical_names]


def _invalid_review_fields(fields: dict[str, str], *, repo_root: Path) -> dict[str, str]:
    invalid: dict[str, str] = {}
    for field in VIDEO_REVIEW_REQUIRED_FIELDS:
        value = fields.get(field.lower(), "")
        reason = _review_field_error(field, value, repo_root=repo_root)
        if reason:
            invalid[field] = reason
    return invalid


def _review_field_error(field: str, value: str, *, repo_root: Path) -> str | None:
    if not value:
        return "empty"
    if _contains_secret_like_material(value):
        return "contains secret-like material"
    lowered = value.lower()
    if any(term in lowered for term in VIDEO_REVIEW_PLACEHOLDER_TERMS) or "<" in value or ">" in value:
        return "placeholder value"
    if field == "Review-date":
        try:
            if not VIDEO_REVIEW_DATE_RE.match(value):
                return "must be YYYY-MM-DD"
            date.fromisoformat(value)
        except ValueError:
            return "must be YYYY-MM-DD"
    if field in VIDEO_REVIEW_YES_FIELDS and lowered not in {"yes", "true", "reviewed", "checked"}:
        return "must be yes/reviewed"
    if field == "Video-artifact":
        return _video_artifact_error(repo_root=repo_root, raw_value=value)
    return None


def _video_artifact_error(*, repo_root: Path, raw_value: str) -> str | None:
    parsed = urlparse(raw_value)
    if parsed.scheme == "http":
        return "remote video artifact URL must use https"
    if parsed.scheme == "https":
        return None if parsed.netloc else "must name a video file or URL"
    path = Path(raw_value)
    if path.is_absolute():
        return "must be repo-relative path or URL"
    if ".." in path.parts:
        return "video artifact path must stay inside the repository checkout"
    if PurePosixPath(raw_value).suffix.lower() not in {".mp4", ".mov", ".webm"}:
        return "must name a video file or URL"
    resolved = _repo_path(repo_root, path)
    if not resolved.is_file():
        return "video artifact file is missing"
    return None


def _video_artifact_evidence(*, repo_root: Path, raw_value: str) -> dict[str, str]:
    if not raw_value:
        return {}
    parsed = urlparse(raw_value)
    if parsed.scheme in {"http", "https"}:
        return {"kind": "url", "url_sha256": hashlib.sha256(raw_value.encode("utf-8")).hexdigest()}
    path = Path(raw_value)
    if path.is_absolute() or ".." in path.parts:
        return {"kind": "invalid-path"}
    resolved = _repo_path(repo_root, path)
    evidence = {
        "kind": "repo-file",
        "path": _display_path(repo_root, resolved),
        "exists": str(resolved.is_file()).lower(),
    }
    if resolved.is_file():
        evidence["sha256"] = _file_sha256(resolved)
    return evidence


def _contains_secret_like_material(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


def _base_check(name: str, repo_root: Path, path: Path) -> dict[str, Any]:
    return {
        "name": name,
        "ok": False,
        "path": _display_path(repo_root, path),
        "reason": "not checked",
        "evidence": {},
    }


def _fail(check: dict[str, Any], reason: str) -> dict[str, Any]:
    check["ok"] = False
    check["reason"] = reason
    return check


def _read_json(path: Path) -> object:
    if not path.is_file():
        return JsonReadError(reason="file is missing")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return JsonReadError(reason="file is not valid JSON")
    except UnicodeDecodeError:
        return JsonReadError(reason="file is not valid UTF-8")


class JsonReadError:
    def __init__(self, *, reason: str) -> None:
        self.reason = reason


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


def _neighbor_artifact_path(*, repo_root: Path, anchor: Path, raw_value: object) -> tuple[Path | None, str]:
    if not isinstance(raw_value, str) or not raw_value.strip():
        return None, "camera report does not reference a captured frame artifact"
    raw_path = Path(raw_value)
    if raw_path.is_absolute():
        return None, "camera frame artifact path must be relative"
    resolved = (anchor.parent / raw_path).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError:
        return None, "camera frame artifact path must stay inside the repository checkout"
    return resolved, ""


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
