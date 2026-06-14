#!/usr/bin/env python3
"""Verify persisted traces referenced by a swarm mission-suite report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from accountable_swarm.trace.models import canonical_json, trace_from_dict, verify_trace


MISSION_SUITE_VERIFY_SCHEMA_VERSION = "swarm-mission-suite-verify-report.v1"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    args = parser.parse_args()

    suite_report = json.loads(args.report.read_text(encoding="utf-8"))
    case_results = [
        _verify_case(case=case, trace_root=args.trace_root)
        for case in suite_report.get("cases", [])
    ]
    pass_conditions = {
        "suite_report_loaded": isinstance(suite_report, dict),
        "suite_report_outcome_go": suite_report.get("outcome") == "GO",
        "all_case_trace_paths_relative": all(
            case_result["pass_conditions"]["trace_paths_relative"]
            for case_result in case_results
        ),
        "all_mission_trace_shas_match": all(
            case_result["pass_conditions"]["mission_trace_sha_matches_report"]
            for case_result in case_results
        ),
        "all_agent_trace_shas_match": all(
            case_result["pass_conditions"]["agent_trace_shas_match_report"]
            for case_result in case_results
        ),
        "all_cases_verified": all(
            case_result["pass_conditions"]["case_verified"]
            for case_result in case_results
        ),
        "case_count_nonzero": bool(case_results),
        "case_count_matches_suite_report": len(case_results) == suite_report.get("case_count"),
    }
    outcome = "GO" if all(pass_conditions.values()) else "NARROW_CLAIM"
    report = {
        "schema_version": MISSION_SUITE_VERIFY_SCHEMA_VERSION,
        "outcome": outcome,
        "suite_schema_version": suite_report.get("schema_version"),
        "suite_outcome": suite_report.get("outcome"),
        "case_count": len(case_results),
        "pass_conditions": pass_conditions,
        "cases": case_results,
        "non_claims": [
            "no live Qwen mission assignment",
            "no physical robot behavior",
            "no SO-101 operation",
            "no 3D physics simulation",
            "no latency or reliability claim",
            "no DimOS integration",
            "no cryptographic authenticity beyond local hash-chain verification",
            "no adversarial file-system compromise model beyond persisted artifact mutation",
        ],
    }
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(canonical_json(report) + "\n", encoding="utf-8")

    print(f"outcome {outcome}")
    print(f"case_count {len(case_results)}")
    for case_result in case_results:
        print(
            "case "
            f"{case_result['case_id']} "
            f"actual {case_result['actual_outcome']} "
            f"verified {case_result['pass_conditions']['case_verified']}"
        )
    print(f"wrote {args.report_out}")
    return 0 if outcome == "GO" else 4


def _verify_case(*, case: dict[str, Any], trace_root: Path) -> dict[str, Any]:
    case_id = _expect_str(case.get("case_id"), "case_id")
    actual_outcome = _expect_str(case.get("actual_outcome"), "actual_outcome")
    trace_files = case.get("trace_files")
    if not isinstance(trace_files, dict):
        return _failed_case(
            case=case,
            error_type="case_trace_files_invalid",
            error_message="case trace_files must be an object",
        )
    try:
        mission_relative = _safe_relative_path(_expect_str(trace_files.get("mission"), "mission trace path"))
        agent_files = trace_files.get("agents")
        if not isinstance(agent_files, dict):
            raise ValueError("agent trace files must be an object")
        expected_mission_sha = _expect_str(
            case.get("mission_trace_summary_sha"),
            "mission_trace_summary_sha",
        )
        expected_agent_shas = case.get("trace_summary_shas")
        if not isinstance(expected_agent_shas, dict):
            raise ValueError("trace_summary_shas must be an object")
        agent_paths = {
            agent_id: _safe_relative_path(_expect_str(agent_files[agent_id], "agent trace path"))
            for agent_id in sorted(agent_files)
        }
    except (TypeError, ValueError) as exc:
        return _failed_case(
            case=case,
            error_type="trace_path_invalid",
            error_message="referenced trace path was not a safe relative path",
            error_class=exc.__class__.__name__,
        )

    mission_error = None
    try:
        mission_summary_sha = _verify_trace_file(trace_root / mission_relative)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        mission_summary_sha = ""
        mission_error = exc.__class__.__name__

    agent_summary_shas = {}
    agent_errors = {}
    for agent_id, relative_path in sorted(agent_paths.items()):
        try:
            agent_summary_shas[agent_id] = _verify_trace_file(trace_root / relative_path)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            agent_errors[agent_id] = exc.__class__.__name__

    mission_matches = mission_error is None and mission_summary_sha == expected_mission_sha
    agent_matches = not agent_errors and agent_summary_shas == expected_agent_shas
    pass_conditions = {
        "trace_paths_relative": True,
        "mission_trace_sha_matches_report": mission_matches,
        "agent_trace_shas_match_report": agent_matches,
        "case_verified": actual_outcome == "GO" and mission_matches and agent_matches,
    }
    result = {
        "case_id": case_id,
        "actual_outcome": actual_outcome,
        "mission_trace_summary_sha": mission_summary_sha,
        "trace_summary_shas": agent_summary_shas,
        "pass_conditions": pass_conditions,
    }
    if mission_error is not None or agent_errors:
        result["error_type"] = "trace_artifact_invalid"
        result["error_message"] = "referenced trace artifact could not be verified"
        result["failed_trace_kinds"] = _failed_trace_kinds(
            mission_failed=mission_error is not None,
            agent_errors=agent_errors,
        )
        result["error_classes"] = sorted(
            {
                error_class
                for error_class in [mission_error, *agent_errors.values()]
                if error_class is not None
            }
        )
    return result


def _verify_trace_file(path: Path) -> str:
    value = json.loads(path.read_text(encoding="utf-8"))
    return verify_trace(trace_from_dict(value))


def _failed_case(
    *,
    case: dict[str, Any],
    error_type: str,
    error_message: str,
    error_class: str | None = None,
) -> dict[str, Any]:
    case_id = case.get("case_id", "unknown")
    actual_outcome = case.get("actual_outcome", "NARROW_CLAIM")
    report = {
        "case_id": case_id if isinstance(case_id, str) else "unknown",
        "actual_outcome": actual_outcome if isinstance(actual_outcome, str) else "NARROW_CLAIM",
        "error_type": error_type,
        "error_message": error_message,
        "pass_conditions": {
            "trace_paths_relative": False,
            "mission_trace_sha_matches_report": False,
            "agent_trace_shas_match_report": False,
            "case_verified": False,
        },
    }
    if error_class is not None:
        report["error_class"] = error_class
    return report


def _failed_trace_kinds(*, mission_failed: bool, agent_errors: dict[str, str]) -> list[str]:
    kinds = []
    if mission_failed:
        kinds.append("mission")
    for agent_id in sorted(agent_errors):
        kinds.append(f"agent:{agent_id}")
    return kinds


def _safe_relative_path(value: str) -> Path:
    path = PurePosixPath(value)
    if path.is_absolute() or "\\" in value:
        raise ValueError("trace path must be relative")
    if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("trace path contains unsafe component")
    return Path(*path.parts)


def _expect_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
