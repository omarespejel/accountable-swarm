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
    ".codex/START_HERE.md",
    ".codex/HANDOFF.md",
    ".codex/research/README.md",
    ".codex/research/north_star.yml",
    ".codex/research/operating_model.yml",
    ".coderabbit.yaml",
    ".pr_agent.toml",
    ".github/copilot-instructions.md",
    ".github/instructions/accountable-swarm.instructions.md",
    ".github/instructions/trusted-core.instructions.md",
    ".github/pull_request_template.md",
    "DISCLOSURE_LEDGER.md",
    "Dockerfile",
    ".dockerignore",
    "scripts/build_swarm_demo_bundle.py",
    "scripts/run_camera_go_gate.py",
    "scripts/run_swarm_mission_gate.py",
    "scripts/run_swarm_mission_suite.py",
    "scripts/run_swarm_sim.py",
    "scripts/run_swarm_suite.py",
    "scripts/render_swarm_trace_html.py",
    "scripts/verify_swarm_mission_suite.py",
    "scripts/serve_demo.py",
    "docs/engineering/reproducibility.md",
    "docs/engineering/hardening-policy.md",
    "docs/engineering/swarm-demo-bundle-2026-06-15.md",
    "docs/engineering/swarm-demo-server-2026-06-15.md",
    "docs/engineering/swarm-sim-n2-2026-06-15.md",
    "docs/engineering/swarm-obstacle-gate-2026-06-15.md",
    "docs/engineering/swarm-reservation-planner-2026-06-15.md",
    "docs/engineering/swarm-mission-gate-2026-06-15.md",
    "docs/engineering/swarm-mission-suite-2026-06-15.md",
    "docs/engineering/swarm-mission-suite-tamper-2026-06-15.md",
    "docs/engineering/swarm-trace-visualization-2026-06-15.md",
    "docs/engineering/live-dashscope-swarm-mission-2026-06-15.md",
    "docs/engineering/live-dashscope-swarm-mission-suite-2026-06-15.md",
    "docs/engineering/swarm-suite-2026-06-15.md",
    "docs/engineering/swarm-vertical-slalom-2026-06-15.md",
    "docs/engineering/swarm-horizontal-slalom-2026-06-15.md",
    "docs/engineering/swarm-double-chicane-2026-06-15.md",
    "docs/engineering/swarm-larger-boundary-2026-06-15.md",
    "docs/engineering/swarm-scenario-registry-2026-06-15.md",
    "docs/engineering/camera-go-gate-2026-06-15.md",
    "docs/engineering/alibaba-ecs-manual-deploy-2026-06-15.md",
    "docs/engineering/current-status-2026-06-15.md",
    "docs/engineering/webcam-tooling-note-2026-06-15.md",
    "docs/engineering/trace-scalar-policy.md",
    "docs/engineering/review-bot-policy.md",
    "docs/engineering/research-lab-setup-2026-06-14.md",
    "docs/engineering/no-claims.md",
    "docs/security/threat-model.md",
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
