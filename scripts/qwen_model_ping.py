#!/usr/bin/env python3
"""Ping Qwen/DashScope text models without exposing secrets."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from accountable_swarm.qwen.client import DashScopeQwenClient, DashScopeResponseError, MissingAlibabaApiKey


DEFAULT_MODELS = ("qwen-plus", "qwen3.5-plus")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument("--prompt", default="Return exactly OK.")
    args = parser.parse_args()

    failed = False
    for model in args.models:
        try:
            content = DashScopeQwenClient(model=model).chat_text(prompt=args.prompt, max_tokens=8)
        except MissingAlibabaApiKey as exc:
            print(str(exc), file=sys.stderr)
            return 3
        except (DashScopeResponseError, ValueError) as exc:
            print(f"{model}: FAILED {exc}", file=sys.stderr)
            failed = True
            continue
        if not content.strip():
            print(f"{model}: FAILED empty response", file=sys.stderr)
            failed = True
            continue
        print(f"{model}: OK")
    return 4 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
