#!/usr/bin/env python3
"""Prepare the human-reviewed Alibaba ECS proof note."""

from __future__ import annotations

import argparse
import ipaddress
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import urlparse

from accountable_swarm.trace.models import canonical_json


DEFAULT_OUT = Path("runs/ecs/ecs_proof_review.md")
DEFAULT_ECS_REPORT = Path("runs/ecs/ecs_smoke_report.json")
VIDEO_REVIEW_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Authorization:[ \t]*Bearer[ \t]+(?!<redacted>(?:$|[ \t]))\S+", re.IGNORECASE),
    re.compile(r"ALIBABA_API_KEY[ \t]*=[ \t]*\S+", re.IGNORECASE),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh(?:p|o|u|s|r)_[A-Za-z0-9_]{12,}"),
    re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9._-]{20,}"),
)
GIT_OID_RE = re.compile(r"[0-9a-f]{40}")
TEXT_ARTIFACT_SUFFIXES = {".txt", ".log", ".md"}
LOCAL_ARTIFACT_SUFFIXES = TEXT_ARTIFACT_SUFFIXES | {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov"}
MAX_TEXT_ARTIFACT_BYTES = 1024 * 1024
REQUIRED_ECS_PASS_CONDITIONS = {
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
REQUIRED_ECS_CHECK_NAMES = {
    "healthz",
    "readyz",
    "camera-fixture",
    "swarm-demo",
    "swarm-demo_summary.json",
}
CONFIRMATION_FLAGS = {
    "report_go": "ECS-report-GO-reviewed",
    "alibaba_context": "Alibaba-context-reviewed",
    "public_endpoint": "Public-endpoint-reviewed",
    "deployed_commit": "Deployed-commit-reviewed",
    "security_group": "Security-group-reviewed",
    "secrets": "Secrets-reviewed",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--ecs-report", type=Path, default=DEFAULT_ECS_REPORT)
    parser.add_argument("--terminal-artifact", required=True, help="HTTPS URL or repo-relative transcript/screenshot path.")
    parser.add_argument("--reviewed-by", required=True)
    parser.add_argument("--review-date", required=True, help="Literal YYYY-MM-DD review date.")
    parser.add_argument("--notes", default="")
    parser.add_argument("--allow-overwrite", action="store_true")
    for flag_name, field_name in CONFIRMATION_FLAGS.items():
        parser.add_argument(
            f"--confirm-{flag_name.replace('_', '-')}",
            action="store_true",
            help=f"Confirm ECS proof review field `{field_name}: yes`.",
        )
    args = parser.parse_args()

    missing = [
        field_name
        for flag_name, field_name in CONFIRMATION_FLAGS.items()
        if not getattr(args, f"confirm_{flag_name}")
    ]
    if missing:
        print(
            "ECS proof review note not written; missing explicit confirmations: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        return 2
    for name, value in {
        "reviewed-by": args.reviewed_by,
        "review-date": args.review_date,
        "terminal-artifact": args.terminal_artifact,
    }.items():
        if _has_control_chars(value):
            print(f"ECS proof review note failed: {name} must not contain control characters", file=sys.stderr)
            return 2

    try:
        repo_root = _find_repo_root(Path.cwd())
        out = _repo_path(repo_root, args.out)
        ecs_report_path = _repo_path(repo_root, args.ecs_report)
    except ValueError as exc:
        print(f"ECS proof review note failed: {exc}", file=sys.stderr)
        return 2
    if out.exists() and not args.allow_overwrite:
        print(f"ECS proof review note failed: output already exists: {_display_path(repo_root, out)}", file=sys.stderr)
        return 2
    if out.exists() and out.is_dir():
        print(f"ECS proof review note failed: output path is a directory: {_display_path(repo_root, out)}", file=sys.stderr)
        return 2
    if out.suffix != ".md":
        print("ECS proof review note failed: output path must end in .md", file=sys.stderr)
        return 2
    if out.parent.exists() and not out.parent.is_dir():
        print(f"ECS proof review note failed: output parent is not a directory: {out.parent}", file=sys.stderr)
        return 2

    report_result = _load_go_ecs_report(ecs_report_path)
    if isinstance(report_result, str):
        print(f"ECS proof review note failed: {report_result}", file=sys.stderr)
        return 4
    artifact_result = _validate_terminal_artifact(repo_root, args.terminal_artifact)
    if isinstance(artifact_result, str):
        print(f"ECS proof review note failed: {artifact_result}", file=sys.stderr)
        return 4

    report = report_result
    note = _render_review_note(
        repo_root=repo_root,
        reviewed_by=args.reviewed_by,
        review_date=args.review_date,
        ecs_report_path=ecs_report_path,
        terminal_artifact=artifact_result,
        report=report,
        notes=args.notes,
    )
    validation_error = _review_note_error(note)
    if validation_error:
        print(f"ECS proof review note failed: {validation_error}", file=sys.stderr)
        return 4

    tmp = out.with_name(out.name + ".tmp")
    success = False
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(note, encoding="utf-8")
        tmp.replace(out)
        success = True
    except OSError as exc:
        print(f"ECS proof review note failed: {exc}", file=sys.stderr)
        return 2
    finally:
        if not success:
            tmp.unlink(missing_ok=True)

    print("outcome GO")
    print(f"review {_display_path(repo_root, out)}")
    return 0


def _load_go_ecs_report(path: Path) -> dict[str, Any] | str:
    if not path.is_file():
        return "ECS smoke report file is missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return f"ECS smoke report could not be read: {exc.__class__.__name__}"
    if not isinstance(payload, dict):
        return "ECS smoke report is not a JSON object"
    deployment = payload.get("deployment")
    if (
        payload.get("schema_version") != "ecs-smoke-report.v1"
        or payload.get("outcome") != "GO"
        or payload.get("proof_mode") != "ecs-public"
        or not isinstance(deployment, dict)
        or deployment.get("provider_asserted") != "Alibaba Cloud ECS"
        or deployment.get("deployment_context_verified") is not True
    ):
        return "ECS smoke report is not GO ecs-public proof"
    if not _report_has_required_ecs_evidence(payload, deployment):
        return "ECS smoke report is missing required ECS public proof evidence"
    return payload


def _report_has_required_ecs_evidence(payload: dict[str, Any], deployment: dict[str, Any]) -> bool:
    for key in ("ecs_region", "ecs_instance_id", "ecs_public_ip"):
        value = deployment.get(key)
        if not isinstance(value, str) or not value.strip():
            return False
    if deployment.get("base_url_is_public_endpoint") is not True:
        return False
    if deployment.get("base_url_matches_public_ip_when_ip_literal") is not True:
        return False
    if not _is_public_ip(str(deployment.get("ecs_public_ip", ""))):
        return False
    if not _is_public_base_url(str(payload.get("base_url", ""))):
        return False
    if not isinstance(payload.get("deployed_commit"), str) or not GIT_OID_RE.fullmatch(payload["deployed_commit"]):
        return False
    pass_conditions = payload.get("pass_conditions")
    if not isinstance(pass_conditions, dict):
        return False
    pass_condition_keys = set(pass_conditions)
    if not REQUIRED_ECS_PASS_CONDITIONS.issubset(pass_condition_keys):
        return False
    if not all(pass_conditions.get(key) is True for key in REQUIRED_ECS_PASS_CONDITIONS):
        return False
    if not any(
        isinstance(key, str) and key.startswith("qwen-ping_model_") and value is True
        for key, value in pass_conditions.items()
    ):
        return False
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return False
    check_names = {
        str(item.get("name"))
        for item in checks
        if isinstance(item, dict) and item.get("ok") is True
    }
    return REQUIRED_ECS_CHECK_NAMES.issubset(check_names)


def _validate_terminal_artifact(repo_root: Path, raw_value: str) -> dict[str, str] | str:
    if _contains_secret_material(raw_value):
        return "terminal artifact reference contains secret-like material"
    parsed = urlparse(raw_value)
    if parsed.scheme:
        if parsed.scheme != "https" or not parsed.netloc:
            return "remote terminal artifact URL must use https"
        return {"kind": "https", "value": raw_value, "exists": "not checked"}
    try:
        artifact_path = _repo_path(repo_root, Path(raw_value))
    except ValueError as exc:
        return str(exc)
    if artifact_path.suffix.lower() not in LOCAL_ARTIFACT_SUFFIXES:
        return "terminal artifact must be a transcript, screenshot, or video file"
    if not artifact_path.is_file():
        return "terminal artifact file is missing"
    if artifact_path.suffix.lower() in TEXT_ARTIFACT_SUFFIXES:
        try:
            byte_count = artifact_path.stat().st_size
        except OSError:
            return "text terminal artifact could not be inspected"
        if byte_count > MAX_TEXT_ARTIFACT_BYTES:
            return "text terminal artifact is too large; provide a sanitized excerpt"
        try:
            text = artifact_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return "text terminal artifact is not UTF-8"
        except OSError:
            return "text terminal artifact could not be read"
        if _contains_secret_material(text):
            return "terminal artifact file contains secret-like material"
    return {"kind": "local", "value": _display_path(repo_root, artifact_path), "exists": "true"}


def _render_review_note(
    *,
    repo_root: Path,
    reviewed_by: str,
    review_date: str,
    ecs_report_path: Path,
    terminal_artifact: dict[str, str],
    report: dict[str, Any],
    notes: str,
) -> str:
    deployment = report["deployment"]
    lines = [
        "# Alibaba ECS Proof Review",
        "",
        f"Reviewed-by: {reviewed_by}",
        f"Review-date: {review_date}",
        f"ECS-report: {_display_path(repo_root, ecs_report_path)}",
        f"Terminal-artifact: {terminal_artifact['value']}",
        f"Terminal-artifact-kind: {terminal_artifact['kind']}",
        f"Terminal-artifact-exists: {terminal_artifact['exists']}",
        f"ECS-region: {deployment.get('ecs_region', '')}",
        f"ECS-instance-id: {deployment.get('ecs_instance_id', '')}",
        f"ECS-public-ip: {deployment.get('ecs_public_ip', '')}",
        f"Base-url: {report.get('base_url', '')}",
        f"Deployed-commit: {report.get('deployed_commit', '')}",
        "ECS-report-GO-reviewed: yes",
        "Alibaba-context-reviewed: yes",
        "Public-endpoint-reviewed: yes",
        "Deployed-commit-reviewed: yes",
        "Security-group-reviewed: yes",
        "Secrets-reviewed: yes",
        "",
        "Alibaba ECS proof is claimed only because the checked ECS smoke report is GO with proof_mode ecs-public.",
        "The terminal or screenshot artifact was reviewed for Alibaba ECS context and secret exposure.",
        "This note does not claim production hosting, availability, latency, reliability, SO-101 operation, or Qwen onboard execution.",
        "",
        "## Reviewer Notes",
        "",
        notes.strip() or "No additional notes.",
        "",
    ]
    return "\n".join(lines)


def _review_note_error(text: str) -> str:
    if _contains_secret_material(text):
        return "review note contains secret-like material"
    fields = _parse_fields(text)
    required = {
        "Reviewed-by",
        "Review-date",
        "ECS-report",
        "Terminal-artifact",
        "Terminal-artifact-kind",
        "ECS-report-GO-reviewed",
        "Alibaba-context-reviewed",
        "Public-endpoint-reviewed",
        "Deployed-commit-reviewed",
        "Security-group-reviewed",
        "Secrets-reviewed",
    }
    missing = sorted(required - set(fields))
    if missing:
        return "review note is missing fields: " + ", ".join(missing)
    if not VIDEO_REVIEW_DATE_RE.fullmatch(fields["Review-date"]):
        return "review date must be YYYY-MM-DD"
    for field in CONFIRMATION_FLAGS.values():
        if fields.get(field) != "yes":
            return f"{field} must be yes"
    placeholder_terms = ("todo", "tbd", "placeholder", "replace", "example", "your ", "n/a", "none")
    for key, value in fields.items():
        lowered = value.lower()
        if any(term in lowered for term in placeholder_terms):
            return f"{key} contains placeholder text"
    return ""


def _parse_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if line.strip() == "## Reviewer Notes":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in fields:
            fields[key] = value
    return fields


def _is_public_ip(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_global
    except ValueError:
        return False


def _is_public_base_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        return False
    return _is_public_ip(parsed.hostname)


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists() and (candidate / "pyproject.toml").is_file():
            return candidate
    raise ValueError("could not find repository root")


def _repo_path(repo_root: Path, raw_path: Path) -> Path:
    if raw_path.is_absolute():
        raise ValueError("path must be repo-relative")
    if ".." in raw_path.parts:
        raise ValueError("path must stay inside the repository checkout")
    resolved = (repo_root / raw_path).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError("path must stay inside the repository checkout") from exc
    return resolved


def _display_path(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _contains_secret_material(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def _has_control_chars(text: str) -> bool:
    return any(ord(ch) < 32 and ch not in "\t" for ch in text)


if __name__ == "__main__":
    raise SystemExit(main())
