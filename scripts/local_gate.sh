#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
gate_commit="$(git rev-parse HEAD)"
gate_tmp="$(mktemp -d /tmp/accountable-swarm-local-gate.XXXXXX)"
cleanup() {
    rm -rf "$gate_tmp"
}
trap cleanup EXIT

git diff --check

python3 - <<'PY'
from pathlib import Path
import sys

required = [
    "README.md",
    "LICENSE",
    "pyproject.toml",
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
    "scripts/prepare_sensor_frame_proof_pack.py",
    "scripts/capture_so101_camera_frame.py",
    "scripts/prepare_so101_operator_probe_pack.py",
    "scripts/record_qwenguard_trial.py",
    "scripts/run_qwenguard_memory_replay.py",
    "scripts/verify_qwenguard_memory_replay.py",
    "scripts/run_hazard_formation_gate.py",
    "scripts/run_swarm_mission_gate.py",
    "scripts/run_swarm_mission_suite.py",
    "scripts/run_swarm_sim.py",
    "scripts/run_swarm_suite.py",
    "scripts/render_swarm_trace_html.py",
    "scripts/prepare_demo_recording_pack.py",
    "scripts/prepare_ecs_operator_pack.py",
    "scripts/prepare_ecs_proof_review.py",
    "scripts/prepare_dimos_bridge_pack.py",
    "scripts/run_dimos_replay_consumer.py",
    "scripts/verify_swarm_mission_suite.py",
    "scripts/serve_demo.py",
    "docs/engineering/reproducibility.md",
    "docs/engineering/hardening-policy.md",
    "docs/engineering/go-gate-p1-hardening-2026-06-15.md",
    "docs/engineering/go-gate-p2-packaging-2026-06-15.md",
    "docs/engineering/go-gate-p3-confidence-bbox-2026-06-16.md",
    "docs/engineering/alibaba-proof-2026-06-14.md",
    "docs/engineering/ecs-smoke-proof-collector-2026-06-15.md",
    "docs/engineering/swarm-demo-bundle-2026-06-15.md",
    "docs/engineering/swarm-demo-server-2026-06-15.md",
    "docs/engineering/swarm-sim-n2-2026-06-15.md",
    "docs/engineering/swarm-obstacle-gate-2026-06-15.md",
    "docs/engineering/swarm-reservation-planner-2026-06-15.md",
    "docs/engineering/swarm-mission-gate-2026-06-15.md",
    "docs/engineering/swarm-mission-objective-hardening-2026-06-15.md",
    "docs/engineering/swarm-mission-suite-2026-06-15.md",
    "docs/engineering/swarm-mission-suite-tamper-2026-06-15.md",
    "docs/engineering/swarm-trace-visualization-2026-06-15.md",
    "docs/engineering/animated-swarm-replay-2026-06-16.md",
    "docs/engineering/demo-recording-pack-2026-06-16.md",
    "docs/engineering/ecs-operator-proof-pack-2026-06-16.md",
    "docs/engineering/ecs-proof-review-helper-2026-06-29.md",
    "docs/engineering/dimos-bridge-probe-2026-06-16.md",
    "docs/engineering/dimos-replay-consumer-2026-06-16.md",
    "docs/engineering/live-dashscope-hazard-formation-2026-06-16.md",
    "docs/engineering/live-dashscope-swarm-mission-2026-06-15.md",
    "docs/engineering/live-dashscope-swarm-mission-suite-2026-06-15.md",
    "docs/engineering/live-dashscope-swarm-mission-suite-post-hardening-2026-06-15.md",
    "docs/engineering/swarm-suite-2026-06-15.md",
    "docs/engineering/swarm-vertical-slalom-2026-06-15.md",
    "docs/engineering/swarm-horizontal-slalom-2026-06-15.md",
    "docs/engineering/swarm-double-chicane-2026-06-15.md",
    "docs/engineering/swarm-larger-boundary-2026-06-15.md",
    "docs/engineering/swarm-scenario-registry-2026-06-15.md",
    "docs/engineering/camera-go-gate-2026-06-15.md",
    "docs/engineering/sensor-frame-proof-pack-2026-06-17.md",
    "docs/engineering/so101-trace-only-sensor-frame-adapter-2026-06-17.md",
    "docs/engineering/so101-operator-probe-pack-2026-06-17.md",
    "docs/engineering/qwenguard-trial-recorder-2026-06-29.md",
    "docs/engineering/qwenguard-go2-memory-replay-2026-07-18.md",
    "docs/engineering/hazard-formation-gate-2026-06-16.md",
    "docs/engineering/hazard-formation-replay-pack-2026-06-16.md",
    "docs/engineering/bounded-qwen-mission-choice-2026-06-17.md",
    "docs/engineering/alibaba-ecs-manual-deploy-2026-06-15.md",
    "docs/engineering/current-status-2026-06-15.md",
    "docs/submission/README.md",
    "docs/submission/architecture.md",
    "docs/submission/demo-video-shotlist-2026-06-16.md",
    "docs/engineering/webcam-tooling-note-2026-06-15.md",
    "docs/engineering/trace-scalar-policy.md",
    "docs/engineering/review-bot-policy.md",
    "docs/engineering/research-lab-setup-2026-06-14.md",
    "docs/engineering/no-claims.md",
    "docs/security/threat-model.md",
    "fixtures/qwenguard_memory/manifest.json",
    "fixtures/qwenguard_memory/observations.json",
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

python3 -m venv "$gate_tmp/venv"
"$gate_tmp/venv/bin/python" -m pip install --upgrade pip
"$gate_tmp/venv/bin/python" -m pip install -e .

"$gate_tmp/venv/bin/run-go-gate" \
    --image fixtures/hazard_marker.ppm \
    --mode fixture \
    --out runs/go_gate/local_gate_hazard_trace.json
"$gate_tmp/venv/bin/verify-trace" runs/go_gate/local_gate_hazard_trace.json

"$gate_tmp/venv/bin/run-go-gate" \
    --image fixtures/clear_frame.ppm \
    --mode fixture \
    --out runs/go_gate/local_gate_clear_trace.json
"$gate_tmp/venv/bin/verify-trace" runs/go_gate/local_gate_clear_trace.json

"$gate_tmp/venv/bin/run-camera-go-gate" \
    --image fixtures/hazard_marker.ppm \
    --mode fixture \
    --trace-out runs/go_gate/local_gate_camera_trace.json \
    --report-out runs/go_gate/local_gate_camera_report.json
"$gate_tmp/venv/bin/verify-trace" runs/go_gate/local_gate_camera_trace.json

"$gate_tmp/venv/bin/prepare-sensor-frame-proof-pack" \
    --image fixtures/hazard_marker.ppm \
    --mode fixture \
    --out-dir runs/physical/local_gate_sensor_frame_proof

rm -rf runs/physical/local_gate_qwenguard_trials
"$gate_tmp/venv/bin/record-qwenguard-trial" \
    --trial-id local-gate-trial \
    --outcome cloud_hold \
    --cloud-mode degraded \
    --gate-decision HOLD \
    --predicted-success-milli 0 \
    --risk-level high \
    --motion-executed false \
    --control-label SCRIPTED \
    --confirm-operator-attestation \
    --trace-dir runs/physical/local_gate_qwenguard_trials/traces \
    --csv-out runs/physical/local_gate_qwenguard_trials/trial_results.csv \
    --report-out runs/physical/local_gate_qwenguard_trials/reports/local-gate-trial.json \
    --overwrite
"$gate_tmp/venv/bin/verify-trace" runs/physical/local_gate_qwenguard_trials/traces/local-gate-trial.json
"$gate_tmp/venv/bin/summarize-qwenguard-trials" \
    --trial-csv runs/physical/local_gate_qwenguard_trials/trial_results.csv \
    --trial-trace-dir runs/physical/local_gate_qwenguard_trials/traces \
    --out runs/physical/local_gate_qwenguard_trials/trial_summary.json

rm -rf runs/submission/local_gate_qwenguard_memory
"$gate_tmp/venv/bin/run-qwenguard-memory-replay" \
    --trace-out runs/submission/local_gate_qwenguard_memory/trace.json \
    --report-out runs/submission/local_gate_qwenguard_memory/report.json
"$gate_tmp/venv/bin/verify-qwenguard-memory-replay" \
    --trace runs/submission/local_gate_qwenguard_memory/trace.json \
    --report runs/submission/local_gate_qwenguard_memory/report.json

"$gate_tmp/venv/bin/run-hazard-formation-gate" \
    --image fixtures/hazard_marker.ppm \
    --mode fixture \
    --formation x \
    --trace-dir runs/hazard_formation/local_gate_x \
    --report-out runs/hazard_formation/local_gate_x_report.json
"$gate_tmp/venv/bin/verify-trace" runs/hazard_formation/local_gate_x/hazard.json

"$gate_tmp/venv/bin/prepare-ecs-operator-pack" \
    --out-dir runs/ecs/local_gate_operator_pack \
    --commit "$gate_commit"

mkdir -p runs/ecs/local_gate_proof_review
"$gate_tmp/venv/bin/python" - <<'PY'
from pathlib import Path

from accountable_swarm.trace.models import canonical_json

report = {
    "schema_version": "ecs-smoke-report.v1",
    "outcome": "GO",
    "base_url": "http://47.88.8.8:8000",
    "deployed_commit": "d" * 40,
    "collector_head": "d" * 40,
    "proof_mode": "ecs-public",
    "deployment": {
        "provider_asserted": "Alibaba Cloud ECS",
        "deployment_context_verified": True,
        "ecs_region": "us-west-1",
        "ecs_instance_id": "i-accountable-swarm",
        "ecs_public_ip": "47.88.8.8",
        "base_url_is_public_endpoint": True,
        "base_url_matches_public_ip_when_ip_literal": True,
        "ecs_metadata_identity": {
            "document_present": True,
            "region_id": "us-west-1",
            "instance_id": "i-accountable-swarm",
            "body_sha256": "a" * 64,
            "status_code": 200,
        },
        "ecs_metadata_public_ip": {
            "public_ipv4": "47.88.8.8",
            "eipv4": "",
        },
    },
    "qwen_model": "qwen3-vl-flash",
    "checks": [
        {"name": "healthz", "ok": True},
        {"name": "readyz", "ok": True},
        {"name": "camera-fixture", "ok": True},
        {"name": "qwenguard-memory-fixture", "ok": True},
        {"name": "qwen-vl-fixture_model_qwen3-vl-flash", "ok": True},
        {"name": "swarm-demo", "ok": True},
        {"name": "swarm-demo_summary.json", "ok": True},
        {"name": "qwen-ping_model_qwen3-vl-flash", "ok": True},
    ],
    "pass_conditions": {
        "healthz": True,
        "readyz": True,
        "camera-fixture": True,
        "qwenguard-memory-fixture": True,
        "qwen-vl-fixture_model_qwen3-vl-flash": True,
        "swarm-demo": True,
        "swarm-demo_summary.json": True,
        "qwen-ping_model_qwen3-vl-flash": True,
        "deployed_commit_recorded": True,
        "deployed_commit_matches_collector_head": True,
        "proof_mode_is_ecs_public": True,
        "ecs_region_recorded": True,
        "ecs_instance_id_recorded": True,
        "ecs_public_ip_is_global": True,
        "base_url_is_public_endpoint": True,
        "base_url_matches_public_ip_when_ip_literal": True,
        "ecs_metadata_identity_document_present": True,
        "ecs_metadata_region_matches": True,
        "ecs_metadata_instance_id_matches": True,
        "ecs_metadata_public_ip_matches": True,
    },
    "non_claims": ["not a production hosting claim"],
}
out = Path("runs/ecs/local_gate_proof_review/ecs_smoke_report.json")
out.write_text(canonical_json(report) + "\n", encoding="utf-8")
Path("runs/ecs/local_gate_proof_review/terminal-proof.txt").write_text(
    "Alibaba ECS public endpoint proof transcript reviewed for local gate.\n",
    encoding="utf-8",
)
PY
"$gate_tmp/venv/bin/prepare-ecs-proof-review" \
    --ecs-report runs/ecs/local_gate_proof_review/ecs_smoke_report.json \
    --terminal-artifact runs/ecs/local_gate_proof_review/terminal-proof.txt \
    --out runs/ecs/local_gate_proof_review/ecs_proof_review.md \
    --reviewed-by local-gate \
    --review-date 2026-06-29 \
    --confirm-report-go \
    --confirm-alibaba-context \
    --confirm-public-endpoint \
    --confirm-deployed-commit \
    --confirm-security-group \
    --confirm-secrets \
    --allow-overwrite

"$gate_tmp/venv/bin/python" scripts/build_swarm_demo_bundle.py \
    --out-dir runs/demo/local_gate_dimos_source
"$gate_tmp/venv/bin/prepare-dimos-bridge-pack" \
    --source-bundle runs/demo/local_gate_dimos_source \
    --out-dir runs/dimos/local_gate_bridge_pack
"$gate_tmp/venv/bin/run-dimos-replay-consumer" \
    --bridge-pack runs/dimos/local_gate_bridge_pack \
    --report-out runs/dimos/local_gate_replay_consumer_report.json

"$gate_tmp/venv/bin/python" -m unittest discover -s tests

echo "local gate passed"
