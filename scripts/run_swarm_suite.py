#!/usr/bin/env python3
"""Run the deterministic swarm scenario suite."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from accountable_swarm.swarm import build_agent_traces, replay_swarm_traces, run_swarm_sim
from accountable_swarm.trace.models import canonical_json, trace_from_dict, verify_trace


SWARM_SUITE_SCHEMA_VERSION = "swarm-suite-report.v1"
DEFAULT_CASES = (
    {
        "case_id": "n2-corridor-go",
        "agent_count": 2,
        "ticks": 8,
        "scenario": "corridor",
        "expected_outcome": "GO",
        "purpose": "baseline two-agent corridor success case",
    },
    {
        "case_id": "n2-center-block-go",
        "agent_count": 2,
        "ticks": 9,
        "scenario": "center-block",
        "expected_outcome": "GO",
        "purpose": "two-agent obstacle replay success case",
    },
    {
        "case_id": "n4-center-block-go",
        "agent_count": 4,
        "ticks": 16,
        "scenario": "center-block",
        "expected_outcome": "GO",
        "purpose": "four-agent reservation-planner success case",
    },
    {
        "case_id": "n4-center-block-short-narrow",
        "agent_count": 4,
        "ticks": 2,
        "scenario": "center-block",
        "expected_outcome": "NARROW_CLAIM",
        "purpose": "overclaim canary for insufficient-budget runs",
    },
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-root", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    args = parser.parse_args()

    case_reports = [
        _run_case(case=dict(case), trace_root=args.trace_root)
        for case in DEFAULT_CASES
    ]
    pass_conditions = {
        "all_case_expectations_matched": all(
            case_report["pass_conditions"]["outcome_matches_expected"]
            for case_report in case_reports
        ),
        "all_agent_traces_replay_deterministic": all(
            case_report["pass_conditions"]["agent_traces_replay_deterministic"]
            for case_report in case_reports
        ),
        "all_replay_counts_match_reports": all(
            case_report["pass_conditions"]["replay_counts_match_report"]
            for case_report in case_reports
        ),
        "all_replay_violation_counts_zero": all(
            case_report["pass_conditions"]["replay_violation_counts_zero"]
            for case_report in case_reports
        ),
        "narrow_canary_present": any(
            case_report["expected_outcome"] == "NARROW_CLAIM"
            and case_report["actual_outcome"] == "NARROW_CLAIM"
            for case_report in case_reports
        ),
    }
    outcome = "GO" if all(pass_conditions.values()) else "NARROW_CLAIM"
    report = {
        "schema_version": SWARM_SUITE_SCHEMA_VERSION,
        "outcome": outcome,
        "case_count": len(case_reports),
        "pass_conditions": pass_conditions,
        "cases": case_reports,
        "non_claims": [
            "no physical robot behavior",
            "no SO-101 operation",
            "no 3D physics simulation",
            "no live Qwen mission assignment",
            "no latency or reliability claim",
            "no DimOS integration",
            "no arbitrary-map planner claim",
            "no larger-swarm claim beyond the listed deterministic integer-grid cases",
        ],
    }
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(canonical_json(report) + "\n", encoding="utf-8")

    print(f"outcome {outcome}")
    print(f"case_count {len(case_reports)}")
    for case_report in case_reports:
        print(
            "case "
            f"{case_report['case_id']} "
            f"expected {case_report['expected_outcome']} "
            f"actual {case_report['actual_outcome']}"
        )
    print(f"wrote {args.trace_root}")
    print(f"wrote {args.report_out}")
    return 0 if outcome == "GO" else 4


def _run_case(*, case: dict[str, Any], trace_root: Path) -> dict[str, Any]:
    case_id = _safe_case_id(case["case_id"])
    result = run_swarm_sim(
        agent_count=case["agent_count"],
        ticks=case["ticks"],
        scenario=case["scenario"],
        run_id=f"swarm-suite-{case_id}",
    )
    traces = build_agent_traces(result)

    case_trace_dir = trace_root / case_id
    case_trace_dir.mkdir(parents=True, exist_ok=True)
    loaded_traces = {}
    in_memory_summary_shas = {
        agent_id: verify_trace(trace)
        for agent_id, trace in sorted(traces.items())
    }
    for agent_id, trace in sorted(traces.items()):
        trace_path = case_trace_dir / f"{agent_id}.json"
        trace_path.write_text(trace.to_canonical_json() + "\n", encoding="utf-8")
        loaded_trace = trace_from_dict(json.loads(trace_path.read_text(encoding="utf-8")))
        loaded_traces[agent_id] = loaded_trace

    trace_summary_shas = {
        agent_id: verify_trace(trace)
        for agent_id, trace in sorted(loaded_traces.items())
    }
    replay = replay_swarm_traces(loaded_traces, obstacles=result.obstacles)
    sim_report = result.report_dict(trace_summary_shas)
    sim_report["replay"] = replay.to_dict()

    replay_counts_match_report = (
        replay.same_cell_collision_count == sim_report["same_cell_collision_count"]
        and replay.swap_collision_count == sim_report["swap_collision_count"]
        and replay.obstacle_occupancy_violation_count
        == sim_report["obstacle_occupancy_violation_count"]
    )
    replay_violation_counts_zero = (
        replay.same_cell_collision_count == 0
        and replay.swap_collision_count == 0
        and replay.obstacle_occupancy_violation_count == 0
    )
    agent_traces_replay_deterministic = trace_summary_shas == in_memory_summary_shas
    actual_outcome = sim_report["outcome"]
    expected_outcome = case["expected_outcome"]
    pass_conditions = {
        "outcome_matches_expected": actual_outcome == expected_outcome,
        "agent_traces_replay_deterministic": agent_traces_replay_deterministic,
        "replay_counts_match_report": replay_counts_match_report,
        "replay_violation_counts_zero": replay_violation_counts_zero,
    }
    return {
        "case_id": case_id,
        "purpose": case["purpose"],
        "scenario": case["scenario"],
        "agent_count": case["agent_count"],
        "ticks": case["ticks"],
        "expected_outcome": expected_outcome,
        "actual_outcome": actual_outcome,
        "trace_dir": str(case_trace_dir),
        "trace_summary_shas": trace_summary_shas,
        "pass_conditions": pass_conditions,
        "sim_report": sim_report,
    }


def _safe_case_id(value: str) -> str:
    if not value or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in value):
        raise ValueError(f"unsafe suite case_id: {value}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
