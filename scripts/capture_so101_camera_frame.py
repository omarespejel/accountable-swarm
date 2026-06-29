#!/usr/bin/env python3
"""Capture one trace-only SO-101 camera frame or emit a controlled NO_GO report."""

from __future__ import annotations

import argparse
from pathlib import Path
from pathlib import PurePosixPath
import sys

from accountable_swarm.physical.so101 import SO101CameraSpec, capture_frame, dependency_status, parse_index_or_path
from accountable_swarm.trace.models import canonical_json


REPORT_SCHEMA_VERSION = "so101-camera-capture-report.v1"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera-name", default="so101_overhead")
    parser.add_argument("--index-or-path", default="0")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--rotation", type=int, default=0)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    args = parser.parse_args()

    try:
        repo_root = _find_repo_root(Path.cwd())
        out_path = _repo_path(repo_root, args.out)
        report_path = _repo_path(repo_root, args.report_out)
    except ValueError as exc:
        print(f"SO-101 camera capture failed: {exc}", file=sys.stderr)
        return 2
    if out_path.parent != report_path.parent:
        print(
            "SO-101 camera capture failed: frame and report artifacts must be written to the same directory",
            file=sys.stderr,
        )
        return 2

    spec = SO101CameraSpec(
        camera_name=args.camera_name,
        index_or_path=parse_index_or_path(args.index_or_path),
        width=args.width,
        height=args.height,
        fps=args.fps,
        rotation=args.rotation,
    )

    deps_ok, deps_detail = dependency_status()
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "outcome": "NO_GO",
        "camera_name": spec.camera_name,
        "index_or_path": spec.index_or_path,
        "output_path": out_path.name,
        "pass_conditions": {
            "dependencies_available": deps_ok,
            "frame_captured": False,
            "trace_only_motion_boundary_preserved": True,
        },
        "non_claims": [
            "no autonomous SO-101 motion",
            "no ACT policy success",
            "no safety claim",
            "no latency or reliability claim",
            "no physical swarm claim",
        ],
        "detail": deps_detail,
    }

    if deps_ok:
        try:
            capture = capture_frame(spec, out_path)
        except RuntimeError as exc:
            report["detail"] = str(exc)
        else:
            report["outcome"] = "GO"
            report["pass_conditions"]["frame_captured"] = True
            report["capture"] = capture

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(canonical_json(report) + "\n", encoding="utf-8")
    print(f"outcome {report['outcome']}")
    print(f"report {_display_path(repo_root, report_path)}")
    if report["outcome"] == "GO":
        print(f"frame {_display_path(repo_root, out_path)}")
        return 0
    print(report["detail"], file=sys.stderr)
    return 4


def _find_repo_root(start: Path) -> Path:
    for candidate in [start.resolve(), *start.resolve().parents]:
        if (candidate / "pyproject.toml").is_file() and (candidate / "accountable_swarm").is_dir():
            return candidate
    raise ValueError("could not locate repository root")


def _repo_path(repo_root: Path, raw_path: Path) -> Path:
    if raw_path.is_absolute():
        raise ValueError("artifact paths must be repo-relative")
    if ".." in raw_path.parts:
        raise ValueError("artifact paths must stay inside the repository checkout")
    resolved = (repo_root / raw_path).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError("artifact paths must stay inside the repository checkout") from exc
    if resolved.is_dir():
        raise ValueError("artifact paths must name files, not existing directories")
    return resolved


def _display_path(repo_root: Path, path: Path) -> str:
    return PurePosixPath(path.resolve().relative_to(repo_root.resolve()).as_posix()).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
