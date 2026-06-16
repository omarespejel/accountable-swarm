#!/usr/bin/env python3
"""Collect a claim-safe DimOS runtime smoke report from a verified bridge pack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from accountable_swarm.trace.models import canonical_json
from scripts.run_dimos_replay_consumer import _read_timeline, _validate_manifest_against_timeline


REPORT_SCHEMA_VERSION = "dimos-runtime-smoke-report.v1"
BRIDGE_SCHEMA_VERSION = "dimos-bridge-pack-report.v1"
DEFAULT_BRIDGE_PACK = Path("runs/dimos/bridge-pack")
DEFAULT_REPORT_OUT = Path("runs/dimos/runtime-smoke-report.json")
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Authorization:[ \t]*Bearer[ \t]+(?!<redacted>)\S+", re.IGNORECASE),
    re.compile(r"ALIBABA_API_KEY[ \t]*=[ \t]*\S+", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9._-]{6,}"),
)
DIMOS_REQUIRED_FILES = (
    "AGENTS.md",
    "dimos/core/module.py",
    "dimos/core/stream.py",
    "dimos/core/coordination/blueprints.py",
    "dimos/visualization/rerun/bridge.py",
)
PROBE_SCRIPT = """
import json
import sys
from pathlib import Path

checkout = Path(sys.argv[1])
bridge_pack = Path(sys.argv[2])
sys.path.insert(0, str(checkout))

result = {
    "dimos_import_available": False,
    "rerun_import_available": False,
    "rerun_init_import_available": False,
    "timeline_event_count": 0,
    "timeline_scenarios": [],
}

try:
    import dimos  # noqa: F401
except Exception as exc:
    result["dimos_import_error"] = str(exc)
else:
    result["dimos_import_available"] = True

try:
    import rerun  # noqa: F401
except Exception as exc:
    result["rerun_import_error"] = str(exc)
else:
    result["rerun_import_available"] = True

try:
    from dimos.visualization.rerun.init import rerun_init  # noqa: F401
except Exception as exc:
    result["rerun_init_import_error"] = str(exc)
else:
    result["rerun_init_import_available"] = True

timeline_path = bridge_pack / "timeline.ndjson"
scenarios = set()
event_count = 0
for line in timeline_path.read_text(encoding="utf-8").splitlines():
    if not line:
        continue
    event = json.loads(line)
    event_count += 1
    scenarios.add(event["scenario"])
