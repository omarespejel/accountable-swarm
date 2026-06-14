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
EXPECTED_MISSION_SUITE_SCHEMA_VERSION = "swarm-mission-suite-report.v2"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    args = parser.parse_args()

    suite_report = {}
    suite_report_loaded = False
    suite_report_valid = False
    suite_schema_version_valid = False
    suite_cases_valid = False
    top_level_error = None
    try:
        loaded = json.loads(args.report.read_text(encoding="utf-8"))
        suite_report_loaded = True
        if not isinstance(loaded, dict):
            top_level_error = ("suite_report_invalid", "suite report must be a JSON object", None)
        else:
            suite_report = loaded
            suite_report_valid = True
            if suite_report.get("schema_version") != EXPECTED_MISSION_SUITE_SCHEMA_VERSION:
                top_level_error = (
                    "suite_schema_version_mismatch",
                    "suite report schema_version is unsupported",
                    None,
                )
            else:
                suite_schema_version_valid = True
            if suite_schema_version_valid and not isinstance(suite_report.get("cases"), list):
                top_level_error = ("suite_cases_invalid", "suite report cases must be a list", None)
            elif suite_schema_version_valid:
                suite_cases_valid = True
    except (OSError, json.JSONDecodeError) as exc:
        top_level_error = (
            "suite_report_unreadable",
            "suite report could not be read as JSON",
            exc.__class__.__name__,
        )

    case_results = []
    if suite_report_valid and suite_schema_version_valid and suite_cases_valid:
        case_results = [
            _verify_case(case=case, trace_root=args.trace_root)
            for case in suite_report.get("cases", [])
        ]
    pass_conditions = {
        "suite_report_loaded": suite_report_loaded,
        "suite_report_valid": suite_report_valid,
        "suite_schema_version_valid": suite_schema_version_valid,
        "suite_cases_valid": suite_cases_valid,
        "suite_report_outcome_go": suite_report.get("outcome") == "GO",
        "all_case_trace_paths_relative": all(
            case_result["pass_conditions"]["trace_paths_relative"]
            for case_result in case_results
        ),
        "all_case_trace_paths_confined": all(
            case_result["pass_conditions"]["trace_paths_confined"]
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
            _live_qwen_non_claim(suite_report.get("mode")),
            "no physical robot behavior",
            "no SO-101 operation",
            "no 3D physics simulation",
            "no latency or reliability claim",
            "no DimOS integration",
            "no cryptographic authenticity beyond local hash-chain verification",
            "no adversarial file-system compromise model beyond persisted artifact mutation",
        ],
    }
    if top_level_error is not None:
        error_type, error_message, error_class = top_level_error
        report["error_type"] = error_type
        report["error_message"] = error_message
        if error_class is not None:
            report["error_class"] = error_class
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


def _live_qwen_non_claim(mode: Any) -> str:
    if mode == "dashscope":
        return "no live Qwen mission assignment beyond the verified suite report"
    return "no live Qwen mission assignment"


def _verify_case(*, case: dict[str, Any], trace_root: Path) -> dict[str, Any]:
    if not isinstance(case, dict):
        return _failed_case(
            case={},
            error_type="case_invalid",
            error_message="suite case must be a JSON object",
        )
    try:
        case_id = _expect_str(case.get("case_id"), "case_id")
        actual_outcome = _expect_str(case.get("actual_outcome"), "actual_outcome")
    except (TypeError, ValueError) as exc:
        return _failed_case(
            case=case,
            error_type="case_invalid",
            error_message="suite case identity fields are invalid",
            error_class=exc.__class__.__name__,
        )
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
        mission_path = _confined_trace_path(trace_root=trace_root, relative_path=mission_relative)
        agent_confined_paths = {
            agent_id: _confined_trace_path(trace_root=trace_root, relative_path=relative_path)
            for agent_id, relative_path in sorted(agent_paths.items())
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
        mission_summary_sha = _verify_trace_file(mission_path)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        mission_summary_sha = ""
        mission_error = exc.__class__.__name__

    agent_summary_shas = {}
    agent_errors = {}
    for agent_id, path in sorted(agent_confined_paths.items()):
        try:
            agent_summary_shas[agent_id] = _verify_trace_file(path)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            agent_errors[agent_id] = exc.__class__.__name__

    mission_matches = mission_error is None and mission_summary_sha == expected_mission_sha
    agent_matches = not agent_errors and agent_summary_shas == expected_agent_shas
    pass_conditions = {
        "trace_paths_relative": True,
        "trace_paths_confined": True,
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
    elif not mission_matches or not agent_matches:
        result["error_type"] = "trace_summary_sha_mismatch"
        result["error_message"] = "verified trace summary did not match suite report"
        result["failed_trace_kinds"] = _mismatched_trace_kinds(
            mission_matches=mission_matches,
            agent_summary_shas=agent_summary_shas,
            expected_agent_shas=expected_agent_shas,
        )
        result["error_classes"] = []
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
            "trace_paths_confined": False,
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


def _mismatched_trace_kinds(
    *,
    mission_matches: bool,
    agent_summary_shas: dict[str, str],
    expected_agent_shas: dict[str, Any],
) -> list[str]:
    kinds = []
    if not mission_matches:
        kinds.append("mission")
    for agent_id in sorted(set(agent_summary_shas) | set(expected_agent_shas)):
        if agent_summary_shas.get(agent_id) != expected_agent_shas.get(agent_id):
            kinds.append(f"agent:{agent_id}")
    return kinds


def _safe_relative_path(value: str) -> Path:
    path = PurePosixPath(value)
    if path.is_absolute() or "\\" in value:
        raise ValueError("trace path must be relative")
    if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("trace path contains unsafe component")
    return Path(*path.parts)


def _confined_trace_path(*, trace_root: Path, relative_path: Path) -> Path:
    root = trace_root.resolve(strict=False)
    candidate = (root / relative_path).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("trace path escapes trace root") from exc
    return candidate


def _expect_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
