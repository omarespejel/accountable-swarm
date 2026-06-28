#!/usr/bin/env python3
"""Collect a sanitized Alibaba ECS smoke-proof report."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse

from accountable_swarm.trace.models import canonical_json


REPORT_SCHEMA_VERSION = "ecs-smoke-report.v1"
SWARM_BUNDLE_SCHEMA_VERSION = "swarm-demo-bundle-report.v1"
DEFAULT_OUT = Path("runs/ecs/ecs_smoke_report.json")
DEFAULT_MODEL = "qwen-plus"
TEXT_PREVIEW_LIMIT = 128
PROOF_MODES = ("local-smoke", "ecs-public")
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Authorization:[ \t]*Bearer[ \t]+(?!<redacted>)\S+", re.IGNORECASE),
    re.compile(r"ALIBABA_API_KEY[ \t]*=[ \t]*\S+", re.IGNORECASE),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh(?:p|o|u|s|r)_[A-Za-z0-9_]{12,}"),
    re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9._-]{20,}"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Base URL for the deployed demo server.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--commit", default=None, help="Deployed commit SHA. Defaults to local git HEAD when available.")
    parser.add_argument("--qwen-model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout-seconds", type=int, default=10)
    parser.add_argument(
        "--proof-mode",
        choices=PROOF_MODES,
        default="local-smoke",
        help="Use ecs-public for submission proof; local-smoke is explicitly not deployment proof.",
    )
    parser.add_argument("--ecs-region", default="", help="Alibaba ECS region, for example us-west-1.")
    parser.add_argument("--ecs-instance-id", default="", help="Alibaba ECS instance ID recorded by the operator.")
    parser.add_argument("--ecs-public-ip", default="", help="Public IPv4/IPv6 address for the ECS instance.")
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
        _validate_no_secret_inputs(
            base_url=args.base_url,
            qwen_model=args.qwen_model,
            deployed_commit=args.commit or "",
            proof_mode=args.proof_mode,
            ecs_region=args.ecs_region,
            ecs_instance_id=args.ecs_instance_id,
            ecs_public_ip=args.ecs_public_ip,
            out=str(args.out),
        )
    except ValueError as exc:
        print(f"ecs smoke report failed: {exc}", file=sys.stderr)
        return 2

    try:
        report = collect_report(
            base_url=args.base_url,
            qwen_model=args.qwen_model,
            deployed_commit=args.commit or _git_head(),
            timeout_seconds=args.timeout_seconds,
            proof_mode=args.proof_mode,
            ecs_region=args.ecs_region,
            ecs_instance_id=args.ecs_instance_id,
            ecs_public_ip=args.ecs_public_ip,
        )
    except ValueError as exc:
        if args.allow_narrow_claim:
            deployed_commit = args.commit or _git_head()
            report = _input_validation_failure_report(
                base_url=args.base_url,
                qwen_model=args.qwen_model,
                deployed_commit=deployed_commit,
                proof_mode=args.proof_mode,
                ecs_region=args.ecs_region,
                ecs_instance_id=args.ecs_instance_id,
                ecs_public_ip=args.ecs_public_ip,
                error_message=str(exc),
            )
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(canonical_json(report) + "\n", encoding="utf-8")
            print(f"outcome {report['outcome']}")
            print(f"wrote {args.out}")
            return 0
        print(f"ecs smoke report failed: {exc}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(canonical_json(report) + "\n", encoding="utf-8")

    print(f"outcome {report['outcome']}")
    print(f"wrote {args.out}")
    if report["outcome"] != "GO" and not args.allow_narrow_claim:
        return 4
    return 0


def collect_report(
    *,
    base_url: str,
    qwen_model: str,
    deployed_commit: str,
    timeout_seconds: int,
    proof_mode: str = "local-smoke",
    ecs_region: str = "",
    ecs_instance_id: str = "",
    ecs_public_ip: str = "",
    fetcher: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if proof_mode not in PROOF_MODES:
        raise ValueError(f"proof mode must be one of {', '.join(PROOF_MODES)}")
    _validate_no_secret_inputs(
        base_url=base_url,
        qwen_model=qwen_model,
        deployed_commit=deployed_commit,
        proof_mode=proof_mode,
        ecs_region=ecs_region,
        ecs_instance_id=ecs_instance_id,
        ecs_public_ip=ecs_public_ip,
    )
    if _has_control_chars(ecs_region) or _has_control_chars(ecs_instance_id) or _has_control_chars(ecs_public_ip):
        raise ValueError("ECS metadata must not contain control characters")
    normalized_base_url = _normalize_base_url(base_url)
    fetch = fetcher or _fetch
    checks = [
        _check_json(
            base_url=normalized_base_url,
            path="/healthz",
            timeout_seconds=timeout_seconds,
            validator=_validate_healthz,
            fetcher=fetch,
        ),
        _check_json(
            base_url=normalized_base_url,
            path="/readyz",
            timeout_seconds=timeout_seconds,
            validator=_validate_readyz,
            fetcher=fetch,
        ),
        _check_json(
            base_url=normalized_base_url,
            path="/camera-fixture",
            timeout_seconds=timeout_seconds,
            validator=_validate_camera_fixture,
            fetcher=fetch,
        ),
        _check_text(
            base_url=normalized_base_url,
            path="/swarm-demo",
            timeout_seconds=timeout_seconds,
            validator=_validate_swarm_demo_html,
            fetcher=fetch,
        ),
        _check_json(
            base_url=normalized_base_url,
            path="/swarm-demo/summary.json",
            timeout_seconds=timeout_seconds,
            validator=_validate_swarm_summary,
            fetcher=fetch,
        ),
        _check_json(
            base_url=normalized_base_url,
            path=f"/qwen-ping?model={qwen_model}",
            timeout_seconds=timeout_seconds,
            validator=lambda payload: _validate_qwen_ping(payload, qwen_model=qwen_model),
            fetcher=fetch,
        ),
    ]
    deployment = _deployment_evidence(
        base_url=normalized_base_url,
        proof_mode=proof_mode,
        ecs_region=ecs_region,
        ecs_instance_id=ecs_instance_id,
        ecs_public_ip=ecs_public_ip,
    )
    pass_conditions = {check["name"]: check["ok"] for check in checks}
    pass_conditions["deployed_commit_recorded"] = _is_git_oid(deployed_commit)
    pass_conditions.update(deployment["pass_conditions"])
    outcome = "GO" if all(pass_conditions.values()) else "NARROW_CLAIM"
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "outcome": outcome,
        "base_url": normalized_base_url,
        "deployed_commit": deployed_commit,
        "proof_mode": proof_mode,
        "deployment": deployment["evidence"],
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
            "local-smoke mode is not an Alibaba ECS deployment proof",
        ],
    }


def _check_json(
    *,
    base_url: str,
    path: str,
    timeout_seconds: int,
    validator: Any,
    fetcher: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    response = fetcher(base_url=base_url, path=path, timeout_seconds=timeout_seconds)
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
    fetcher: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    response = fetcher(base_url=base_url, path=path, timeout_seconds=timeout_seconds)
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
        and payload.get("schema_version") == "decisiontrace.v2"
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
    schema_version = str(payload.get("schema_version", ""))
    ok = (
        payload.get("outcome") == "GO"
        and scenario_count >= 1
        and _is_hex_64(index_sha)
        and schema_version == SWARM_BUNDLE_SCHEMA_VERSION
    )
    return _validation(
        ok=ok,
        reason="swarm demo summary reports GO",
        evidence={
            "schema_version": schema_version,
            "outcome": payload.get("outcome"),
            "scenario_count": scenario_count,
            "index_sha256": index_sha,
        },
    )


def _validate_qwen_ping(payload: dict[str, Any], *, qwen_model: str) -> dict[str, Any]:
    content_prefix = str(payload.get("content_prefix", ""))
    ok = payload.get("status") == "ok" and payload.get("model") == qwen_model and content_prefix.startswith("OK")
    return _validation(
        ok=ok,
        reason="DashScope Qwen ping returned ok",
        evidence={
            "status": payload.get("status"),
            "model": payload.get("model"),
            "content_prefix": content_prefix[:8],
        },
    )


def _validation(*, ok: bool, reason: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"ok": ok, "reason": reason, "evidence": evidence}


def _check_name(path: str) -> str:
    return path.strip("/").replace("/", "_").replace("?", "_").replace("=", "_") or "root"


def _normalize_base_url(base_url: str) -> str:
    if _has_control_chars(base_url):
        raise ValueError("base URL must not contain control characters")
    normalized = base_url.rstrip("/")
    if not normalized.startswith(("http://", "https://")):
        raise ValueError("base URL must start with http:// or https://")
    parsed = urlparse(normalized)
    if parsed.hostname is None:
        raise ValueError("base URL must include a host")
    return normalized


def _deployment_evidence(
    *,
    base_url: str,
    proof_mode: str,
    ecs_region: str,
    ecs_instance_id: str,
    ecs_public_ip: str,
) -> dict[str, Any]:
    region = ecs_region.strip()
    instance_id = ecs_instance_id.strip()
    public_ip_text = ecs_public_ip.strip()
    public_ip = _parse_ip(public_ip_text)
    base_url_public = _base_url_uses_public_host(base_url)
    base_url_matches_ip = _base_url_matches_ip(base_url=base_url, public_ip=public_ip)
    pass_conditions = {
        "proof_mode_is_ecs_public": proof_mode == "ecs-public",
        "ecs_region_recorded": _metadata_value_ok(region),
        "ecs_instance_id_recorded": _metadata_value_ok(instance_id),
        "ecs_public_ip_is_global": public_ip is not None and public_ip.is_global,
        "base_url_is_public_endpoint": base_url_public,
        "base_url_matches_public_ip_when_ip_literal": base_url_matches_ip,
    }
    evidence = {
        "provider_asserted": "Alibaba Cloud ECS" if proof_mode == "ecs-public" else "local smoke",
        "deployment_context_verified": all(pass_conditions.values()),
        "ecs_region": region,
        "ecs_instance_id": instance_id,
        "ecs_public_ip": public_ip_text,
        "base_url_is_public_endpoint": base_url_public,
        "base_url_matches_public_ip_when_ip_literal": base_url_matches_ip,
    }
    return {"evidence": evidence, "pass_conditions": pass_conditions}


def _input_validation_failure_report(
    *,
    base_url: str,
    qwen_model: str,
    deployed_commit: str,
    proof_mode: str,
    ecs_region: str,
    ecs_instance_id: str,
    ecs_public_ip: str,
    error_message: str,
) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "outcome": "NARROW_CLAIM",
        "base_url": _sanitize_text(base_url),
        "deployed_commit": _sanitize_text(deployed_commit),
        "proof_mode": proof_mode,
        "deployment": {
            "provider_asserted": "Alibaba Cloud ECS" if proof_mode == "ecs-public" else "local smoke",
            "deployment_context_verified": False,
            "ecs_region": _sanitize_text(ecs_region.strip()),
            "ecs_instance_id": _sanitize_text(ecs_instance_id.strip()),
            "ecs_public_ip": _sanitize_text(ecs_public_ip.strip()),
        },
        "qwen_model": _sanitize_text(qwen_model),
        "checks": [],
        "pass_conditions": {
            "input_validation_passed": False,
            "deployed_commit_recorded": _is_git_oid(deployed_commit),
        },
        "error": {
            "type": "ValueError",
            "message": _sanitize_text(error_message),
        },
        "non_claims": [
            "not an Alibaba ECS deployment proof",
            "not a production hosting claim",
            "not a public availability claim",
            "not a latency or reliability claim",
            "not physical robot behavior",
            "not SO-101 operation",
            "not Qwen onboard execution",
            "input validation failure report contains no endpoint checks",
        ],
    }


def _sanitize_text(value: str) -> str:
    return "".join(character if ord(character) >= 32 else " " for character in value)


def _validate_no_secret_inputs(**values: str) -> None:
    for name, value in values.items():
        if _contains_secret_material(value):
            raise ValueError(f"{name} must not contain secret-like material")


def _contains_secret_material(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


def _metadata_value_ok(value: str) -> bool:
    return bool(value.strip()) and not _has_control_chars(value)


def _parse_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def _base_url_uses_public_host(base_url: str) -> bool:
    host = urlparse(base_url).hostname
    if host is None:
        return False
    lowered = host.lower()
    if lowered in {"localhost"} or lowered.endswith(".local"):
        return False
    ip = _parse_ip(host)
    if ip is None:
        return False
    return ip.is_global


def _base_url_matches_ip(
    *,
    base_url: str,
    public_ip: ipaddress.IPv4Address | ipaddress.IPv6Address | None,
) -> bool:
    host = urlparse(base_url).hostname
    if host is None or public_ip is None:
        return False
    host_ip = _parse_ip(host)
    if host_ip is None:
        return False
    return host_ip == public_ip


def _has_control_chars(value: str) -> bool:
    return any(ord(character) < 32 for character in value)


def _is_hex_64(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _is_git_oid(value: str) -> bool:
    if len(value) not in {40, 64}:
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
    return head if _is_git_oid(head) else "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