result["timeline_event_count"] = event_count
result["timeline_scenarios"] = sorted(scenarios)
print(json.dumps(result, sort_keys=True))
""".strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge-pack", type=Path, default=DEFAULT_BRIDGE_PACK)
    parser.add_argument("--dimos-checkout", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT_OUT)
    args = parser.parse_args()

    try:
        repo_root = _find_repo_root(Path.cwd())
        bridge_pack = _repo_path(repo_root, args.bridge_pack)
        report_out = _repo_path(repo_root, args.report_out)
        dimos_checkout = args.dimos_checkout.expanduser().resolve()
        manifest = _read_bridge_manifest(repo_root=repo_root, bridge_pack=bridge_pack)
        events = _read_timeline(bridge_pack / "timeline.ndjson")
        _validate_manifest_against_timeline(
            repo_root=repo_root,
            bridge_pack=bridge_pack,
            manifest=manifest,
            events=events,
        )
        runtime_probe = _probe_runtime(dimos_checkout=dimos_checkout, bridge_pack=bridge_pack)
        report = _build_report(
            repo_root=repo_root,
            bridge_pack=bridge_pack,
            report_out=report_out,
            manifest=manifest,
            runtime_probe=runtime_probe,
            dimos_checkout=dimos_checkout,
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"dimos runtime smoke failed: {exc}", file=sys.stderr)
        return 4

    report_text = canonical_json(report)
    if _contains_secret_material(report_text):
        print("dimos runtime smoke report would contain secret material; aborting", file=sys.stderr)
        return 2

    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(report_text + "\n", encoding="utf-8")

    print(f"outcome {report['outcome']}")
    print(f"report {_display_path(repo_root, report_out)}")
    return 0 if report["outcome"] == "GO" else 4


def _find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "AGENTS.md").exists() and (candidate / "pyproject.toml").exists():
            return candidate
    raise ValueError("could not find repository root from current working directory")


def _repo_path(repo_root: Path, candidate: Path) -> Path:
    path = (repo_root / candidate).resolve()
    try:
        path.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes repository root: {candidate}") from exc
    return path


def _display_path(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _read_bridge_manifest(*, repo_root: Path, bridge_pack: Path) -> dict[str, Any]:
    manifest_path = bridge_pack / "manifest.json"
    timeline_path = bridge_pack / "timeline.ndjson"
    if not manifest_path.is_file():
        raise ValueError("bridge pack manifest.json is required")
    if not timeline_path.is_file():
        raise ValueError("bridge pack timeline.ndjson is required")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != BRIDGE_SCHEMA_VERSION:
        raise ValueError("bridge pack manifest uses an unsupported schema")
    if manifest.get("bridge_outcome") != "GO":
        raise ValueError("bridge pack must have bridge_outcome GO")
    artifacts = _require_dict(manifest, "artifacts")
    expected_manifest = _display_path(repo_root, manifest_path)
    expected_timeline = _display_path(repo_root, timeline_path)
    if artifacts.get("manifest") != expected_manifest:
        raise ValueError("bridge pack manifest artifact path mismatch")
    if artifacts.get("timeline_ndjson") != expected_timeline:
        raise ValueError("bridge pack timeline artifact path mismatch")
    return manifest


def _probe_runtime(*, dimos_checkout: Path, bridge_pack: Path) -> dict[str, Any]:
    required_files = {relative: (dimos_checkout / relative).is_file() for relative in DIMOS_REQUIRED_FILES}
    checkout_exists = dimos_checkout.is_dir()
    venv_python = dimos_checkout / ".venv" / "bin" / "python"
    venv_dimos = dimos_checkout / ".venv" / "bin" / "dimos"
    python_probe: dict[str, Any] | None = None
    python_probe_error: str | None = None
    python_probe_ok = False
    cli_help_ok = False
    cli_help_error: str | None = None

    if checkout_exists and venv_python.is_file():
        probe_result = subprocess.run(
            [
                str(venv_python),
                "-c",
                PROBE_SCRIPT,
                str(dimos_checkout),
                str(bridge_pack),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if probe_result.returncode == 0:
            try:
                python_probe = json.loads(probe_result.stdout)
            except json.JSONDecodeError as exc:
                python_probe_error = f"python probe output was not valid JSON: {exc}"
            else:
                python_probe_ok = True
        else:
            python_probe_error = probe_result.stderr.strip() or probe_result.stdout.strip() or "python probe failed"

    if checkout_exists and venv_dimos.is_file():
        cli_result = subprocess.run(
            [str(venv_dimos), "--help"],
            text=True,
            capture_output=True,
            check=False,
        )
        cli_help_ok = cli_result.returncode == 0
        if not cli_help_ok:
            cli_help_error = cli_result.stderr.strip() or cli_result.stdout.strip() or "dimos --help failed"

    return {
        "checkout_provided": True,
        "checkout_name": dimos_checkout.name,
        "checkout_exists": checkout_exists,
        "required_files_present": required_files,
        "venv_python_present": venv_python.is_file(),
        "venv_dimos_cli_present": venv_dimos.is_file(),
        "python_probe_ok": python_probe_ok,
        "python_probe": python_probe,
        "python_probe_error": python_probe_error,
        "dimos_cli_help_ok": cli_help_ok,
        "dimos_cli_help_error": cli_help_error,
    }


def _build_report(
    *,
    repo_root: Path,
    bridge_pack: Path,
    report_out: Path,
    manifest: dict[str, Any],
    runtime_probe: dict[str, Any],
    dimos_checkout: Path,
) -> dict[str, Any]:
    scenarios = manifest["scenarios"]
    event_count = _require_int(manifest, "event_count")
    python_probe = runtime_probe["python_probe"]
    python_probe_matches_bridge_counts = False
    if isinstance(python_probe, dict):
        python_probe_matches_bridge_counts = (
            python_probe.get("timeline_event_count") == event_count
            and python_probe.get("timeline_scenarios") == scenarios
        )

    pass_conditions = {
        "bridge_pack_inside_repo": True,
        "bridge_pack_timeline_valid": True,
        "report_out_inside_repo": True,
        "checkout_exists": bool(runtime_probe["checkout_exists"]),
        "required_source_files_present": all(runtime_probe["required_files_present"].values()),
        "venv_python_present": bool(runtime_probe["venv_python_present"]),
        "venv_dimos_cli_present": bool(runtime_probe["venv_dimos_cli_present"]),
        "python_probe_ok": bool(runtime_probe["python_probe_ok"]),
        "dimos_import_available": bool(python_probe and python_probe.get("dimos_import_available")),
        "rerun_import_available": bool(python_probe and python_probe.get("rerun_import_available")),
        "rerun_init_import_available": bool(python_probe and python_probe.get("rerun_init_import_available")),
        "python_probe_matches_bridge_counts": python_probe_matches_bridge_counts,
        "dimos_cli_help_ok": bool(runtime_probe["dimos_cli_help_ok"]),
        "report_paths_are_relative": True,
    }
    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "outcome": "PENDING",
        "bridge_pack": _display_path(repo_root, bridge_pack),
        "bridge_manifest": {
            "scenario_count": _require_int(manifest, "scenario_count"),
            "scenarios": scenarios,
            "event_count": event_count,
            "agent_count": _require_int(manifest, "agent_count"),
        },
        "dimos_runtime_probe": {
            "checkout_name": dimos_checkout.name,
            "checkout_exists": runtime_probe["checkout_exists"],
            "required_files_present": runtime_probe["required_files_present"],
            "venv_python_present": runtime_probe["venv_python_present"],
            "venv_dimos_cli_present": runtime_probe["venv_dimos_cli_present"],
            "python_probe_ok": runtime_probe["python_probe_ok"],
            "python_probe": python_probe,
            "python_probe_error": runtime_probe["python_probe_error"],
            "dimos_cli_help_ok": runtime_probe["dimos_cli_help_ok"],
            "dimos_cli_help_error": runtime_probe["dimos_cli_help_error"],
            "claim_boundary": (
                "This smoke report proves only that a checked DimOS environment could import "
                "DimOS/Rerun surfaces while reading the verified replay artifact. "
                "It does not prove DimOS controlled, simulated, or visualized the swarm."
            ),
        },
        "artifacts": {
            "bridge_manifest": _display_path(repo_root, bridge_pack / "manifest.json"),
            "bridge_timeline": _display_path(repo_root, bridge_pack / "timeline.ndjson"),
            "report": _display_path(repo_root, report_out),
        },
        "pass_conditions": pass_conditions,
        "non_claims": [
            "no DimOS swarm control claim",
            "no DimOS 3D simulation claim",
            "no Rerun recording proof",
            "no physical robot behavior",
            "no SO-101 operation",
            "no latency or reliability claim",
        ],
    }
    pass_conditions["report_contains_no_key_material"] = not _contains_secret_material(canonical_json(report))
    report["outcome"] = "GO" if all(pass_conditions.values()) else "NARROW_CLAIM"
    return report


def _require_dict(payload: dict[str, Any], field: str) -> dict[str, Any]:
    value = payload.get(field)
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _require_int(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def _contains_secret_material(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


if __name__ == "__main__":
    raise SystemExit(main())
