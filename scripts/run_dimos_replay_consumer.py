#!/usr/bin/env python3
"""Consume a verified DimOS bridge pack into deterministic stream summaries."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any

from accountable_swarm.trace.models import canonical_json, sha256_canonical


REPORT_SCHEMA_VERSION = "dimos-replay-consumer-report.v1"
BRIDGE_SCHEMA_VERSION = "dimos-bridge-pack-report.v1"
EVENT_SCHEMA_VERSION = "dimos-swarm-replay-event.v1"
DEFAULT_BRIDGE_PACK = Path("runs/dimos/bridge-pack")
DEFAULT_REPORT_OUT = Path("runs/dimos/replay-consumer-report.json")
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Authorization:\s*Bearer\s+\S+", re.IGNORECASE),
    re.compile(r"ALIBABA_API_KEY\s*=\s*\S+", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9._-]{6,}"),
)
DIMOS_REQUIRED_FILES = (
    "AGENTS.md",
    "dimos/core/module.py",
    "dimos/core/stream.py",
    "dimos/core/coordination/blueprints.py",
    "dimos/visualization/rerun/bridge.py",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge-pack", type=Path, default=DEFAULT_BRIDGE_PACK)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT_OUT)
    parser.add_argument(
        "--dimos-checkout",
        type=Path,
        default=None,
        help="Optional local DimOS checkout to inspect without executing it.",
    )
    parser.add_argument(
        "--require-dimos-runtime",
        action="store_true",
        help="Fail unless dimos import, dimos CLI, and rerun import are available.",
    )
    args = parser.parse_args()

    try:
        repo_root = _find_repo_root(Path.cwd())
        bridge_pack = _repo_path(repo_root, args.bridge_pack)
        report_out = _repo_path(repo_root, args.report_out)
        manifest_path = bridge_pack / "manifest.json"
        timeline_path = bridge_pack / "timeline.ndjson"
        manifest = _read_manifest(manifest_path)
        events = _read_timeline(timeline_path)
        streams = _stream_summaries(events)
        _validate_manifest_against_timeline(
            repo_root=repo_root,
            bridge_pack=bridge_pack,
            manifest=manifest,
            events=events,
        )
        runtime_probe = _probe_dimos(args.dimos_checkout)
        report = _build_report(
            repo_root=repo_root,
            bridge_pack=bridge_pack,
            report_out=report_out,
            manifest=manifest,
            events=events,
            streams=streams,
            runtime_probe=runtime_probe,
            require_dimos_runtime=args.require_dimos_runtime,
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"dimos replay consumer failed: {exc}", file=sys.stderr)
        return 4

    report_text = canonical_json(report)
    if _contains_secret_material(report_text):
        print("dimos replay consumer report would contain secret material; aborting", file=sys.stderr)
        return 2

    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(report_text + "\n", encoding="utf-8")

    print(f"outcome {report['outcome']}")
    print(f"consumer_outcome {report['consumer_outcome']}")
    print(f"dimos_runtime_outcome {report['dimos_runtime']['runtime_outcome']}")
    print(f"stream_count {report['stream_count']}")
    print(f"event_count {report['event_count']}")
    print(f"report {_display_path(repo_root, report_out)}")
    if args.require_dimos_runtime and report["dimos_runtime"]["runtime_outcome"] != "GO":
        return 4
    return 0 if report["consumer_outcome"] == "GO" else 4


def _read_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError("bridge pack manifest.json is required")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != BRIDGE_SCHEMA_VERSION:
        raise ValueError("bridge pack manifest uses an unsupported schema")
    if manifest.get("bridge_outcome") != "GO":
        raise ValueError("bridge pack must have bridge_outcome GO")
    return manifest


def _read_timeline(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError("bridge pack timeline.ndjson is required")
    events = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            raise ValueError(f"timeline line {line_number} is empty")
        event = json.loads(line)
        _validate_event(event)
        if canonical_json(event) != line:
            raise ValueError(f"timeline line {line_number} is not canonical JSON")
        events.append(event)
    if not events:
        raise ValueError("timeline must contain at least one event")
    return events


def _validate_event(event: dict[str, Any]) -> None:
    _reject_raw_float_or_bool(event)
    if event.get("schema_version") != EVENT_SCHEMA_VERSION:
        raise ValueError("timeline event uses an unsupported schema")
    if event.get("source") != "accountable_swarm_decisiontrace":
        raise ValueError("timeline event source is unsupported")
    scenario = _require_non_empty_string(event, "scenario")
    agent_id = _require_non_empty_string(event, "agent_id")
    tick = _require_int(event, "tick")
    if tick < 0:
        raise ValueError("tick must be non-negative")
    position = _require_dict(event, "position_cell")
    grid = _require_dict(event, "grid")
    x = _require_int(position, "x")
    y = _require_int(position, "y")
    width = _require_int(grid, "width")
    height = _require_int(grid, "height")
    if width <= 0 or height <= 0:
        raise ValueError("grid dimensions must be positive")
    if not 0 <= x < width or not 0 <= y < height:
        raise ValueError("position cell outside grid")
    decision = _require_non_empty_string(event, "decision")
    if decision not in {"MOVE", "VETO", "HOLD", "REROUTE"}:
        raise ValueError("unsupported decision")
    if not _is_hex_64(event.get("event_sha256")):
        raise ValueError("event_sha256 must be a 64-character hex string")
    if not _is_hex_64(event.get("trace_summary_sha")):
        raise ValueError("trace_summary_sha must be a 64-character hex string")
    expected_hint = f"/accountable_swarm/{scenario}/{agent_id}/grid_pose"
    if event.get("dimos_stream_hint") != expected_hint:
        raise ValueError("dimos_stream_hint does not match scenario and agent id")


def _stream_summaries(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        grouped.setdefault(event["dimos_stream_hint"], []).append(event)

    summaries = []
    for stream_hint, stream_events in sorted(grouped.items()):
        ticks = [event["tick"] for event in stream_events]
        if ticks != sorted(ticks):
            raise ValueError(f"stream ticks are not monotonic for {stream_hint}")
        first = stream_events[0]
        last = stream_events[-1]
        summaries.append(
            {
                "stream_hint": stream_hint,
                "scenario": first["scenario"],
                "agent_id": first["agent_id"],
                "event_count": len(stream_events),
                "first_tick": first["tick"],
                "last_tick": last["tick"],
                "first_position_cell": first["position_cell"],
                "last_position_cell": last["position_cell"],
                "decisions": sorted({event["decision"] for event in stream_events}),
            }
        )
    return summaries


def _validate_manifest_against_timeline(
    *,
    repo_root: Path,
    bridge_pack: Path,
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
) -> None:
    scenario_names = sorted({event["scenario"] for event in events})
    if _require_int(manifest, "event_count") != len(events):
        raise ValueError("manifest event_count does not match timeline")
    if _require_int(manifest, "scenario_count") != len(scenario_names):
        raise ValueError("manifest scenario_count does not match timeline")
    manifest_scenarios = manifest["scenarios"]
    if not isinstance(manifest_scenarios, list) or not all(
        isinstance(item, str) and item.strip() for item in manifest_scenarios
    ):
        raise ValueError("manifest scenarios must be a non-empty string list")
    if manifest_scenarios != scenario_names:
        raise ValueError("manifest scenarios do not match timeline")
    artifacts = _require_dict(manifest, "artifacts")
    expected_manifest = _display_path(repo_root, bridge_pack / "manifest.json")
    expected_timeline = _display_path(repo_root, bridge_pack / "timeline.ndjson")
    if artifacts.get("manifest") != expected_manifest:
        raise ValueError("manifest artifact path does not match bridge-pack manifest path")
    if artifacts.get("timeline_ndjson") != expected_timeline:
        raise ValueError("manifest artifact path does not match bridge-pack timeline path")


def _build_report(
    *,
    repo_root: Path,
    bridge_pack: Path,
    report_out: Path,
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    streams: list[dict[str, Any]],
    runtime_probe: dict[str, Any],
    require_dimos_runtime: bool,
) -> dict[str, Any]:
    source_manifest_sha = sha256_canonical(manifest)
    scenario_names = sorted({event["scenario"] for event in events})
    pass_conditions = {
        "bridge_pack_inside_repo": _is_relative_to(bridge_pack, repo_root),
        "report_out_inside_repo": _is_relative_to(report_out, repo_root),
        "source_manifest_schema_valid": manifest.get("schema_version") == BRIDGE_SCHEMA_VERSION,
        "source_bridge_outcome_go": manifest.get("bridge_outcome") == "GO",
        "source_manifest_hash_stable": _is_hex_64(source_manifest_sha),
        "source_event_count_matches_timeline": manifest.get("event_count") == len(events),
        "source_scenario_count_matches_timeline": manifest.get("scenario_count") == len(scenario_names),
        "source_scenarios_match_timeline": manifest.get("scenarios") == scenario_names,
        "timeline_has_events": bool(events),
        "stream_count_matches_events": len(streams) <= len(events),
        "events_are_integer_only": _events_are_integer_only(events),
        "events_reference_hashes": all(
            _is_hex_64(event["event_sha256"]) and _is_hex_64(event["trace_summary_sha"])
            for event in events
        ),
        "stream_ticks_monotonic": True,
        "stream_hints_valid": all(
            summary["stream_hint"]
            == f"/accountable_swarm/{summary['scenario']}/{summary['agent_id']}/grid_pose"
            for summary in streams
        ),
        "report_paths_are_relative": True,
    }
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "outcome": "PENDING",
        "consumer_outcome": "GO" if all(pass_conditions.values()) else "NARROW_CLAIM",
        "bridge_pack": _display_path(repo_root, bridge_pack),
        "source_manifest_sha256": source_manifest_sha,
        "artifacts": {
            "source_manifest": _display_path(repo_root, bridge_pack / "manifest.json"),
            "source_timeline": _display_path(repo_root, bridge_pack / "timeline.ndjson"),
            "report": _display_path(repo_root, report_out),
        },
        "scenario_count": len(scenario_names),
        "scenarios": scenario_names,
        "event_count": len(events),
        "stream_count": len(streams),
        "first_tick": min(event["tick"] for event in events),
        "last_tick": max(event["tick"] for event in events),
        "streams": streams,
        "dimos_runtime": runtime_probe,
        "require_dimos_runtime": require_dimos_runtime,
        "pass_conditions": pass_conditions,
        "non_claims": [
            "no DimOS runtime execution",
            "no DimOS swarm control",
            "no Rerun recording proof",
            "no physical robot behavior",
            "no SO-101 operation",
            "no 3D physics simulation",
            "no Qwen real-time control",
            "no latency or reliability claim",
        ],
    }
    report["pass_conditions"]["report_contains_no_key_material"] = not _contains_secret_material(
        canonical_json(report)
    )
    consumer_go = all(report["pass_conditions"].values())
    report["consumer_outcome"] = "GO" if consumer_go else "NARROW_CLAIM"
    runtime_go = runtime_probe["runtime_outcome"] == "GO"
    report["outcome"] = "GO" if consumer_go and runtime_go else "NARROW_CLAIM"
    return report


def _probe_dimos(dimos_checkout: Path | None) -> dict[str, Any]:
    source_probe = {
        "checkout_provided": dimos_checkout is not None,
        "checkout_exists": False,
        "source_name": None,
        "required_files_present": {},
        "source_outcome": "NARROW_CLAIM",
    }
    if dimos_checkout is not None:
        checkout = dimos_checkout.expanduser()
        source_probe["checkout_exists"] = checkout.is_dir()
        source_probe["source_name"] = checkout.name if checkout.name else None
        required = {relative: (checkout / relative).is_file() for relative in DIMOS_REQUIRED_FILES}
        source_probe["required_files_present"] = required
        source_probe["source_outcome"] = (
            "GO" if source_probe["checkout_exists"] and all(required.values()) else "NARROW_CLAIM"
        )

    python_import_available = importlib.util.find_spec("dimos") is not None
    cli_available = shutil.which("dimos") is not None
    rerun_import_available = importlib.util.find_spec("rerun") is not None
    runtime_outcome = (
        "GO" if python_import_available and cli_available and rerun_import_available else "NARROW_CLAIM"
    )
    return {
        "source": source_probe,
        "python_import_available": python_import_available,
        "cli_available": cli_available,
        "rerun_import_available": rerun_import_available,
        "runtime_outcome": runtime_outcome,
        "claim_boundary": (
            "This probe does not start DimOS, run a blueprint, open Rerun, "
            "or prove DimOS consumed the replay timeline."
        ),
    }


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "accountable_swarm" / "trace" / "models.py").is_file()
            and (candidate / "scripts" / "run_dimos_replay_consumer.py").is_file()
        ):
            return candidate
    raise ValueError("could not locate accountable-swarm repository root")


def _repo_path(repo_root: Path, path: Path) -> Path:
    if path.is_absolute():
        raise ValueError("paths written or consumed by this script must be repo-relative")
    candidate = (repo_root / path).resolve()
    root = repo_root.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("path must stay inside the repository checkout") from exc
    return candidate


def _display_path(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _events_are_integer_only(events: list[dict[str, Any]]) -> bool:
    try:
        _reject_raw_float_or_bool(events)
        canonical_json(events)
    except (TypeError, ValueError):
        return False
    return all(
        _is_plain_int(event["tick"])
        and _is_plain_int(event["position_cell"]["x"])
        and _is_plain_int(event["position_cell"]["y"])
        and _is_plain_int(event["grid"]["width"])
        and _is_plain_int(event["grid"]["height"])
        for event in events
    )


def _reject_raw_float_or_bool(value: Any, path: str = "$") -> None:
    if isinstance(value, bool):
        raise TypeError(f"boolean scalar not allowed in DimOS replay timeline at {path}")
    if isinstance(value, float):
        raise TypeError(f"raw float not allowed in DimOS replay timeline at {path}")
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_raw_float_or_bool(item, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_raw_float_or_bool(item, f"{path}[{index}]")


def _require_dict(value: dict[str, Any], key: str) -> dict[str, Any]:
    item = value[key]
    if not isinstance(item, dict):
        raise ValueError(f"{key} must be an object")
    return item


def _require_non_empty_string(value: dict[str, Any], key: str) -> str:
    item = value[key]
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return item


def _require_int(value: dict[str, Any], key: str) -> int:
    item = value[key]
    if not _is_plain_int(item):
        raise ValueError(f"{key} must be an integer")
    return item


def _is_plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_hex_64(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _contains_secret_material(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


if __name__ == "__main__":
    raise SystemExit(main())
