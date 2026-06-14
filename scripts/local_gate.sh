#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

git diff --check

python3 - <<'PY'
from pathlib import Path
import sys

required = [
    "README.md",
    "LICENSE",
    "AGENTS.md",
    ".coderabbit.yaml",
    ".pr_agent.toml",
    ".github/pull_request_template.md",
    "DISCLOSURE_LEDGER.md",
    "docs/engineering/review-bot-policy.md",
    "docs/engineering/no-claims.md",
]

missing = [path for path in required if not Path(path).exists()]
if missing:
    print("Missing required files:", ", ".join(missing), file=sys.stderr)
    raise SystemExit(1)
PY

python3 - <<'PY'
from pathlib import Path
import sys

try:
    import tomllib
except ModuleNotFoundError:
    print("tomllib unavailable; skipping .pr_agent.toml parse")
    raise SystemExit(0)

with Path(".pr_agent.toml").open("rb") as f:
    tomllib.load(f)
PY

python3 - <<'PY'
from pathlib import Path

try:
    import yaml  # type: ignore[import-not-found]
except ModuleNotFoundError:
    print("PyYAML unavailable; skipping .coderabbit.yaml parse")
    raise SystemExit(0)

with Path(".coderabbit.yaml").open() as f:
    yaml.safe_load(f)
PY

python3 -m unittest discover -s tests

echo "local gate passed"
