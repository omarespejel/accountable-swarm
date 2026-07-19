#!/usr/bin/env python3
"""Rebuild and verify a persisted QwenGuard memory replay from its fixture."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from accountable_swarm.qwenguard.memory import (
    MEMORY_REPLAY_MEMORY_ID,
    MEMORY_REPLAY_RUN_ID,
    build_memory_replay_report,
    build_qwenguard_memory_replay,
    parse_memory_evidence_manifest_json,
    parse_memory_fixture_json,
    verify_qwenguard_memory_replay,
)
from accountable_swarm.trace.models import canonical_json, trace_from_dict
from scripts.run_qwenguard_memory_replay import (
    DEFAULT_FIXTURE,
    DEFAULT_MANIFEST,
    DEFAULT_REPORT_OUT,
    DEFAULT_TRACE_OUT,
    _load_json_object,
    resolve_repo_path,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--trace", type=Path, default=DEFAULT_TRACE_OUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_OUT)
    args = parser.parse_args()

    try:
        fixture_path = resolve_repo_path(args.fixture, label="fixture", must_exist=True)
        manifest_path = resolve_repo_path(args.manifest, label="manifest", must_exist=True)
        trace_path = resolve_repo_path(args.trace, label="trace", must_exist=True, within_runs=True)
        report_path = resolve_repo_path(args.report, label="report", must_exist=True, within_runs=True)
        if len({fixture_path, manifest_path, trace_path, report_path}) != 4:
            raise ValueError("fixture, manifest, trace, and report must be different files")
        fixture = parse_memory_fixture_json(fixture_path.read_text(encoding="utf-8"))
        evidence_manifest = parse_memory_evidence_manifest_json(
            manifest_path.read_text(encoding="utf-8"),
            fixture=fixture,
        )
        trace_value = _load_json_object(trace_path)
        report_value = _load_json_object(report_path)
        trace = trace_from_dict(trace_value)
        summary_sha = verify_qwenguard_memory_replay(trace)
        expected_trace = build_qwenguard_memory_replay(
            run_id=MEMORY_REPLAY_RUN_ID,
            memory_id=MEMORY_REPLAY_MEMORY_ID,
            baseline=fixture.baseline,
            conflict=fixture.conflict,
        )
        expected_report = build_memory_replay_report(
            fixture=fixture,
            evidence_manifest=evidence_manifest,
            trace=expected_trace,
        )
        if canonical_json(trace_value) != expected_trace.to_canonical_json():
            raise ValueError("trace does not match the checked fixture replay")
        if canonical_json(report_value) != canonical_json(expected_report):
            raise ValueError("report does not match the checked fixture replay")
        if report_value.get("trace_summary_sha") != summary_sha:
            raise ValueError("report summary does not match the verified trace")
    except (KeyError, OSError, TypeError, ValueError) as exc:
        print(f"qwenguard memory verification failed: {exc}", file=sys.stderr)
        return 2

    print(f"verified {trace_path.name} and {report_path.name}")
    print(f"trace_summary_sha {summary_sha}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
