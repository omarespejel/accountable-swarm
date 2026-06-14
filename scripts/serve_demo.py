#!/usr/bin/env python3
"""Serve the minimal Accountable Swarm backend for manual ECS proof."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from accountable_swarm.server import run_server


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"serving accountable-swarm on http://{args.host}:{args.port}", flush=True)
    run_server(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
