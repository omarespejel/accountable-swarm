#!/usr/bin/env python3
"""Prepare a claim-safe DimOS bridge pack from verified swarm traces."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from accountable_swarm.trace.models import canonical_json, trace_from_dict, verify_trace


BRIDGE_SCHEMA_VERSION = "dimos-bridge-pack-report.v1"
EVENT_SCHEMA_VERSION = "dimos-swarm-replay-event.v1"
DEFAULT_SOURCE_BUNDLE = Path("runs/demo/swarm")
DEFAULT_OUT_DIR = Path("runs/dimos/bridge-pack")
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
    parser.add_argument("--source-bundle", type=Path, default=DEFAULT_SOURCE_BUNDLE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--dimos-checkout",
        type=Path,
        default=None,
        help="Optional local DimOS checkout to inspect without executing it.",
    )
    args = parser.parse_args()

    try:
        repo_root = _find_repo_root(Path.cwd())
        source_bundle = _repo_path(repo_root, args.source_bundle)
        out_dir = _repo_path(repo_root, args.out_dir)
        events, source_summary = _events_from_bundle(source_bundle)
        manifest = _build_manifest(
            repo_root=repo_root,
            source_bundle=source_bundle,
            out_dir=out_dir,
            events=events,
            source_summary=source_summary,
            dimos_checkout=args.dimos_checkout,
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"dimos bridge pack failed: {exc}", file=sys.stderr)
        return 4

    event_lines = [canonical_json(event) for event in events]
    manifest_text = canonical_json(manifest)
    generated_text = "\n".join([*event_lines, manifest_text])
    if _contains_secret_material(generated_text):
        print("dimos bridge pack would contain secret material; aborting", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    timeline_path = out_dir / "timeline.ndjson"
    manifest_path = out_dir / "manifest.json"
    timeline_path.write_text("\n".join(event_lines) + "\n", encoding="utf-8")
    manifest_path.write_text(manifest_text + "\n", encoding="utf-8")

    print(f"outcome {manifest['outcome']}")
    print(f"bridge_outcome {manifest['bridge_outcome']}")
    print(f"dimos_runtime_outcome {manifest['dimos_probe']['runtime_outcome']}")
    print(f"manifest {_display_path(repo_root, manifest_path)}")
    print(f"timeline {_display_path(repo_root, timeline_path)}")
    return 0 if manifest["outcome"] == "GO" else 4


def _build_manifest(
    *,
    repo_root: Path,
    source_bundle: Path,
    out_dir: Path,
    events: list[dict[str, Any]],
    source_summary: dict[str, Any],
    dimos_checkout: Path | None,
) -> dict[str, Any]:
    dimos_probe = _probe_dimos(dimos_checkout)
    scenario_names = sorted({event["scenario"] for event in events})
    pass_conditions = {
        "source_bundle_outcome_go": source_summary.get("outcome") == "GO",
        "source_bundle_inside_repo": _is_relative_to(source_bundle, repo_root),
        "out_dir_inside_repo": _is_relative_to(out_dir, repo_root),
        "timeline_has_events": bool(events),
        "timeline_events_integer_only": _events_are_integer_only(events),
        "timeline_events_reference_verified_hashes": all(
            _is_hex_64(event["event_sha256"]) and _is_hex_64(event["trace_summary_sha"])
            for event in events
        ),
        "manifest_paths_are_relative": True,
    }
    manifest = {
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "outcome": "PENDING",
        "bridge_outcome": "GO" if all(pass_conditions.values()) else "NARROW_CLAIM",
        "source_bundle": _display_path(repo_root, source_bundle),
        "artifacts": {
            "manifest": _display_path(repo_root, out_dir / "manifest.json"),
            "timeline_ndjson": _display_path(repo_root, out_dir / "timeline.ndjson"),
        },
        "scenario_count": len(scenario_names),
        "scenarios": scenario_names,
        "event_count": len(events),
        "agent_count": len({event["agent_id"] for event in events}),
        "dimos_probe": dimos_probe,
        "pass_conditions": pass_conditions,
        "non_claims": [
            "no DimOS execution",
            "no DimOS swarm integration",
            "no Rerun recording proof",
            "no physical robot behavior",
            "no SO-101 operation",
            "no 3D physics simulation",
            "no Qwen real-time control",
            "no latency or reliability claim",
        ],
    }
    manifest["pass_conditions"]["manifest_contains_no_key_material"] = not _contains_secret_material(
        canonical_json(manifest)
    )
    manifest["outcome"] = "GO" if all(manifest["pass_conditions"].values()) else "NARROW_CLAIM"
    return manifest


def _events_from_bundle(source_bundle: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    summary_path = source_bundle / "summary.json"
    if not summary_path.is_file():
        raise ValueError("source bundle summary.json is required")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("schema_version") != "swarm-demo-bundle-report.v1":
        raise ValueError("source bundle must use swarm-demo-bundle-report.v1")
    scenarios = summary.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("source bundle must contain scenarios")

    events: list[dict[str, Any]] = []
    for case in scenarios:
        scenario = _require_non_empty_string(case, "scenario")
        grid = case["grid"]
        grid_width = _require_int(grid, "width")
        grid_height = _require_int(grid, "height")
        trace_paths = case["files"]["traces"]
        if not isinstance(trace_paths, dict) or not trace_paths:
            raise ValueError(f"{scenario} must list trace paths")
        for agent_id, relative_trace_path in sorted(trace_paths.items()):
            if not isinstance(agent_id, str) or not agent_id.strip():
                raise ValueError(f"{scenario} has invalid agent id")
            if not isinstance(relative_trace_path, str) or Path(relative_trace_path).is_absolute():
                raise ValueError(f"{scenario} trace path must be relative")
            trace_path = (source_bundle / relative_trace_path).resolve()
            try:
                trace_path.relative_to(source_bundle.resolve())
            except ValueError as exc:
                raise ValueError(f"{scenario} trace path escapes source bundle") from exc
            if trace_path.suffix != ".json":
                raise ValueError(f"{scenario} trace path must point to a JSON file")
            trace = trace_from_dict(json.loads(trace_path.read_text(encoding="utf-8")))
            trace_summary_sha = verify_trace(trace)
            for event in trace.events:
                if not _is_plain_int(event.tick):
                    raise ValueError("trace event tick must be an integer")
                command = event.command
                if not isinstance(command, dict):
                    raise ValueError("trace command must be an object")
                if command.get("type") != "grid_step":
                    raise ValueError("bridge only supports grid_step trace commands")
                accepted_x = _require_int(command, "accepted_x")
                accepted_y = _require_int(command, "accepted_y")
                command_grid_width = _require_int(command, "grid_width")
                command_grid_height = _require_int(command, "grid_height")
                if command_grid_width != grid_width or command_grid_height != grid_height:
                    raise ValueError("trace grid dimensions do not match bundle summary")
                if not 0 <= accepted_x < grid_width or not 0 <= accepted_y < grid_height:
                    raise ValueError("accepted grid cell outside scenario bounds")
                events.append(
                    {
                        "schema_version": EVENT_SCHEMA_VERSION,
                        "source": "accountable_swarm_decisiontrace",
                        "scenario": scenario,
                        "tick": event.tick,
                        "agent_id": agent_id,
                        "position_cell": {"x": accepted_x, "y": accepted_y},
                        "grid": {"width": grid_width, "height": grid_height},
                        "decision": event.decision,
                        "event_sha256": event.sha256,
                        "trace_summary_sha": trace_summary_sha,
                        "dimos_stream_hint": f"/accountable_swarm/{scenario}/{agent_id}/grid_pose",
                    }
                )
    if not events:
        raise ValueError("bridge timeline would be empty")
    return events, summary


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
        required = {
            relative: (checkout / relative).is_file()
            for relative in DIMOS_REQUIRED_FILES
        }
        source_probe["required_files_present"] = required
        source_probe["source_outcome"] = (
            "GO" if source_probe["checkout_exists"] and all(required.values()) else "NARROW_CLAIM"
        )

    python_import_available = importlib.util.find_spec("dimos") is not None
    cli_available = shutil.which("dimos") is not None
    runtime_outcome = "GO" if python_import_available and cli_available else "NARROW_CLAIM"
    return {
        "source": source_probe,
        "python_import_available": python_import_available,
        "cli_available": cli_available,
        "runtime_outcome": runtime_outcome,
        "claim_boundary": (
            "This probe does not start DimOS, run a blueprint, open Rerun, "
            "or prove DimOS consumed the bridge timeline."
        ),
    }


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "scripts" / "prepare_dimos_bridge_pack.py").is_file()
            and (candidate / "accountable_swarm" / "trace" / "models.py").is_file()
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


def _contains_secret_material(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


def _events_are_integer_only(events: list[dict[str, Any]]) -> bool:
    try:
        canonical_json(events)
    except TypeError:
        return False
    return all(
        _is_plain_int(event["tick"])
        and _is_plain_int(event["position_cell"]["x"])
        and _is_plain_int(event["position_cell"]["y"])
        and _is_plain_int(event["grid"]["width"])
        and _is_plain_int(event["grid"]["height"])
        for event in events
    )


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


def _is_hex_64(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
