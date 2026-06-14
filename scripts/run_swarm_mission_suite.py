#!/usr/bin/env python3
"""Run mission assignment across reviewed swarm scenarios."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from accountable_swarm.swarm import (
    DEFAULT_MISSION_AGENT_COUNT,
    MISSION_MODEL_FIXTURE_ID,
    SUPPORTED_MISSION_SCENARIOS,
)
from accountable_swarm.trace.models import canonical_json, trace_from_dict, verify_trace


SWARM_MISSION_SUITE_SCHEMA_VERSION = "swarm-mission-suite-report.v2"
MISSION_GATE_SCRIPT = Path("scripts/run_swarm_mission_gate.py")
DEFAULT_DASHSCOPE_MISSION_MODEL = "qwen-plus"
MISSION_GATE_TIMEOUT_SECONDS = 120


def _default_cases_for_mode(*, mode: str, model: str) -> tuple[dict[str, Any], ...]:
    if mode not in {"fixture", "dashscope"}:
        raise ValueError("mission suite mode must be fixture or dashscope")
    suite_model = MISSION_MODEL_FIXTURE_ID if mode == "fixture" else model
    mode_segment = "fixture" if mode == "fixture" else f"dashscope-{_safe_id_segment(suite_model)}"
    return tuple(
        {
            "case_id": f"mission-{scenario}-{mode_segment}-n{DEFAULT_MISSION_AGENT_COUNT}-go",
            "mode": mode,
            "model": suite_model,
            "mission_scenario": scenario,
            "expected_outcome": "GO",
            "purpose": f"{mode} mission binding for reviewed scenario {scenario}",
        }
        for scenario in SUPPORTED_MISSION_SCENARIOS
    )


DEFAULT_CASES = _default_cases_for_mode(
    mode="fixture",
    model=MISSION_MODEL_FIXTURE_ID,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["fixture", "dashscope"], default="fixture")
    parser.add_argument("--model", default=DEFAULT_DASHSCOPE_MISSION_MODEL)
    parser.add_argument("--trace-root", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    suite_model = MISSION_MODEL_FIXTURE_ID if args.mode == "fixture" else args.model
    cases = (
        DEFAULT_CASES
        if args.mode == "fixture"
        else _default_cases_for_mode(mode=args.mode, model=suite_model)
    )
    case_reports = [
        _run_case(case=dict(case), trace_root=args.trace_root, repo_root=repo_root)
        for case in cases
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
        "all_cases_use_requested_mode": all(
            case_report["pass_conditions"]["child_mode_matches_requested"]
            for case_report in case_reports
        ),
        "all_cases_use_requested_model": all(
            case_report["pass_conditions"]["child_model_matches_requested"]
            for case_report in case_reports
        ),
    }
    outcome = "GO" if all(pass_conditions.values()) else "NARROW_CLAIM"
    report = {
        "schema_version": SWARM_MISSION_SUITE_SCHEMA_VERSION,
        "outcome": outcome,
        "mode": args.mode,
        "model": suite_model,
        "case_count": len(case_reports),
        "covered_mission_scenarios": sorted(
            case_report["mission_scenario"] for case_report in case_reports
        ),
        "pass_conditions": pass_conditions,
        "cases": case_reports,
        "non_claims": _non_claims_for_mode(args.mode),
    }
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(canonical_json(report) + "\n", encoding="utf-8")

    print(f"outcome {outcome}")
    print(f"mode {args.mode}")
    print(f"model {suite_model}")
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


def _non_claims_for_mode(mode: str) -> list[str]:
    live_scope_claim = (
        "no live Qwen mission assignment beyond the listed reviewed scenarios"
        if mode == "dashscope"
        else "no live Qwen mission assignment"
    )
    return [
        live_scope_claim,
        "no physical robot behavior",
        "no SO-101 operation",
        "no 3D physics simulation",
        "no latency or reliability claim",
        "no DimOS integration",
        "no arbitrary-map planner claim",
        "no larger-swarm claim beyond the listed deterministic integer-grid cases",
    ]


def _run_case(*, case: dict[str, Any], trace_root: Path, repo_root: Path) -> dict[str, Any]:
    case_id = _safe_case_id(case["case_id"])
    mission_scenario = _safe_case_id(case["mission_scenario"])
    case_dir = trace_root / case_id
    trace_dir = case_dir / "trace"
    case_report_path = case_dir / "mission_gate_report.json"
    case_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            [
                sys.executable,
                str(MISSION_GATE_SCRIPT),
                "--mode",
                case["mode"],
                "--model",
                case["model"],
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
            timeout=MISSION_GATE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return _failed_case_report(
            case=case,
            case_id=case_id,
            returncode=124,
            error_type="mission_gate_timeout",
            error_message="child mission gate command timed out",
        )

    if result.returncode != 0:
        return _failed_case_report(
            case=case,
            case_id=case_id,
            returncode=result.returncode,
            error_type="mission_gate_failed",
            error_message="child mission gate command failed",
        )
    if not case_report_path.exists():
        return _failed_case_report(
            case=case,
            case_id=case_id,
            returncode=result.returncode,
            error_type="mission_report_missing",
            error_message="child mission gate report was not produced",
        )

    try:
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
        child_mode_matches_requested = child_report.get("mode") == case["mode"]
        child_model_matches_requested = child_report.get("model") == case["model"]
        replay_violation_counts_zero = (
            replay_report["same_cell_collision_count"] == 0
            and replay_report["swap_collision_count"] == 0
            and replay_report["obstacle_occupancy_violation_count"] == 0
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return _failed_case_report(
            case=case,
            case_id=case_id,
            returncode=result.returncode,
            error_type="case_artifact_invalid",
            error_message="child mission gate artifact could not be verified",
            error_class=exc.__class__.__name__,
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
        "child_mode_matches_requested": child_mode_matches_requested,
        "child_model_matches_requested": child_model_matches_requested,
    }
    return {
        "case_id": case_id,
        "purpose": case["purpose"],
        "mode": case["mode"],
        "model": case["model"],
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
    error_type: str,
    error_message: str,
    error_class: str | None = None,
) -> dict[str, Any]:
    report = {
        "case_id": case_id,
        "purpose": case["purpose"],
        "mode": case["mode"],
        "model": case.get("model", MISSION_MODEL_FIXTURE_ID),
        "mission_scenario": case["mission_scenario"],
        "expected_outcome": case["expected_outcome"],
        "actual_outcome": "NARROW_CLAIM",
        "mission_gate_returncode": returncode,
        "error_type": error_type,
        "error_message": error_message,
        "pass_conditions": {
            "mission_gate_command_succeeded": False,
            "outcome_matches_expected": False,
            "child_pass_conditions_true": False,
            "mission_trace_replay_deterministic": False,
            "agent_traces_replay_deterministic": False,
            "sim_report_go": False,
            "replay_violation_counts_zero": False,
            "scenario_matches_case": False,
            "child_mode_matches_requested": False,
            "child_model_matches_requested": False,
        },
    }
    if error_class is not None:
        report["error_class"] = error_class
    return report


def _safe_case_id(value: str) -> str:
    if not value or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in value):
        raise ValueError(f"unsafe suite value: {value}")
    return value


def _safe_id_segment(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("suite model must be a non-empty string")
    slug = []
    last_was_dash = False
    for character in value.strip().lower():
        if character in "abcdefghijklmnopqrstuvwxyz0123456789":
            slug.append(character)
            last_was_dash = False
        elif not last_was_dash:
            slug.append("-")
            last_was_dash = True
    result = "".join(slug).strip("-")
    if not result:
        raise ValueError(f"suite model has no safe identifier characters: {value}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
