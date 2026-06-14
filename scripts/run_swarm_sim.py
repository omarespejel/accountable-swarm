#!/usr/bin/env python3
"""Run the deterministic simulated swarm GO gate."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from accountable_swarm.swarm import build_agent_traces, replay_swarm_traces, run_swarm_sim, scenario_names
from accountable_swarm.trace.models import canonical_json, verify_trace


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agents", type=int, default=2)
    parser.add_argument("--ticks", type=int, default=8)
    parser.add_argument("--grid-width", type=int, default=7)
    parser.add_argument("--grid-height", type=int, default=5)
    parser.add_argument(
        "--scenario",
        choices=scenario_names(),
        default="corridor",
    )
    parser.add_argument("--trace-dir", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    args = parser.parse_args()

    result = run_swarm_sim(
        agent_count=args.agents,
        ticks=args.ticks,
        grid_width=args.grid_width,
        grid_height=args.grid_height,
        scenario=args.scenario,
    )
    traces = build_agent_traces(result)
    args.trace_dir.mkdir(parents=True, exist_ok=True)
    trace_summary_shas: dict[str, str] = {}
    for agent_id, trace in sorted(traces.items()):
        summary_sha = verify_trace(trace)
        trace_summary_shas[agent_id] = summary_sha
        (args.trace_dir / f"{agent_id}.json").write_text(trace.to_canonical_json() + "\n", encoding="utf-8")

    replay_report = replay_swarm_traces(traces, obstacles=result.obstacles)
    report = result.report_dict(trace_summary_shas)
    report["replay"] = replay_report.to_dict()
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(canonical_json(report) + "\n", encoding="utf-8")

    print(f"outcome {report['outcome']}")
    print(f"agents {report['agent_count']}")
    print(f"same_cell_collision_count {report['same_cell_collision_count']}")
    print(f"swap_collision_count {report['swap_collision_count']}")
    print(f"obstacle_occupancy_violation_count {report['obstacle_occupancy_violation_count']}")
    print(f"reroute_count {report['reroute_count']}")
    print(f"wrote {args.trace_dir}")
    print(f"wrote {args.report_out}")
    return 0 if report["outcome"] == "GO" else 4


if __name__ == "__main__":
    raise SystemExit(main())
