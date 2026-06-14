#!/usr/bin/env python3
"""Run the low-rate mission assignment gate for the deterministic swarm."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from accountable_swarm.qwen.client import DashScopeQwenClient, DashScopeResponseError, MissingAlibabaApiKey
from accountable_swarm.swarm import (
    MISSION_MODEL_FIXTURE_ID,
    MISSION_SCHEMA_VERSION,
    build_agent_traces,
    build_mission_trace,
    fixture_mission_response,
    parse_mission_response,
    qwen_mission_prompt,
    replay_swarm_traces,
    run_swarm_sim,
)
from accountable_swarm.trace.models import canonical_json, trace_from_dict, verify_trace


REPORT_SCHEMA_VERSION = "swarm-mission-gate-report.v1"
DEFAULT_MISSION_MODEL = "qwen-plus"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["fixture", "dashscope"], default="fixture")
    parser.add_argument("--model", default=DEFAULT_MISSION_MODEL)
    parser.add_argument("--trace-dir", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    args = parser.parse_args()

    try:
        response_text = _mission_response(mode=args.mode, model=args.model)
        spec = parse_mission_response(response_text)
    except MissingAlibabaApiKey as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except (DashScopeResponseError, ValueError, TypeError) as exc:
        print(f"swarm-mission-gate validation failed: {exc}", file=sys.stderr)
        return 4

    mission_model = args.model if args.mode == "dashscope" else MISSION_MODEL_FIXTURE_ID
    mission_trace = build_mission_trace(spec=spec, mode=args.mode, model=mission_model)
    mission_summary_sha = verify_trace(mission_trace)

    result = run_swarm_sim(
        agent_count=spec.agent_count,
        ticks=spec.ticks,
        scenario=spec.scenario,
        run_id=f"swarm-mission-{spec.mission_id}",
    )
    agent_traces = build_agent_traces(result)
    agent_summary_shas = {
        agent_id: verify_trace(trace) for agent_id, trace in sorted(agent_traces.items())
    }
    replay_report = replay_swarm_traces(agent_traces, obstacles=result.obstacles)
    sim_report = result.report_dict(agent_summary_shas)
    sim_report["replay"] = replay_report.to_dict()

    args.trace_dir.mkdir(parents=True, exist_ok=True)
    mission_trace_path = args.trace_dir / "mission.json"
    mission_trace_path.write_text(mission_trace.to_canonical_json() + "\n", encoding="utf-8")
    loaded_mission_trace = trace_from_dict(json.loads(mission_trace_path.read_text(encoding="utf-8")))
    mission_replay_sha = verify_trace(loaded_mission_trace)

    agents_dir = args.trace_dir / "agents"
    agents_dir.mkdir(exist_ok=True)
    for agent_id, trace in sorted(agent_traces.items()):
        (agents_dir / f"{agent_id}.json").write_text(trace.to_canonical_json() + "\n", encoding="utf-8")

    pass_conditions = {
        "mission_json_validated": True,
        "mission_trace_replay_deterministic": mission_summary_sha == mission_replay_sha,
        "sim_report_go": sim_report["outcome"] == "GO",
        "agent_trace_replay_counts_zero": (
            replay_report.same_cell_collision_count == 0
            and replay_report.swap_collision_count == 0
            and replay_report.obstacle_occupancy_violation_count == 0
        ),
    }
    outcome = "GO" if all(pass_conditions.values()) else "NARROW_CLAIM"
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "outcome": outcome,
        "mode": args.mode,
        "model": mission_model,
        "mission_schema_version": MISSION_SCHEMA_VERSION,
        "mission_validated": True,
        "mission": spec.to_dict(),
        "mission_trace_summary_sha": mission_summary_sha,
        "trace_summary_shas": agent_summary_shas,
        "pass_conditions": pass_conditions,
        "sim_report": sim_report,
        "non_claims": [
            "no physical robot behavior",
            "no SO-101 operation",
            "no 3D physics simulation",
            "no latency or reliability claim",
            "no DimOS integration",
            "no Alibaba deployment proof",
            "no claim that Qwen is in the real-time loop",
            "no live Qwen mission claim unless mode is dashscope and separately recorded",
        ],
    }
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(canonical_json(report) + "\n", encoding="utf-8")

    print(f"outcome {outcome}")
    print(f"mode {args.mode}")
    print(f"scenario {spec.scenario}")
    print(f"agent_count {spec.agent_count}")
    print(f"mission_trace_summary_sha {mission_summary_sha}")
    print(f"sim_report_outcome {sim_report['outcome']}")
    print(f"same_cell_collision_count {sim_report['same_cell_collision_count']}")
    print(f"swap_collision_count {sim_report['swap_collision_count']}")
    print(f"obstacle_occupancy_violation_count {sim_report['obstacle_occupancy_violation_count']}")
    print(f"wrote {args.trace_dir}")
    print(f"wrote {args.report_out}")
    return 0 if outcome == "GO" else 4


def _mission_response(*, mode: str, model: str) -> str:
    if mode == "fixture":
        return fixture_mission_response()
    return DashScopeQwenClient(model=model).chat_text(prompt=qwen_mission_prompt(), max_tokens=256)


if __name__ == "__main__":
    raise SystemExit(main())
