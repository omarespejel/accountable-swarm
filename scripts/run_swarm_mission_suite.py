#!/usr/bin/env python3
"""Run fixture mission assignment across reviewed swarm scenarios."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from accountable_swarm.swarm import DEFAULT_MISSION_AGENT_COUNT, SUPPORTED_MISSION_SCENARIOS
from accountable_swarm.trace.models import canonical_json, trace_from_dict, verify_trace


SWARM_MISSION_SUITE_SCHEMA_VERSION = "swarm-mission-suite-report.v1"
MISSION_GATE_SCRIPT = Path("scripts/run_swarm_mission_gate.py")
DEFAULT_CASES = tuple(
    {
        "case_id": f"mission-{scenario}-fixture-n{DEFAULT_MISSION_AGENT_COUNT}-go",
        "mode": "fixture",
        "mission_scenario": scenario,
        "expected_outcome": "GO",
        "purpose": f"fixture mission binding for reviewed scenario {scenario}",
    }
    for scenario in SUPPORTED_MISSION_SCENARIOS
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-root", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    case_reports = [
        _run_case(case=dict(case), trace_root=args.trace_root, repo_root=repo_root)
        for case in DEFAULT_CASES
    ]
    pass_conditions = {
        "all_case_expectations_matched": all(
            case_report["pass_conditions"]["outcome_matches_expected"]
            for case_report in case_reports
        ),
        "all_mission_gate_commands_succeeded": all(
            case_report["pass_conditions"]["mission_gate_command_succeeded"]
            for case_report in case_reports
        ),
        "all_mission_traces_replay_deterministic": all(
            case_report["pass_conditions"]["mission_trace_replay_deterministic"]
            for case_report in case_reports
        ),
        "all_agent_traces_replay_deterministic": all(
            case_report["pass_conditions"]["agent_traces_replay_deterministic"]
            for case_report in case_reports
        ),
        "all_sim_reports_go": all(
            case_report["pass_conditions"]["sim_report_go"]
            for case_report in case_reports
        ),
        "all_replay_violation_counts_zero": all(
            case_report["pass_conditions"]["replay_violation_counts_zero"]
            for case_report in case_reports
        ),
        "all_reviewed_scenarios_covered": {
            case_report["mission_scenario"] for case_report in case_reports
        }
        == set(SUPPORTED_MISSION_SCENARIOS),
    }
    outcome = "GO" if all(pass_conditions.values()) else "NARROW_CLAIM"
    report = {
        "schema_version": SWARM_MISSION_SUITE_SCHEMA_VERSION,
        "outcome": outcome,
        "case_count": len(case_reports),
        "covered_mission_scenarios": sorted(
            case_report["mission_scenario"] for case_report in case_reports
        ),
        "pass_conditions": pass_conditions,
        "cases": case_reports,
        "non_claims": [
            "no live Qwen mission assignment",
            "no physical robot behavior",
            "no SO-101 operation",
            "no 3D physics simulation",
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
            f"scenario {case_report['mission_scenario']} "
            f"expected {case_report['expected_outcome']} "
            f"actual {case_report['actual_outcome']}"
        )
    print(f"wrote {args.trace_root}")
    print(f"wrote {args.report_out}")
    return 0 if outcome == "GO" else 4


def _run_case(*, case: dict[str, Any], trace_root: Path, repo_root: Path) -> dict[str, Any]:
    case_id = _safe_case_id(case["case_id"])
    mission_scenario = _safe_case_id(case["mission_scenario"])
    case_dir = trace_root / case_id
    trace_dir = case_dir / "trace"
    case_report_path = case_dir / "mission_gate_report.json"
    case_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            sys.executable,
            str(MISSION_GATE_SCRIPT),
            "--mode",
            case["mode"],
            "--mission-scenario",
            mission_scenario,
            "--trace-dir",
            str(trace_dir),
            "--report-out",
            str(case_report_path),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0 or not case_report_path.exists():
        return _failed_case_report(
            case=case,
            case_id=case_id,
            returncode=result.returncode,
            stderr=result.stderr,
            stdout=result.stdout,
        )

    child_report = json.loads(case_report_path.read_text(encoding="utf-8"))
    expected_outcome = case["expected_outcome"]
    actual_outcome = child_report["outcome"]
    trace_files = _verify_case_traces(
        case_id=case_id,
        trace_dir=trace_dir,
        child_report=child_report,
    )
    child_conditions = child_report["pass_conditions"]
    replay_report = child_report["sim_report"]["replay"]
    replay_violation_counts_zero = (
        replay_report["same_cell_collision_count"] == 0
        and replay_report["swap_collision_count"] == 0
        and replay_report["obstacle_occupancy_violation_count"] == 0
    )
    pass_conditions = {
        "mission_gate_command_succeeded": result.returncode == 0,
        "outcome_matches_expected": actual_outcome == expected_outcome,
        "child_pass_conditions_true": all(child_conditions.values()),
        "mission_trace_replay_deterministic": trace_files["mission_summary_sha"]
        == child_report["mission_trace_summary_sha"],
        "agent_traces_replay_deterministic": trace_files["agent_summary_shas"]
        == child_report["trace_summary_shas"],
        "sim_report_go": child_report["sim_report"]["outcome"] == "GO",
        "replay_violation_counts_zero": replay_violation_counts_zero,
        "scenario_matches_case": child_report["mission"]["scenario"] == mission_scenario,
    }
    return {
        "case_id": case_id,
        "purpose": case["purpose"],
        "mode": case["mode"],
        "mission_scenario": mission_scenario,
        "expected_outcome": expected_outcome,
        "actual_outcome": actual_outcome,
        "mission_id": child_report["mission"]["mission_id"],
        "mission_report_file": f"{case_id}/mission_gate_report.json",
        "trace_files": trace_files["relative_files"],
        "mission_trace_summary_sha": child_report["mission_trace_summary_sha"],
        "trace_summary_shas": child_report["trace_summary_shas"],
        "pass_conditions": pass_conditions,
        "mission_gate_report": child_report,
    }


def _verify_case_traces(
    *,
    case_id: str,
    trace_dir: Path,
    child_report: dict[str, Any],
) -> dict[str, Any]:
    mission_trace = trace_from_dict(json.loads((trace_dir / "mission.json").read_text(encoding="utf-8")))
    mission_summary_sha = verify_trace(mission_trace)
    agent_summary_shas = {}
    relative_agent_files = {}
    for agent_id in sorted(child_report["trace_summary_shas"]):
        trace_path = trace_dir / "agents" / f"{agent_id}.json"
        agent_trace = trace_from_dict(json.loads(trace_path.read_text(encoding="utf-8")))
        agent_summary_shas[agent_id] = verify_trace(agent_trace)
        relative_agent_files[agent_id] = f"{case_id}/trace/agents/{agent_id}.json"
    return {
        "mission_summary_sha": mission_summary_sha,
        "agent_summary_shas": agent_summary_shas,
        "relative_files": {
            "mission": f"{case_id}/trace/mission.json",
            "agents": relative_agent_files,
        },
    }


def _failed_case_report(
    *,
    case: dict[str, Any],
    case_id: str,
    returncode: int,
    stderr: str,
    stdout: str,
) -> dict[str, Any]:
    stderr_excerpt = stderr.strip().splitlines()[:3]
    stdout_excerpt = stdout.strip().splitlines()[:3]
    return {
        "case_id": case_id,
        "purpose": case["purpose"],
        "mode": case["mode"],
        "mission_scenario": case["mission_scenario"],
        "expected_outcome": case["expected_outcome"],
        "actual_outcome": "NARROW_CLAIM",
        "mission_gate_returncode": returncode,
        "stdout_excerpt": stdout_excerpt,
        "stderr_excerpt": stderr_excerpt,
        "pass_conditions": {
            "mission_gate_command_succeeded": False,
            "outcome_matches_expected": False,
            "child_pass_conditions_true": False,
            "mission_trace_replay_deterministic": False,
            "agent_traces_replay_deterministic": False,
            "sim_report_go": False,
            "replay_violation_counts_zero": False,
            "scenario_matches_case": False,
        },
    }


def _safe_case_id(value: str) -> str:
    if not value or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in value):
        raise ValueError(f"unsafe suite value: {value}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
