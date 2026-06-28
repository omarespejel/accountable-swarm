#!/usr/bin/env python3
"""Audit whether QwenGuard has enough evidence for Track 5 submission readiness."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Any

from accountable_swarm.qwenguard.trial import TrialRecord
from accountable_swarm.trace.models import canonical_json, trace_from_dict, verify_trace


REPORT_SCHEMA_VERSION = "qwenguard-submission-readiness-report.v1"
DEFAULT_OUT = Path("runs/submission/qwenguard-readiness-report.json")
DEFAULT_SUBMISSION_MANIFEST = Path("runs/submission/qwenguard-pack/manifest.json")
DEFAULT_SO101_CAMERA_REPORT = Path("runs/physical/qwenguard_physical_go/so101_capture_report.json")
DEFAULT_FIXTURE_TRACE = Path("runs/physical/qwenguard_physical_go/fixture_trace.json")
DEFAULT_DEGRADED_TRACE = Path("runs/physical/qwenguard_physical_go/degraded_trace.json")
DEFAULT_TRIAL_CSV = Path("runs/physical/qwenguard_so101_training_pack/trial_template.csv")
DEFAULT_TRIAL_TRACE_DIR = Path("runs/physical/qwenguard_trials/traces")
DEFAULT_ECS_REPORT = Path("runs/ecs/ecs_smoke_report.json")
DEFAULT_VIDEO_REVIEW = Path("runs/submission/final_video_review.md")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--submission-manifest", type=Path, default=DEFAULT_SUBMISSION_MANIFEST)
    parser.add_argument("--so101-camera-report", type=Path, default=DEFAULT_SO101_CAMERA_REPORT)
    parser.add_argument("--fixture-trace", type=Path, default=DEFAULT_FIXTURE_TRACE)
    parser.add_argument("--degraded-trace", type=Path, default=DEFAULT_DEGRADED_TRACE)
    parser.add_argument("--trial-csv", type=Path, default=DEFAULT_TRIAL_CSV)
    parser.add_argument("--trial-trace-dir", type=Path, default=DEFAULT_TRIAL_TRACE_DIR)
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
    checks = [
        _check_submission_manifest(repo_root, paths["submission_manifest"]),
        _check_camera_report(repo_root, paths["so101_camera_report"]),
        fixture_trace_check,
        degraded_trace_check,
        trial_trace_check,
        _check_trial_csv(repo_root, paths["trial_csv"], verified_trace_summaries=verified_trial_trace_summaries),
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
    check = _base_check("human_video_review_present", repo_root, path)
    if not path.is_file():
        return _fail(check, "final video review note is missing")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return _fail(check, f"final video review note is not UTF-8: {exc}")
    required_phrases = [
        "Qwen never controls motors",
        "SO-101",
        "Alibaba ECS",
        "AUTONOMOUS",
        "TELEOP",
        "SCRIPTED",
    ]
    missing = [phrase for phrase in required_phrases if phrase not in text]
    ok = not missing
    check["ok"] = ok
    check["reason"] = "human video review records required claim labels" if ok else "human video review lacks required labels"
    check["evidence"] = {
        "byte_count": len(text.encode("utf-8")),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "missing_phrases": missing,
    }
    return check


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
