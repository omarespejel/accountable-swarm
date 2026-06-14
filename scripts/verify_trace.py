#!/usr/bin/env python3
"""Verify a DecisionTrace JSON artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from accountable_swarm.trace.models import trace_from_dict, verify_trace


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    args = parser.parse_args()

    value = json.loads(args.trace.read_text(encoding="utf-8"))
    summary = verify_trace(trace_from_dict(value))
    print(f"verified {args.trace}")
    print(f"summary_sha {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
