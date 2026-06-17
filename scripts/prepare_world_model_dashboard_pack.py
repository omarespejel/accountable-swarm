#!/usr/bin/env python3
"""Prepare verified data for the accountable world-model dashboard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any

from accountable_swarm.trace.models import DecisionTrace, canonical_json, trace_from_dict, verify_trace
from accountable_swarm.world_model import WorldModelState, verify_world_model_state, world_model_from_dict


DASHBOARD_PACK_SCHEMA_VERSION = "world-model-dashboard-pack-report.v1"
DASHBOARD_DATA_SCHEMA_VERSION = "world-model-dashboard-data.v1"
DEFAULT_TRACE_DIR = Path("runs/hazard_formation/world_model_x")
DEFAULT_HAZARD_REPORT = Path("runs/hazard_formation/world_model_x_report.json")
DEFAULT_OUT_DIR = Path("runs/dashboard/world_model_x")
DEFAULT_SOURCE_IMAGE = None
DEFAULT_DIMOS_BRIDGE_MANIFEST = None
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Authorization:\s*Bearer\s+\S+", re.IGNORECASE),
    re.compile(r"ALIBABA_API_KEY\s*=\s*\S+", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9._-]{6,}"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-dir", type=Path, default=DEFAULT_TRACE_DIR)
    parser.add_argument("--hazard-report", type=Path, default=DEFAULT_HAZARD_REPORT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--source-image", type=Path, default=DEFAULT_SOURCE_IMAGE)
    parser.add_argument("--dimos-bridge-manifest", type=Path, default=DEFAULT_DIMOS_BRIDGE_MANIFEST)
    args = parser.parse_args()

    try:
        repo_root = _find_repo_root(Path.cwd())
        trace_dir = _repo_path(repo_root, args.trace_dir)
        hazard_report_path = _repo_path(repo_root, args.hazard_report)
        out_dir = _repo_path(repo_root, args.out_dir)
        source_image_path = _optional_repo_path(repo_root, args.source_image)
        dimos_bridge_manifest_path = _optional_repo_path(repo_root, args.dimos_bridge_manifest)
        _require_inside_repo(repo_root, trace_dir, "trace-dir")
        _require_inside_repo(repo_root, hazard_report_path, "hazard-report")
        _require_inside_repo(repo_root, out_dir, "out-dir")
        if source_image_path is not None:
            _require_inside_repo(repo_root, source_image_path, "source-image")
        if dimos_bridge_manifest_path is not None:
            _require_inside_repo(repo_root, dimos_bridge_manifest_path, "dimos-bridge-manifest")

        pack = _build_pack(
            repo_root=repo_root,
            trace_dir=trace_dir,
            hazard_report_path=hazard_report_path,
            out_dir=out_dir,
            source_image_path=source_image_path,
            dimos_bridge_manifest_path=dimos_bridge_manifest_path,
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        copied_asset_count = _copy_assets(
            repo_root=repo_root,
            out_dir=out_dir,
            assets=pack["copied_assets"],
        )
        if source_image_path is not None and copied_asset_count != len(pack["copied_assets"]):
            raise ValueError("source-image asset copy did not complete")
        _set_source_image_copy_result(
            pack=pack,
            copied_ok=(source_image_path is None or copied_asset_count > 0),
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"world-model dashboard pack failed: {exc}", file=sys.stderr)
        return 4

    data_path = out_dir / "data.json"
    manifest_path = out_dir / "manifest.json"
    data_path.write_text(canonical_json(pack["data"]) + "\n", encoding="utf-8")
    manifest_path.write_text(canonical_json(pack["manifest"]) + "\n", encoding="utf-8")

    print(f"outcome {pack['manifest']['outcome']}")
    print(f"data {_display_path(repo_root, data_path)}")
    print(f"manifest {_display_path(repo_root, manifest_path)}")
    print(f"state_count {pack['manifest']['state_count']}")
    return 0 if pack["manifest"]["outcome"] == "GO" else 4


def _build_pack(
    *,
    repo_root: Path,
    trace_dir: Path,
    hazard_report_path: Path,
    out_dir: Path,
    source_image_path: Path | None,
    dimos_bridge_manifest_path: Path | None,
) -> dict[str, Any]:
    hazard_report = _read_json_object(hazard_report_path, "hazard report")
    hazard_trace_path = _contained_path(repo_root, trace_dir / "hazard.json", "hazard trace")
    mission_choice_report = hazard_report.get("mission_choice")
    agent_trace_dir = _contained_path(repo_root, trace_dir / "agents", "agent trace dir")
    export_trace_path = _contained_path(repo_root, trace_dir / "world_model_export.json", "world model export trace")
    timeline_path = _contained_path(repo_root, trace_dir / "world_model_timeline.jsonl", "world model timeline")
    hazard_trace = _read_trace(hazard_trace_path, "hazard trace")
    hazard_trace_sha = verify_trace(hazard_trace)
    mission_trace_info = _read_optional_mission_trace(
        repo_root=repo_root,
        trace_dir=trace_dir,
        mission_choice_report=mission_choice_report,
    )
    agent_traces = _read_agent_traces(agent_trace_dir, repo_root=repo_root)
    agent_trace_shas = {agent_id: verify_trace(trace) for agent_id, trace in sorted(agent_traces.items())}
    export_trace = _read_trace(export_trace_path, "world model export trace")
    export_trace_sha = verify_trace(export_trace)
    states = _read_world_model_timeline(timeline_path)
    state_hashes = [verify_world_model_state(state) for state in states]

    _validate_report_and_sources(
        repo_root=repo_root,
        trace_dir=trace_dir,
        hazard_report=hazard_report,
        hazard_trace_sha=hazard_trace_sha,
        mission_trace_info=mission_trace_info,
        agent_trace_shas=agent_trace_shas,
        export_trace_sha=export_trace_sha,
        states=states,
        state_hashes=state_hashes,
    )
    timeline = _timeline_from_states(
        states=states,
        agent_traces=agent_traces,
        agent_trace_shas=agent_trace_shas,
        hazard_trace_sha=hazard_trace_sha,
    )
    copied_assets: list[dict[str, Any]] = []
    image_metadata = dict(_require_dict(hazard_report.get("image", {}), "hazard report image"))
    if source_image_path is not None:
        if not source_image_path.is_file():
            raise ValueError("source-image file is required")
        image_asset_relative_path = Path("assets") / source_image_path.name
        copied_assets.append(
            {
                "source_path": source_image_path,
                "relative_path": image_asset_relative_path,
            }
        )
        image_metadata["asset_path"] = image_asset_relative_path.as_posix()
    dimos_export = _read_dimos_bridge_manifest(
        repo_root=repo_root,
        manifest_path=dimos_bridge_manifest_path,
    )
    source = {
        "hazard_report": _display_path(repo_root, hazard_report_path),
        "hazard_trace": _display_path(repo_root, hazard_trace_path),
        "agent_trace_dir": _display_path(repo_root, agent_trace_dir),
        "world_model_timeline": _display_path(repo_root, timeline_path),
        "world_model_export_trace": _display_path(repo_root, export_trace_path),
    }
    if mission_trace_info is not None:
        source["mission_trace"] = mission_trace_info["path"]
    data = {
        "schema_version": DASHBOARD_DATA_SCHEMA_VERSION,
        "source": source,
        "image": image_metadata,
        "mode": hazard_report.get("mode", ""),
        "model": hazard_report.get("model", ""),
        "formation": hazard_report.get("formation"),
        "mission_choice": mission_trace_info["payload"] if mission_trace_info is not None else None,
        "grid": hazard_report.get("grid", {}),
        "hazard": hazard_report.get("hazard"),
        "formation_plan": hazard_report.get("formation_plan"),
        "assigned_goals": hazard_report.get("assigned_goals", {}),
        "hazard_trace_summary_sha": hazard_trace_sha,
        "mission_trace_summary_sha": (
            mission_trace_info["trace_summary_sha"] if mission_trace_info is not None else ""
        ),
        "agent_trace_summary_shas": dict(sorted(agent_trace_shas.items())),
        "world_model": {
            "state_count": len(states),
            "first_world_model_sha": state_hashes[0],
            "last_world_model_sha": state_hashes[-1],
            "export_trace_summary_sha": export_trace_sha,
            "predicted_conflict_count": sum(len(state.predicted_conflicts) for state in states),
        },
        "dimos_export": dimos_export,
        "timeline": timeline,
        "planner_metrics": {
            "outcome": hazard_report.get("sim_report", {}).get("outcome"),
            "same_cell_collision_count": hazard_report.get("sim_report", {}).get("same_cell_collision_count"),
            "swap_collision_count": hazard_report.get("sim_report", {}).get("swap_collision_count"),
            "obstacle_occupancy_violation_count": hazard_report.get("sim_report", {}).get(
                "obstacle_occupancy_violation_count"
            ),
            "reroute_count": hazard_report.get("sim_report", {}).get("reroute_count"),
            "hold_count": hazard_report.get("sim_report", {}).get("hold_count"),
            "all_goals_reached": hazard_report.get("sim_report", {}).get("all_goals_reached"),
        },
        "pass_conditions": hazard_report.get("pass_conditions", {}),
        "non_claims": _non_claims(),
    }
    data_text = canonical_json(data)
    pass_conditions = {
        "source_paths_inside_repo": True,
        "hazard_report_schema_valid": hazard_report.get("schema_version") == "hazard-formation-gate-report.v1",
        "hazard_report_accepted_outcome": hazard_report.get("outcome") in {"GO", "DEGRADED"},
        "hazard_trace_verified": _is_hex_64(hazard_trace_sha),
        "agent_traces_verified": bool(agent_trace_shas) and all(_is_hex_64(value) for value in agent_trace_shas.values()),
        "world_model_export_trace_verified": _is_hex_64(export_trace_sha),
        "world_model_timeline_verified": bool(state_hashes) and all(_is_hex_64(value) for value in state_hashes),
        "report_hashes_match_sources": True,
        "timeline_matches_traces": True,
        "source_image_copied": source_image_path is None,
        "dimos_export_summary_valid": dimos_export is None or dimos_export.get("bridge_manifest_schema") == "dimos-bridge-pack-report.v1",
        "dashboard_data_contains_no_key_material": not _contains_secret_material(data_text),
        "dashboard_data_paths_are_relative": not _contains_absolute_path(data),
        "dashboard_data_canonical_json_stable": canonical_json(json.loads(data_text)) == data_text,
    }
    manifest = {
        "schema_version": DASHBOARD_PACK_SCHEMA_VERSION,
        "outcome": "GO" if all(pass_conditions.values()) else "NARROW_CLAIM",
        "data_path": _display_path(repo_root, out_dir / "data.json"),
        "source": data["source"],
        "state_count": len(states),
        "agent_count": len(agent_trace_shas),
        "first_world_model_sha": state_hashes[0],
        "last_world_model_sha": state_hashes[-1],
        "world_model_export_trace_summary_sha": export_trace_sha,
        "dimos_export": dimos_export,
        "pass_conditions": pass_conditions,
        "non_claims": _non_claims(),
    }
    manifest_text = canonical_json(manifest)
    if _contains_secret_material(manifest_text):
        raise ValueError("dashboard manifest would contain secret material")
    if _contains_absolute_path(manifest):
        raise ValueError("dashboard manifest would contain an absolute path")
    return {"data": data, "manifest": manifest, "copied_assets": copied_assets}


def _validate_report_and_sources(
    *,
    repo_root: Path,
    trace_dir: Path,
    hazard_report: dict[str, Any],
    hazard_trace_sha: str,
    mission_trace_info: dict[str, Any] | None,
    agent_trace_shas: dict[str, str],
    export_trace_sha: str,
    states: list[WorldModelState],
    state_hashes: list[str],
) -> None:
    if hazard_report.get("schema_version") != "hazard-formation-gate-report.v1":
        raise ValueError("hazard report uses an unsupported schema")
    if hazard_report.get("outcome") not in {"GO", "DEGRADED"}:
        raise ValueError("hazard report outcome must be GO or DEGRADED")
    if hazard_report.get("hazard_trace_summary_sha") != hazard_trace_sha:
        raise ValueError("hazard report hazard_trace_summary_sha does not match hazard trace")
    report_mission = hazard_report.get("mission_choice")
    if mission_trace_info is None:
        if report_mission not in (None, {}):
            raise ValueError("hazard report mission_choice requires mission trace evidence")
    else:
        report_mission = _require_dict(report_mission, "hazard report mission_choice")
        if report_mission.get("trace_summary_sha") != mission_trace_info["trace_summary_sha"]:
            raise ValueError("hazard report mission_choice trace_summary_sha does not match mission trace")
        if report_mission.get("choice") != mission_trace_info["payload"]["choice"]:
            raise ValueError("hazard report mission_choice choice does not match mission trace")
    if hazard_report.get("trace_summary_shas") != agent_trace_shas:
        raise ValueError("hazard report trace_summary_shas do not match agent traces")
    report_world_model = _require_dict(hazard_report.get("world_model"), "hazard report world_model")
    expected_timeline = _display_path(repo_root, trace_dir / "world_model_timeline.jsonl")
    if report_world_model.get("path") != expected_timeline:
        raise ValueError("hazard report world_model path does not match trace-dir timeline")
    expected_export_trace = _display_path(repo_root, trace_dir / "world_model_export.json")
    if report_world_model.get("export_trace_path") != expected_export_trace:
        raise ValueError("hazard report world_model export_trace_path does not match trace-dir export trace")
    if report_world_model.get("export_trace_summary_sha") != export_trace_sha:
        raise ValueError("hazard report world_model export_trace_summary_sha does not match export trace")
    if report_world_model.get("state_count") != len(states):
        raise ValueError("hazard report world_model state_count does not match timeline")
    if not states:
        raise ValueError("world model timeline must contain at least one state")
    if report_world_model.get("first_world_model_sha") != state_hashes[0]:
        raise ValueError("hazard report first_world_model_sha does not match timeline")
    if report_world_model.get("last_world_model_sha") != state_hashes[-1]:
        raise ValueError("hazard report last_world_model_sha does not match timeline")


def _timeline_from_states(
    *,
    states: list[WorldModelState],
    agent_traces: dict[str, DecisionTrace],
    agent_trace_shas: dict[str, str],
    hazard_trace_sha: str,
) -> list[dict[str, Any]]:
    timeline = []
    for state in states:
        agents = []
        for agent in sorted(state.agents, key=lambda item: item.agent_id):
            trace = agent_traces.get(agent.agent_id)
            if trace is None:
                raise ValueError(f"world model references unknown agent trace: {agent.agent_id}")
            if state.tick >= len(trace.events):
                raise ValueError(f"world model tick {state.tick} exceeds trace length for {agent.agent_id}")
            event = trace.events[state.tick]
            if event.tick != state.tick:
                raise ValueError(f"trace tick mismatch for {agent.agent_id}")
            if event.actor_id != agent.agent_id:
                raise ValueError(f"trace actor_id does not match world model agent for {agent.agent_id}")
            command = event.command
            accepted_x = _require_int(command, "accepted_x")
            accepted_y = _require_int(command, "accepted_y")
            goal_x = _require_int(command, "goal_x")
            goal_y = _require_int(command, "goal_y")
            if (agent.cell.x, agent.cell.y) != (accepted_x, accepted_y):
                raise ValueError(f"world model agent cell does not match trace command for {agent.agent_id}")
            if (agent.goal.x, agent.goal.y) != (goal_x, goal_y):
                raise ValueError(f"world model agent goal does not match trace command for {agent.agent_id}")
            if agent.last_decision != event.decision:
                raise ValueError(f"world model last_decision does not match trace for {agent.agent_id}")
            if agent.decision_trace_sha != agent_trace_shas[agent.agent_id]:
                raise ValueError(f"world model decision_trace_sha does not match trace for {agent.agent_id}")
            if agent.decision_event_sha != event.sha256:
                raise ValueError(f"world model decision_event_sha does not match trace event for {agent.agent_id}")
            agents.append(
                {
                    "agent_id": agent.agent_id,
                    "cell": agent.cell.to_dict(),
                    "goal": agent.goal.to_dict(),
                    "decision": event.decision,
                    "reason": event.reason,
                    "event_sha256": event.sha256,
                    "world_model_decision_event_sha": agent.decision_event_sha,
                    "trace_summary_sha": agent_trace_shas[agent.agent_id],
                    "command": {
                        "from_x": _require_int(command, "from_x"),
                        "from_y": _require_int(command, "from_y"),
                        "proposed_x": _require_int(command, "proposed_x"),
                        "proposed_y": _require_int(command, "proposed_y"),
                        "accepted_x": accepted_x,
                        "accepted_y": accepted_y,
                        "goal_x": goal_x,
                        "goal_y": goal_y,
                    },
                }
            )
        for reservation in state.reservations:
            matching_agent = next((agent for agent in state.agents if agent.agent_id == reservation.agent_id), None)
            if matching_agent is None:
                raise ValueError(f"reservation references unknown agent: {reservation.agent_id}")
            if reservation.tick != state.tick:
                raise ValueError("reservation tick does not match world model tick")
            if reservation.cell != matching_agent.cell:
                raise ValueError(f"reservation cell does not match agent cell for {reservation.agent_id}")
        for observation in state.observations:
            if observation.source_trace_sha != hazard_trace_sha:
                raise ValueError("world model observation source_trace_sha does not match hazard trace")
        timeline.append(
            {
                "tick": state.tick,
                "world_model_sha": state.world_model_sha,
                "observations": [observation.to_dict() for observation in state.observations],
                "hazards": [hazard.to_dict() for hazard in state.hazards],
                "agents": agents,
                "reservations": [reservation.to_dict() for reservation in state.reservations],
                "predicted_conflicts": [conflict.to_dict() for conflict in state.predicted_conflicts],
            }
        )
    return timeline


def _read_trace(path: Path, name: str) -> DecisionTrace:
    if not path.is_file():
        raise ValueError(f"{name} file is required")
    payload = _read_json_object(path, name)
    trace = trace_from_dict(payload)
    verify_trace(trace)
    return trace


def _read_optional_mission_trace(
    *,
    repo_root: Path,
    trace_dir: Path,
    mission_choice_report: Any,
) -> dict[str, Any] | None:
    if mission_choice_report in (None, {}):
        return None
    report = _require_dict(mission_choice_report, "hazard report mission_choice")
    trace_path = _contained_path(repo_root, trace_dir / "mission.json", "mission trace")
    mission_trace = _read_trace(trace_path, "mission trace")
    trace_summary_sha = verify_trace(mission_trace)
    payload = {
        "source": _require_string(report, "source"),
        "model": _require_string(report, "model"),
        "choice": _require_dict(report.get("choice"), "mission choice payload"),
    }
    return {
        "path": _display_path(repo_root, trace_path),
        "trace_summary_sha": trace_summary_sha,
        "payload": payload,
    }


def _read_agent_traces(path: Path, *, repo_root: Path) -> dict[str, DecisionTrace]:
    if not path.is_dir():
        raise ValueError("agent trace directory is required")
    traces = {}
    for trace_path in sorted(path.glob("*.json")):
        trace_path = _contained_path(repo_root, trace_path, trace_path.name)
        trace = _read_trace(trace_path, trace_path.name)
        agent_id = trace_path.stem
        if trace.run_id and not trace.run_id.endswith(f"-{agent_id}"):
            raise ValueError(f"agent trace filename does not match run_id for {agent_id}")
        for index, event in enumerate(trace.events):
            if event.actor_id != agent_id:
                raise ValueError(f"agent trace actor_id does not match filename for {agent_id}")
            if event.tick != index:
                raise ValueError(f"agent trace ticks must be contiguous for {agent_id}")
        traces[agent_id] = trace
    if not traces:
        raise ValueError("at least one agent trace is required")
    return traces


def _read_world_model_timeline(path: Path) -> list[WorldModelState]:
    if not path.is_file():
        raise ValueError("world_model_timeline.jsonl is required")
    states = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            raise ValueError(f"world model timeline line {line_number} is empty")
        payload = json.loads(line)
        state = world_model_from_dict(payload)
        verify_world_model_state(state)
        if state.to_canonical_json() != line:
            raise ValueError(f"world model timeline line {line_number} is not canonical JSON")
        states.append(state)
    if not states:
        raise ValueError("world model timeline must contain at least one state")
    return states


def _read_json_object(path: Path, name: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"{name} file is required")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _require_dict(payload, name)


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "scripts" / "run_hazard_formation_gate.py").is_file()
            and (candidate / "fixtures" / "hazard_marker.ppm").is_file()
        ):
            return candidate
    raise ValueError("run from an accountable-swarm checkout")


def _repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _optional_repo_path(repo_root: Path, path: Path | None) -> Path | None:
    if path is None:
        return None
    return _repo_path(repo_root, path)


def _copy_assets(*, repo_root: Path, out_dir: Path, assets: list[dict[str, Any]]) -> int:
    copied = 0
    for asset in assets:
        source_path = Path(asset["source_path"])
        relative_path = Path(asset["relative_path"])
        if not source_path.is_file():
            raise ValueError(f"asset source file is required: {_display_path(repo_root, source_path)}")
        target_path = out_dir / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target_path)
        if not target_path.is_file():
            raise ValueError(f"asset copy did not produce a file: {_display_path(repo_root, target_path)}")
        copied += 1
    return copied


def _set_source_image_copy_result(*, pack: dict[str, Any], copied_ok: bool) -> None:
    pack["data"]["pass_conditions"]["source_image_copied"] = copied_ok
    pack["manifest"]["pass_conditions"]["source_image_copied"] = copied_ok
    pack["manifest"]["outcome"] = "GO" if all(pack["manifest"]["pass_conditions"].values()) else "NARROW_CLAIM"


def _require_inside_repo(repo_root: Path, path: Path, name: str) -> None:
    _contained_path(repo_root, path, name)


def _contained_path(repo_root: Path, path: Path, name: str) -> Path:
    resolved_root = repo_root.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"{name} must be inside the repository") from exc
    return resolved


def _display_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _require_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _require_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _require_int(value: dict[str, Any], key: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int):
        raise ValueError(f"{key} must be an integer")
    return item


def _require_nonbool_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _require_string(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise ValueError(f"{key} must be a non-empty string")
    return item


def _require_non_empty_string_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be a non-empty string list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValueError(f"{name} must contain non-empty strings")
        result.append(item)
    return result


def _is_hex_64(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _contains_secret_material(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


def _contains_absolute_path(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_absolute_path(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_absolute_path(item) for item in value)
    if isinstance(value, str):
        return Path(value).is_absolute() or bool(re.match(r"^[A-Za-z]:[\\/]", value))
    return False


def _read_dimos_bridge_manifest(*, repo_root: Path, manifest_path: Path | None) -> dict[str, Any] | None:
    if manifest_path is None:
        return None
    payload = _read_json_object(manifest_path, "dimos bridge manifest")
    if payload.get("schema_version") != "dimos-bridge-pack-report.v1":
        raise ValueError("dimos bridge manifest uses an unsupported schema")
    bridge_outcome = _require_string(payload, "bridge_outcome")
    overall_outcome = _require_string(payload, "outcome")
    event_count = _require_nonbool_int(payload.get("event_count"), "dimos bridge event_count")
    scenario_count = _require_nonbool_int(payload.get("scenario_count"), "dimos bridge scenario_count")
    manifest_scenarios = _require_non_empty_string_list(payload.get("scenarios"), "dimos bridge scenarios")
    artifacts = _require_dict(payload.get("artifacts"), "dimos bridge artifacts")
    timeline_path = artifacts.get("timeline_ndjson")
    manifest_rel_path = artifacts.get("manifest")
    if not isinstance(timeline_path, str) or not timeline_path:
        raise ValueError("dimos bridge timeline path must be a non-empty string")
    if not isinstance(manifest_rel_path, str) or not manifest_rel_path:
        raise ValueError("dimos bridge manifest path must be a non-empty string")
    if _contains_absolute_path(payload):
        raise ValueError("dimos bridge manifest must not contain absolute paths")
    if _contains_secret_material(canonical_json(payload)):
        raise ValueError("dimos bridge manifest contains secret material")
    dimos_probe = _require_dict(payload.get("dimos_probe"), "dimos bridge probe")
    runtime_outcome = _require_string(dimos_probe, "runtime_outcome")
    source_probe = _require_dict(dimos_probe.get("source"), "dimos source probe")
    source_checkout_provided = _require_bool(source_probe.get("checkout_provided"), "dimos source checkout_provided")
    timeline_abspath = _contained_path(repo_root, repo_root / timeline_path, "dimos bridge timeline")
    timeline_events = _read_dimos_timeline_events(timeline_abspath)
    timeline_scenarios = sorted({event["scenario"] for event in timeline_events})
    if event_count != len(timeline_events):
        raise ValueError("dimos bridge event_count does not match timeline")
    if scenario_count != len(timeline_scenarios):
        raise ValueError("dimos bridge scenario_count does not match timeline")
    if manifest_scenarios != timeline_scenarios:
        raise ValueError("dimos bridge scenarios do not match timeline")
    expected_manifest_path = _display_path(repo_root, manifest_path)
    expected_timeline_path = _display_path(repo_root, timeline_abspath)
    if manifest_rel_path != expected_manifest_path:
        raise ValueError("dimos bridge manifest artifact path does not match provided manifest")
    if timeline_path != expected_timeline_path:
        raise ValueError("dimos bridge timeline artifact path does not match referenced timeline")
    return {
        "bridge_manifest_schema": payload["schema_version"],
        "bridge_outcome": bridge_outcome,
        "overall_outcome": overall_outcome,
        "runtime_outcome": runtime_outcome,
        "event_count": event_count,
        "scenario_count": scenario_count,
        "timeline_path": timeline_path,
        "manifest_path": manifest_rel_path,
        "source_checkout_provided": source_checkout_provided,
    }


def _read_dimos_timeline_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError("dimos bridge timeline.ndjson is required")
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            raise ValueError(f"dimos bridge timeline line {line_number} is empty")
        payload = _read_json_object_line(line, f"dimos bridge timeline line {line_number}")
        if payload.get("schema_version") != "dimos-swarm-replay-event.v1":
            raise ValueError("dimos bridge timeline uses an unsupported event schema")
        _require_string(payload, "scenario")
        events.append(payload)
    if not events:
        raise ValueError("dimos bridge timeline must contain at least one event")
    return events


def _read_json_object_line(line: str, name: str) -> dict[str, Any]:
    payload = json.loads(line)
    return _require_dict(payload, name)


def _non_claims() -> list[str]:
    return [
        "no physical robot behavior",
        "no SO-101 operation",
        "no learned world model",
        "no 3D physics simulation",
        "no DimOS runtime execution",
        "no Open-RMF compatibility claim",
        "no Qwen real-time control",
        "no safety, latency, or reliability claim",
        "no Alibaba ECS deployment proof",
    ]


if __name__ == "__main__":
    raise SystemExit(main())
