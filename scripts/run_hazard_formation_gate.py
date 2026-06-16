#!/usr/bin/env python3
"""Run the hazard-to-formation Accountable Swarm GO gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from accountable_swarm.images import image_size
from accountable_swarm.qwen.bbox import QwenGrounding, parse_qwen_bbox_response
from accountable_swarm.qwen.client import DashScopeQwenClient, DashScopeResponseError, MissingAlibabaApiKey
from accountable_swarm.swarm import (
    SUPPORTED_FORMATIONS,
    AgentConfig,
    GridPoint,
    assign_formation_slots,
    build_agent_traces,
    compile_formation,
    default_agent_configs,
    hazard_cell_from_grounding,
    points_to_dicts,
    replay_swarm_traces,
    run_swarm_custom,
)
from accountable_swarm.trace.models import (
    TRACE_SCHEMA_VERSION,
    PerceptionEvent,
    build_single_event_trace,
    canonical_json,
    trace_from_dict,
    verify_trace,
)
from accountable_swarm.world_model import (
    WorldAgentState,
    WorldModelState,
    WorldObservation,
    WorldReservation,
    verify_world_model_state,
    world_model_from_dict,
)


FIXTURE_RESPONSE = '[{"bbox_2d":[250,250,750,750],"label":"marked hazard"}]'
REPORT_SCHEMA_VERSION = "hazard-formation-gate-report.v1"
DEFAULT_GRID_WIDTH = 7
DEFAULT_GRID_HEIGHT = 5
DEFAULT_TICKS = 8
DEFAULT_MODEL = "qwen3-vl-flash"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--mode", choices=["fixture", "dashscope", "degraded"], default="fixture")
    parser.add_argument("--degraded-on-error", action="store_true")
    parser.add_argument("--target", default="marked hazard")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--formation", choices=SUPPORTED_FORMATIONS, default="surround")
    parser.add_argument("--grid-width", type=int, default=DEFAULT_GRID_WIDTH)
    parser.add_argument("--grid-height", type=int, default=DEFAULT_GRID_HEIGHT)
    parser.add_argument("--ticks", type=int, default=DEFAULT_TICKS)
    parser.add_argument("--trace-dir", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    args = parser.parse_args()

    try:
        report = _build_report(
            image_path=args.image,
            mode=args.mode,
            target=args.target,
            model=args.model,
            formation=args.formation,
            grid_width=args.grid_width,
            grid_height=args.grid_height,
            ticks=args.ticks,
            trace_dir=args.trace_dir,
        )
    except MissingAlibabaApiKey as exc:
        if not args.degraded_on_error:
            print(str(exc), file=sys.stderr)
            return 3
        report = _build_degraded_report(
            image_path=args.image,
            model=args.model,
            formation=args.formation,
            grid_width=args.grid_width,
            grid_height=args.grid_height,
            trace_dir=args.trace_dir,
            model_error=str(exc),
        )
    except (DashScopeResponseError, OSError, ValueError, TypeError) as exc:
        if not args.degraded_on_error:
            print(f"hazard-formation gate failed: {exc}", file=sys.stderr)
            return 4
        report = _build_degraded_report(
            image_path=args.image,
            model=args.model,
            formation=args.formation,
            grid_width=args.grid_width,
            grid_height=args.grid_height,
            trace_dir=args.trace_dir,
            model_error=str(exc),
        )

    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(canonical_json(report) + "\n", encoding="utf-8")
    print(f"outcome {report['outcome']}")
    print(f"mode {report['mode']}")
    print(f"formation {report['formation']}")
    print(f"trace_dir {args.trace_dir}")
    print(f"wrote {args.report_out}")
    return 0 if report["outcome"] in {"GO", "NARROW_CLAIM", "DEGRADED"} else 4


def _build_report(
    *,
    image_path: Path,
    mode: str,
    target: str,
    model: str,
    formation: str,
    grid_width: int,
    grid_height: int,
    ticks: int,
    trace_dir: Path,
) -> dict[str, Any]:
    if mode == "degraded":
        return _build_degraded_report(
            image_path=image_path,
            model=model,
            formation=formation,
            grid_width=grid_width,
            grid_height=grid_height,
            trace_dir=trace_dir,
            model_error="degraded mode requested",
        )
    _validate_image(image_path)
    width, height = image_size(image_path)
    response_text = _grounding_response(
        mode=mode,
        model=model,
        image_path=image_path,
        target=target,
    )
    grounding = parse_qwen_bbox_response(response_text, image_width=width, image_height=height)
    hazard = hazard_cell_from_grounding(grounding, grid_width=grid_width, grid_height=grid_height)
    perception = _perception_from_grounding(
        grounding=grounding,
        image_path=image_path,
        image_width=width,
        image_height=height,
        model=model if mode == "dashscope" else "fixture-qwen3-vl-shape",
    )
    hazard_trace = _hazard_trace(
        perception=perception,
        mode="cloud" if mode == "dashscope" else "fixture",
        hazard_cell=hazard.cell,
        grid_width=grid_width,
        grid_height=grid_height,
    )
    hazard_trace_sha = verify_trace(hazard_trace)

    plan = compile_formation(
        formation=formation,
        hazard_cell=hazard.cell,
        grid_width=grid_width,
        grid_height=grid_height,
        agent_count=4,
    )
    starts = default_agent_configs(4, grid_width=grid_width, grid_height=grid_height)
    configs = assign_formation_slots(starts=starts, plan=plan)
    result = run_swarm_custom(
        configs=configs,
        obstacles=(hazard.cell,),
        ticks=ticks,
        grid_width=grid_width,
        grid_height=grid_height,
        scenario=f"hazard-{formation}-formation",
        run_id=f"hazard-formation-{formation}-n4",
    )
    agent_report = _write_and_verify_traces(
        trace_dir=trace_dir,
        hazard_trace=hazard_trace,
        result=result,
    )
    world_report = _write_world_model_timeline(
        trace_dir=trace_dir,
        result=result,
        hazard_cell=hazard.cell,
        hazard_trace_sha=hazard_trace_sha,
        trace_summary_shas=agent_report["trace_summary_shas"],
        observation_source="qwen_bbox" if mode == "dashscope" else "fixture_bbox",
        observation_label=hazard.source_label,
        observation_bbox=hazard.bbox_2d_norm_1000,
        observation_score_milli=grounding.score_milli,
    )
    sim_report = result.report_dict(agent_report["trace_summary_shas"])
    sim_report["replay"] = agent_report["replay"]
    pass_conditions = {
        "hazard_perception_available": True,
        "hazard_cell_quantized": True,
        "formation_compiled": plan.agent_count == 4,
        "hazard_trace_replay_deterministic": agent_report["hazard_trace_replay_deterministic"],
        "agent_traces_replay_deterministic": agent_report["agent_traces_replay_deterministic"],
        "world_model_timeline_replay_deterministic": world_report["timeline_replay_deterministic"],
        "formation_run_go": sim_report["outcome"] == "GO",
        "trace_replay_clean": (
            sim_report["replay"]["same_cell_collision_count"] == 0
            and sim_report["replay"]["swap_collision_count"] == 0
            and sim_report["replay"]["obstacle_occupancy_violation_count"] == 0
        ),
    }
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "outcome": "GO" if all(pass_conditions.values()) else "NARROW_CLAIM",
        "mode": mode,
        "model": model if mode == "dashscope" else "fixture-qwen3-vl-shape",
        "image": {"name": image_path.name, "width": width, "height": height},
        "formation": formation,
        "grid": {"width": grid_width, "height": grid_height},
        "ticks": ticks,
        "hazard": hazard.to_dict(),
        "formation_plan": plan.to_dict(),
        "assigned_goals": {
            config.agent_id: config.goal.to_dict() for config in sorted(configs, key=lambda item: item.agent_id)
        },
        "hazard_trace_summary_sha": hazard_trace_sha,
        "trace_summary_shas": agent_report["trace_summary_shas"],
        "world_model": world_report,
        "pass_conditions": pass_conditions,
        "sim_report": sim_report,
        "model_error": "",
        "non_claims": _non_claims(mode=mode),
    }


def _build_degraded_report(
    *,
    image_path: Path,
    model: str,
    formation: str,
    grid_width: int,
    grid_height: int,
    trace_dir: Path,
    model_error: str,
) -> dict[str, Any]:
    width, height = _safe_image_size(image_path)
    perception = PerceptionEvent(
        event_id="hazard-perception-0000",
        source=f"degraded://{image_path.name}",
        image_width=width,
        image_height=height,
        label="degraded_no_model",
        bbox_2d_norm_1000=(0, 0, 1000, 1000),
        bbox_2d_px=(0, 0, width, height),
        model=f"{model}:unavailable",
    )
    hazard_trace = build_single_event_trace(
        run_id="hazard-formation-degraded-hazard",
        actor_id="edge-node-0",
        mode="degraded",
        perception=perception,
        intent="hold agents when cloud perception cannot be validated",
        decision="HOLD",
        reason="cloud perception unavailable or invalid; local safe fallback selected",
        command={"type": "hold", "duration_ticks": 1},
    )
    starts = default_agent_configs(4, grid_width=grid_width, grid_height=grid_height)
    hold_configs = tuple(
        AgentConfig(agent_id=config.agent_id, start=config.start, goal=config.start)
        for config in starts
    )
    result = run_swarm_custom(
        configs=hold_configs,
        obstacles=(),
        ticks=1,
        grid_width=grid_width,
        grid_height=grid_height,
        scenario="degraded-hold",
        run_id="hazard-formation-degraded-hold-n4",
    )
    agent_report = _write_and_verify_traces(
        trace_dir=trace_dir,
        hazard_trace=hazard_trace,
        result=result,
    )
    world_report = _write_world_model_timeline(
        trace_dir=trace_dir,
        result=result,
        hazard_cell=None,
        hazard_trace_sha=verify_trace(hazard_trace),
        trace_summary_shas=agent_report["trace_summary_shas"],
        observation_source="degraded",
        observation_label="degraded_no_model",
        observation_bbox=None,
        observation_score_milli=0,
    )
    sim_report = result.report_dict(agent_report["trace_summary_shas"])
    sim_report["replay"] = agent_report["replay"]
    pass_conditions = {
        "hazard_perception_unavailable": True,
        "degraded_hold_selected": sim_report["hold_count"] == 4 and sim_report["outcome"] == "GO",
        "hazard_trace_replay_deterministic": agent_report["hazard_trace_replay_deterministic"],
        "agent_traces_replay_deterministic": agent_report["agent_traces_replay_deterministic"],
        "world_model_timeline_replay_deterministic": world_report["timeline_replay_deterministic"],
        "trace_replay_clean": (
            sim_report["replay"]["same_cell_collision_count"] == 0
            and sim_report["replay"]["swap_collision_count"] == 0
            and sim_report["replay"]["obstacle_occupancy_violation_count"] == 0
        ),
    }
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "outcome": "DEGRADED" if all(pass_conditions.values()) else "NARROW_CLAIM",
        "mode": "degraded",
        "model": f"{model}:unavailable",
        "image": {"name": image_path.name, "width": width, "height": height},
        "formation": formation,
        "grid": {"width": grid_width, "height": grid_height},
        "ticks": 1,
        "hazard": None,
        "formation_plan": None,
        "assigned_goals": {
            config.agent_id: config.goal.to_dict()
            for config in sorted(hold_configs, key=lambda item: item.agent_id)
        },
        "hazard_trace_summary_sha": verify_trace(hazard_trace),
        "trace_summary_shas": agent_report["trace_summary_shas"],
        "world_model": world_report,
        "pass_conditions": pass_conditions,
        "sim_report": sim_report,
        "model_error": model_error,
        "non_claims": _non_claims(mode="degraded"),
    }


def _grounding_response(*, mode: str, model: str, image_path: Path, target: str) -> str:
    if mode == "fixture":
        return FIXTURE_RESPONSE
    return DashScopeQwenClient(model=model).detect_bbox(image_path=image_path, target=target)


def _perception_from_grounding(
    *,
    grounding: QwenGrounding,
    image_path: Path,
    image_width: int,
    image_height: int,
    model: str,
) -> PerceptionEvent:
    return PerceptionEvent(
        event_id="hazard-perception-0000",
        source=f"image://{image_path.name}",
        image_width=image_width,
        image_height=image_height,
        label=grounding.label,
        bbox_2d_norm_1000=grounding.bbox_2d_norm_1000,
        bbox_2d_px=grounding.bbox_2d_px,
        model=model,
        score_milli=grounding.score_milli,
    )


def _hazard_trace(
    *,
    perception: PerceptionEvent,
    mode: str,
    hazard_cell: GridPoint,
    grid_width: int,
    grid_height: int,
):
    return build_single_event_trace(
        run_id="hazard-formation-hazard",
        actor_id="edge-node-0",
        mode=mode,
        perception=perception,
        intent="quantize keyframe hazard into local formation planner grid",
        decision="MOVE",
        reason="validated hazard bbox accepted as local planner input",
        command={
            "type": "hazard_cell",
            "grid_width": grid_width,
            "grid_height": grid_height,
            "hazard_x": hazard_cell.x,
            "hazard_y": hazard_cell.y,
        },
    )


def _write_and_verify_traces(
    *,
    trace_dir: Path,
    hazard_trace,
    result,
) -> dict[str, Any]:
    trace_dir.mkdir(parents=True, exist_ok=True)
    hazard_path = trace_dir / "hazard.json"
    hazard_path.write_text(hazard_trace.to_canonical_json() + "\n", encoding="utf-8")
    hazard_loaded = trace_from_dict(json.loads(hazard_path.read_text(encoding="utf-8")))
    hazard_replay_sha = verify_trace(hazard_loaded)
    hazard_summary_sha = verify_trace(hazard_trace)

    agents_dir = trace_dir / "agents"
    agents_dir.mkdir(exist_ok=True)
    traces = build_agent_traces(result)
    loaded_traces = {}
    trace_summary_shas = {}
    for agent_id, trace in sorted(traces.items()):
        trace_path = agents_dir / f"{agent_id}.json"
        trace_path.write_text(trace.to_canonical_json() + "\n", encoding="utf-8")
        loaded = trace_from_dict(json.loads(trace_path.read_text(encoding="utf-8")))
        loaded_traces[agent_id] = loaded
        trace_summary_shas[agent_id] = verify_trace(loaded)
    replay = replay_swarm_traces(loaded_traces, obstacles=result.obstacles)
    agent_replay_matches = all(
        trace_summary_shas[agent_id] == verify_trace(traces[agent_id])
        for agent_id in sorted(trace_summary_shas)
    )
    return {
        "hazard_trace_replay_deterministic": hazard_summary_sha == hazard_replay_sha,
        "agent_traces_replay_deterministic": agent_replay_matches,
        "trace_summary_shas": trace_summary_shas,
        "replay": replay.to_dict(),
    }


def _write_world_model_timeline(
    *,
    trace_dir: Path,
    result,
    hazard_cell: GridPoint | None,
    hazard_trace_sha: str,
    trace_summary_shas: dict[str, str],
    observation_source: str,
    observation_label: str,
    observation_bbox: tuple[int, int, int, int] | None,
    observation_score_milli: int,
) -> dict[str, Any]:
    timeline_path = trace_dir / "world_model_timeline.jsonl"
    timeline_path.parent.mkdir(parents=True, exist_ok=True)
    states = []
    for tick in result.ticks:
        state = _world_state_for_tick(
            result=result,
            tick=tick,
            hazard_cell=hazard_cell,
            hazard_trace_sha=hazard_trace_sha,
            trace_summary_shas=trace_summary_shas,
            observation_source=observation_source,
            observation_label=observation_label,
            observation_bbox=observation_bbox,
            observation_score_milli=observation_score_milli,
        ).with_computed_sha()
        states.append(state)
    timeline_path.write_text(
        "".join(state.to_canonical_json() + "\n" for state in states),
        encoding="utf-8",
    )
    loaded = [
        world_model_from_dict(json.loads(line))
        for line in timeline_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    replay_hashes = [verify_world_model_state(state) for state in loaded]
    original_hashes = [verify_world_model_state(state) for state in states]
    return {
        "schema_version": "world-model-timeline-report.v1",
        "path": _display_path(timeline_path),
        "state_count": len(states),
        "first_world_model_sha": original_hashes[0] if original_hashes else "",
        "last_world_model_sha": original_hashes[-1] if original_hashes else "",
        "timeline_replay_deterministic": replay_hashes == original_hashes,
        "predicted_conflict_count": sum(len(state.predicted_conflicts) for state in states),
    }


def _world_state_for_tick(
    *,
    result,
    tick,
    hazard_cell: GridPoint | None,
    hazard_trace_sha: str,
    trace_summary_shas: dict[str, str],
    observation_source: str,
    observation_label: str,
    observation_bbox: tuple[int, int, int, int] | None,
    observation_score_milli: int,
) -> WorldModelState:
    observations = (
        WorldObservation(
            observation_id="hazard-observation-0000",
            source=observation_source,
            label=observation_label,
            cell=hazard_cell or GridPoint(0, 0),
            source_trace_sha=hazard_trace_sha,
            bbox_2d_norm_1000=observation_bbox,
            score_milli=observation_score_milli,
        ),
    )
    goals = {config.agent_id: config.goal for config in result.configs}
    agents = tuple(
        WorldAgentState(
            agent_id=step.agent_id,
            cell=step.accepted,
            goal=goals[step.agent_id],
            decision_trace_sha=trace_summary_shas[step.agent_id],
            last_decision=step.decision,
        )
        for step in tick.steps
    )
    reservations = tuple(
        WorldReservation(tick=step.tick, agent_id=step.agent_id, cell=step.accepted)
        for step in tick.steps
    )
    return WorldModelState(
        tick=tick.tick,
        grid_width=result.grid_width,
        grid_height=result.grid_height,
        observations=observations,
        hazards=(hazard_cell,) if hazard_cell is not None else (),
        agents=agents,
        reservations=reservations,
        predicted_conflicts=(),
    )


def _validate_image(image_path: Path) -> None:
    if not image_path.exists():
        raise ValueError(f"image does not exist: {image_path}")
    if not image_path.is_file():
        raise ValueError(f"image is not a file: {image_path}")


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _safe_image_size(image_path: Path) -> tuple[int, int]:
    if image_path.exists() and image_path.is_file():
        return image_size(image_path)
    return (1, 1)


def _non_claims(*, mode: str) -> list[str]:
    claims = [
        "no physical robot behavior",
        "no SO-101 operation",
        "no safety claim",
        "no latency or reliability claim",
        "no 3D physics simulation",
        "no DimOS integration",
        "no Qwen real-time control",
        "no physical swarm claim",
        "no arbitrary-map planner claim",
    ]
    if mode != "dashscope":
        claims.append("no live Qwen hazard perception claim")
    return claims


if __name__ == "__main__":
    raise SystemExit(main())
