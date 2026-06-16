#!/usr/bin/env python3
"""Prepare verified data for the accountable world-model dashboard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

from accountable_swarm.trace.models import DecisionTrace, canonical_json, trace_from_dict, verify_trace
from accountable_swarm.world_model import WorldModelState, verify_world_model_state, world_model_from_dict


DASHBOARD_PACK_SCHEMA_VERSION = "world-model-dashboard-pack-report.v1"
DASHBOARD_DATA_SCHEMA_VERSION = "world-model-dashboard-data.v1"
DEFAULT_TRACE_DIR = Path("runs/hazard_formation/world_model_x")
DEFAULT_HAZARD_REPORT = Path("runs/hazard_formation/world_model_x_report.json")
DEFAULT_OUT_DIR = Path("runs/dashboard/world_model_x")
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
    args = parser.parse_args()

    try:
        repo_root = _find_repo_root(Path.cwd())
        trace_dir = _repo_path(repo_root, args.trace_dir)
        hazard_report_path = _repo_path(repo_root, args.hazard_report)
        out_dir = _repo_path(repo_root, args.out_dir)
        _require_inside_repo(repo_root, trace_dir, "trace-dir")
        _require_inside_repo(repo_root, hazard_report_path, "hazard-report")
        _require_inside_repo(repo_root, out_dir, "out-dir")

        pack = _build_pack(
            repo_root=repo_root,
            trace_dir=trace_dir,
            hazard_report_path=hazard_report_path,
            out_dir=out_dir,
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"world-model dashboard pack failed: {exc}", file=sys.stderr)
        return 4

    out_dir.mkdir(parents=True, exist_ok=True)
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
) -> dict[str, dict[str, Any]]:
    hazard_report = _read_json_object(hazard_report_path, "hazard report")
    hazard_trace = _read_trace(trace_dir / "hazard.json", "hazard trace")
    hazard_trace_sha = verify_trace(hazard_trace)
    agent_traces = _read_agent_traces(trace_dir / "agents")
    agent_trace_shas = {agent_id: verify_trace(trace) for agent_id, trace in sorted(agent_traces.items())}
    states = _read_world_model_timeline(trace_dir / "world_model_timeline.jsonl")
    state_hashes = [verify_world_model_state(state) for state in states]

    _validate_report_and_sources(
        repo_root=repo_root,
        trace_dir=trace_dir,
        hazard_report=hazard_report,
        hazard_trace_sha=hazard_trace_sha,
        agent_trace_shas=agent_trace_shas,
        states=states,
        state_hashes=state_hashes,
    )
    timeline = _timeline_from_states(
        states=states,
        agent_traces=agent_traces,
        agent_trace_shas=agent_trace_shas,
        hazard_trace_sha=hazard_trace_sha,
    )
    data = {
        "schema_version": DASHBOARD_DATA_SCHEMA_VERSION,
        "source": {
            "hazard_report": _display_path(repo_root, hazard_report_path),
            "hazard_trace": _display_path(repo_root, trace_dir / "hazard.json"),
            "agent_trace_dir": _display_path(repo_root, trace_dir / "agents"),
            "world_model_timeline": _display_path(repo_root, trace_dir / "world_model_timeline.jsonl"),
        },
        "image": hazard_report.get("image", {}),
        "mode": hazard_report.get("mode", ""),
        "model": hazard_report.get("model", ""),
        "formation": hazard_report.get("formation"),
        "grid": hazard_report.get("grid", {}),
        "hazard": hazard_report.get("hazard"),
        "formation_plan": hazard_report.get("formation_plan"),
        "assigned_goals": hazard_report.get("assigned_goals", {}),
        "hazard_trace_summary_sha": hazard_trace_sha,
        "agent_trace_summary_shas": dict(sorted(agent_trace_shas.items())),
        "world_model": {
            "state_count": len(states),
            "first_world_model_sha": state_hashes[0],
            "last_world_model_sha": state_hashes[-1],
            "predicted_conflict_count": sum(len(state.predicted_conflicts) for state in states),
        },
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
        "world_model_timeline_verified": bool(state_hashes) and all(_is_hex_64(value) for value in state_hashes),
        "report_hashes_match_sources": True,
        "timeline_matches_traces": True,
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
        "pass_conditions": pass_conditions,
        "non_claims": _non_claims(),
    }
    manifest_text = canonical_json(manifest)
    if _contains_secret_material(manifest_text):
        raise ValueError("dashboard manifest would contain secret material")
    if _contains_absolute_path(manifest):
        raise ValueError("dashboard manifest would contain an absolute path")
    return {"data": data, "manifest": manifest}


def _validate_report_and_sources(
    *,
    repo_root: Path,
    trace_dir: Path,
    hazard_report: dict[str, Any],
    hazard_trace_sha: str,
    agent_trace_shas: dict[str, str],
    states: list[WorldModelState],
    state_hashes: list[str],
) -> None:
    if hazard_report.get("schema_version") != "hazard-formation-gate-report.v1":
        raise ValueError("hazard report uses an unsupported schema")
    if hazard_report.get("outcome") not in {"GO", "DEGRADED"}:
        raise ValueError("hazard report outcome must be GO or DEGRADED")
    if hazard_report.get("hazard_trace_summary_sha") != hazard_trace_sha:
        raise ValueError("hazard report hazard_trace_summary_sha does not match hazard trace")
    if hazard_report.get("trace_summary_shas") != agent_trace_shas:
        raise ValueError("hazard report trace_summary_shas do not match agent traces")
    report_world_model = _require_dict(hazard_report.get("world_model"), "hazard report world_model")
    expected_timeline = _display_path(repo_root, trace_dir / "world_model_timeline.jsonl")
    if report_world_model.get("path") != expected_timeline:
        raise ValueError("hazard report world_model path does not match trace-dir timeline")
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
            agents.append(
                {
                    "agent_id": agent.agent_id,
                    "cell": agent.cell.to_dict(),
                    "goal": agent.goal.to_dict(),
                    "decision": event.decision,
                    "reason": event.reason,
                    "event_sha256": event.sha256,
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


def _read_agent_traces(path: Path) -> dict[str, DecisionTrace]:
    if not path.is_dir():
        raise ValueError("agent trace directory is required")
    traces = {}
    for trace_path in sorted(path.glob("*.json")):
        trace = _read_trace(trace_path, trace_path.name)
        agent_id = trace_path.stem
        if trace.run_id and not trace.run_id.endswith(f"-{agent_id}"):
            raise ValueError(f"agent trace filename does not match run_id for {agent_id}")
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


def _require_inside_repo(repo_root: Path, path: Path, name: str) -> None:
    try:
        path.resolve().relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError(f"{name} must be inside the repository") from exc


def _display_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _require_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _require_int(value: dict[str, Any], key: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int):
        raise ValueError(f"{key} must be an integer")
    return item


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
