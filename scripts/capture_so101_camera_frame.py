#!/usr/bin/env python3
"""Capture one trace-only SO-101 camera frame or emit a controlled NO_GO report."""

from __future__ import annotations

import argparse
from pathlib import Path
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
        "output_path": args.out.name,
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
            capture = capture_frame(spec, args.out)
        except RuntimeError as exc:
            report["detail"] = str(exc)
        else:
            report["outcome"] = "GO"
            report["pass_conditions"]["frame_captured"] = True
            report["capture"] = capture

    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(canonical_json(report) + "\n", encoding="utf-8")
    print(f"outcome {report['outcome']}")
    print(f"report {args.report_out}")
    if report["outcome"] == "GO":
        print(f"frame {args.out}")
        return 0
    print(report["detail"], file=sys.stderr)
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
