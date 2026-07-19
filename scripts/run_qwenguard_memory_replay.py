#!/usr/bin/env python3
"""Build the privacy-safe QwenGuard memory replay and its receipt report."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile

from accountable_swarm.qwenguard.memory import (
    build_memory_replay_report,
    build_qwenguard_memory_replay,
    parse_memory_evidence_manifest_json,
    parse_memory_fixture_json,
    verify_qwenguard_memory_replay,
)
from accountable_swarm.trace.models import canonical_json, trace_from_dict


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = Path("fixtures/qwenguard_memory/observations.json")
DEFAULT_MANIFEST = Path("fixtures/qwenguard_memory/manifest.json")
DEFAULT_TRACE_OUT = Path("runs/submission/qwenguard-memory/trace.json")
DEFAULT_REPORT_OUT = Path("runs/submission/qwenguard-memory/report.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--trace-out", type=Path, default=DEFAULT_TRACE_OUT)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT_OUT)
    args = parser.parse_args()

    try:
        fixture_path = resolve_repo_path(args.fixture, label="fixture", must_exist=True)
        manifest_path = resolve_repo_path(args.manifest, label="manifest", must_exist=True)
        trace_path = resolve_repo_path(args.trace_out, label="trace output", within_runs=True)
        report_path = resolve_repo_path(args.report_out, label="report output", within_runs=True)
        if len({fixture_path, manifest_path, trace_path, report_path}) != 4:
            raise ValueError("fixture, manifest, trace output, and report output must be different files")
        fixture = parse_memory_fixture_json(fixture_path.read_text(encoding="utf-8"))
        evidence_manifest = parse_memory_evidence_manifest_json(
            manifest_path.read_text(encoding="utf-8"),
            fixture=fixture,
        )
        trace = build_qwenguard_memory_replay(
            run_id="qwenguard-memory-replay-0001",
            memory_id="target-001",
            baseline=fixture.baseline,
            conflict=fixture.conflict,
        )
        report = build_memory_replay_report(
            fixture=fixture,
            evidence_manifest=evidence_manifest,
            trace=trace,
        )
        trace_text = trace.to_canonical_json() + "\n"
        report_text = canonical_json(report) + "\n"
        _write_pair_atomic(
            first_path=trace_path,
            first_text=trace_text,
            second_path=report_path,
            second_text=report_text,
        )
        loaded_trace = trace_from_dict(_load_json_object(trace_path))
        if verify_qwenguard_memory_replay(loaded_trace) != report["trace_summary_sha"]:
            raise ValueError("persisted trace does not match its report")
        if canonical_json(_load_json_object(report_path)) + "\n" != report_text:
            raise ValueError("persisted report is not canonical")
    except (OSError, TypeError, ValueError) as exc:
        print(f"qwenguard memory replay failed: {exc}", file=sys.stderr)
        return 2

    print("outcome GO")
    print(f"trace_summary_sha {report['trace_summary_sha']}")
    print("policy VERIFIED -> PROVISIONAL -> HOLD -> REVERIFY")
    print(f"wrote {trace_path.relative_to(REPO_ROOT)}")
    print(f"wrote {report_path.relative_to(REPO_ROOT)}")
    return 0


def resolve_repo_path(
    path: Path,
    *,
    label: str,
    must_exist: bool = False,
    within_runs: bool = False,
) -> Path:
    if path.is_absolute():
        raise ValueError(f"{label} must be repository-relative")
    root = REPO_ROOT.resolve()
    candidate = root / path
    if _has_symlink_component(candidate, root=root):
        raise ValueError(f"{label} must not use symlinks")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} escapes repository root") from exc
    if within_runs:
        try:
            resolved.relative_to((root / "runs").resolve())
        except ValueError as exc:
            raise ValueError(f"{label} must stay under runs/") from exc
    if resolved.exists() and not resolved.is_file():
        raise ValueError(f"{label} must be a regular file")
    if must_exist and not resolved.is_file():
        raise ValueError(f"{label} does not exist: {path}")
    return resolved


def _has_symlink_component(candidate: Path, *, root: Path) -> bool:
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return False
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _load_json_object(path: Path) -> dict[str, object]:
    import json

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_json_keys)
    if not isinstance(value, dict):
        raise TypeError(f"{path.name} must contain a JSON object")
    return value


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _write_pair_atomic(
    *,
    first_path: Path,
    first_text: str,
    second_path: Path,
    second_text: str,
) -> None:
    first_path.parent.mkdir(parents=True, exist_ok=True)
    second_path.parent.mkdir(parents=True, exist_ok=True)
    temporary: list[tuple[Path, Path]] = []
    try:
        for destination, text in ((first_path, first_text), (second_path, second_text)):
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
                temporary.append((Path(handle.name), destination))
        for source, destination in temporary:
            source.replace(destination)
    finally:
        for source, _destination in temporary:
            source.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
