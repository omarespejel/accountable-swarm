#!/usr/bin/env python3
"""Collect a sanitized Alibaba ECS smoke-proof report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin

from accountable_swarm.trace.models import canonical_json


REPORT_SCHEMA_VERSION = "ecs-smoke-report.v1"
DEFAULT_OUT = Path("runs/ecs/ecs_smoke_report.json")
DEFAULT_MODEL = "qwen-plus"
TEXT_PREVIEW_LIMIT = 128


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Base URL for the deployed demo server.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--commit", default=None, help="Deployed commit SHA. Defaults to local git HEAD when available.")
    parser.add_argument("--qwen-model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout-seconds", type=int, default=10)
    parser.add_argument(
        "--allow-narrow-claim",
        action="store_true",
        help="Write the report even when required ECS/Qwen proof checks fail.",
    )
    args = parser.parse_args()

    if args.timeout_seconds <= 0:
        print("timeout must be positive", file=sys.stderr)
        return 2

    try:
        report = collect_report(
            base_url=args.base_url,
            qwen_model=args.qwen_model,
            deployed_commit=args.commit or _git_head(),
            timeout_seconds=args.timeout_seconds,
        )
    except ValueError as exc:
        print(f"ecs smoke report failed: {exc}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(canonical_json(report) + "\n", encoding="utf-8")

    print(f"outcome {report['outcome']}")
    print(f"wrote {args.out}")
    if report["outcome"] != "GO" and not args.allow_narrow_claim:
        return 4
    return 0


def collect_report(*, base_url: str, qwen_model: str, deployed_commit: str, timeout_seconds: int) -> dict[str, Any]:
    normalized_base_url = _normalize_base_url(base_url)
    checks = [
        _check_json(
            base_url=normalized_base_url,
            path="/healthz",
            timeout_seconds=timeout_seconds,
            validator=_validate_healthz,
        ),
        _check_json(
            base_url=normalized_base_url,
            path="/readyz",
            timeout_seconds=timeout_seconds,
            validator=_validate_readyz,
        ),
        _check_json(
            base_url=normalized_base_url,
            path="/camera-fixture",
            timeout_seconds=timeout_seconds,
            validator=_validate_camera_fixture,
        ),
        _check_text(
            base_url=normalized_base_url,
            path="/swarm-demo",
            timeout_seconds=timeout_seconds,
            validator=_validate_swarm_demo_html,
        ),
        _check_json(
            base_url=normalized_base_url,
            path="/swarm-demo/summary.json",
            timeout_seconds=timeout_seconds,
            validator=_validate_swarm_summary,
        ),
        _check_json(
            base_url=normalized_base_url,
            path=f"/qwen-ping?model={qwen_model}",
            timeout_seconds=timeout_seconds,
            validator=lambda payload: _validate_qwen_ping(payload, qwen_model=qwen_model),
        ),
    ]
    pass_conditions = {check["name"]: check["ok"] for check in checks}
    pass_conditions["deployed_commit_recorded"] = bool(deployed_commit.strip()) and deployed_commit != "unknown"
    outcome = "GO" if all(pass_conditions.values()) else "NARROW_CLAIM"
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "outcome": outcome,
        "base_url": normalized_base_url,
        "deployed_commit": deployed_commit,
        "qwen_model": qwen_model,
        "checks": checks,
        "pass_conditions": pass_conditions,
        "non_claims": [
            "not a production hosting claim",
            "not a public availability claim",
            "not a latency or reliability claim",
            "not physical robot behavior",
            "not SO-101 operation",
            "not Qwen onboard execution",
        ],
    }


def _check_json(
    *,
    base_url: str,
    path: str,
    timeout_seconds: int,
    validator: Any,
) -> dict[str, Any]:
    response = _fetch(base_url=base_url, path=path, timeout_seconds=timeout_seconds)
    check = _base_check(name=_check_name(path), path=path, response=response)
    payload = response.get("json")
    if not isinstance(payload, dict):
        check["ok"] = False
        check["reason"] = "response was not a JSON object"
        return check
    validation = validator(payload)
    check["ok"] = bool(validation["ok"])
    check["reason"] = validation["reason"]
    check["evidence"] = validation["evidence"]
    return check


def _check_text(
    *,
    base_url: str,
    path: str,
    timeout_seconds: int,
    validator: Any,
) -> dict[str, Any]:
    response = _fetch(base_url=base_url, path=path, timeout_seconds=timeout_seconds)
    check = _base_check(name=_check_name(path), path=path, response=response)
    validation = validator(response)
    check["ok"] = bool(validation["ok"])
    check["reason"] = validation["reason"]
    check["evidence"] = validation["evidence"]
    return check


def _fetch(*, base_url: str, path: str, timeout_seconds: int) -> dict[str, Any]:
    url = urljoin(f"{base_url}/", path.lstrip("/"))
    try:
        with request.urlopen(url, timeout=timeout_seconds) as resp:
            body = resp.read()
            return _response_payload(
                status_code=resp.status,
                content_type=resp.headers.get("Content-Type", ""),
                body=body,
            )
    except HTTPError as exc:
        body = exc.read()
        return _response_payload(
            status_code=exc.code,
            content_type=exc.headers.get("Content-Type", ""),
            body=body,
        )
    except (TimeoutError, URLError, OSError) as exc:
        return {
            "status_code": 0,
            "content_type": "",
            "body_sha256": "",
            "byte_count": 0,
            "error": type(exc).__name__,
        }


def _response_payload(*, status_code: int, content_type: str, body: bytes) -> dict[str, Any]:
    response: dict[str, Any] = {
        "status_code": status_code,
        "content_type": content_type,
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "byte_count": len(body),
    }
    if "application/json" in content_type:
        try:
            response["json"] = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            response["json_parse_error"] = True
    else:
        response["text_prefix"] = body[:TEXT_PREVIEW_LIMIT].decode("utf-8", errors="replace")
    return response


def _base_check(*, name: str, path: str, response: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "path": path,
        "status_code": response["status_code"],
        "content_type": response["content_type"],
        "body_sha256": response["body_sha256"],
        "byte_count": response["byte_count"],
        "ok": False,
        "reason": response.get("error", "not validated"),
    }


def _validate_healthz(payload: dict[str, Any]) -> dict[str, Any]:
    ok = payload.get("status") == "ok" and payload.get("service") == "accountable-swarm"
    return _validation(ok=ok, reason="healthz status/service match", evidence={"status": payload.get("status")})


def _validate_readyz(payload: dict[str, Any]) -> dict[str, Any]:
    key_present = payload.get("has_alibaba_api_key") is True
    ok = payload.get("status") == "ok" and key_present
    return _validation(
        ok=ok,
        reason="readyz status ok and Alibaba key present",
        evidence={
            "status": payload.get("status"),
            "has_alibaba_api_key": bool(payload.get("has_alibaba_api_key")),
            "default_vl_model": str(payload.get("default_vl_model", "")),
        },
    )


def _validate_camera_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    trace_sha = str(payload.get("trace_summary_sha", ""))
    ok = (
        payload.get("status") == "ok"
        and payload.get("decision") == "VETO"
        and payload.get("schema_version") == "decisiontrace.v1"
        and _is_hex_64(trace_sha)
    )
    return _validation(
        ok=ok,
        reason="camera fixture emits verified VETO DecisionTrace summary",
        evidence={
            "status": payload.get("status"),
            "decision": payload.get("decision"),
            "schema_version": payload.get("schema_version"),
            "trace_summary_sha": trace_sha,
        },
    )


def _validate_swarm_demo_html(response: dict[str, Any]) -> dict[str, Any]:
    text_prefix = str(response.get("text_prefix", ""))
    ok = response.get("status_code") == 200 and "<!doctype html>" in text_prefix.lower()
    return _validation(
        ok=ok,
        reason="swarm demo HTML served",
        evidence={
            "content_type": response.get("content_type", ""),
            "body_sha256": response.get("body_sha256", ""),
        },
    )


def _validate_swarm_summary(payload: dict[str, Any]) -> dict[str, Any]:
    index_sha = str(payload.get("index_sha256", ""))
    scenario_count = _int_or_zero(payload.get("scenario_count"))
    ok = payload.get("outcome") == "GO" and scenario_count >= 1 and _is_hex_64(index_sha)
    return _validation(
        ok=ok,
        reason="swarm demo summary reports GO",
        evidence={
            "outcome": payload.get("outcome"),
            "scenario_count": scenario_count,
            "index_sha256": index_sha,
        },
    )


def _validate_qwen_ping(payload: dict[str, Any], *, qwen_model: str) -> dict[str, Any]:
    ok = payload.get("status") == "ok" and payload.get("model") == qwen_model
    return _validation(
        ok=ok,
        reason="DashScope Qwen ping returned ok",
        evidence={"status": payload.get("status"), "model": payload.get("model")},
    )


def _validation(*, ok: bool, reason: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"ok": ok, "reason": reason, "evidence": evidence}


def _check_name(path: str) -> str:
    return path.strip("/").replace("/", "_").replace("?", "_").replace("=", "_") or "root"


def _normalize_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if not normalized.startswith(("http://", "https://")):
        raise ValueError("base URL must start with http:// or https://")
    return normalized


def _is_hex_64(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _git_head() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    head = result.stdout.strip()
    return head if _is_hex_64(head) else "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
