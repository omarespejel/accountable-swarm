# Accountable Swarm Submission Manifest

Issue: #55

## Submission Position

Accountable Swarm is a Qwen Cloud EdgeAgent hackathon project. The current
judge-facing demo is a deterministic simulated swarm, not a physical robot
claim. Qwen is used for low-rate mission intent or keyframe semantic checks.
Local deterministic code owns scenario selection, safety constraints, planning,
motion decisions, replay, and trace verification.

The checked demo claim is:

```text
Qwen-assisted mission intent -> bounded local scenario binding ->
deterministic integer-grid swarm -> hash-chained DecisionTrace per agent ->
replay-verifiable report and static visual bundle
```

## Current Judge Path

Run the swarm-first local demo bundle:

```bash
python3 scripts/build_swarm_demo_bundle.py
```

Expected high-level output:

```text
outcome GO
scenario_count 5
wrote runs/demo/swarm/index.html
wrote runs/demo/swarm/summary.json
```

Open the generated static artifact:

```text
runs/demo/swarm/index.html
```

Or serve it locally:

```bash
python3 scripts/serve_demo.py --host 127.0.0.1 --port 8000
```

Then inspect:

```text
GET /healthz
GET /readyz
GET /swarm-demo
GET /swarm-demo/summary.json
```

The `/swarm-demo` routes serve existing bundle artifacts read-only and do not
generate traces or mutate bundle state on request. Auxiliary smoke endpoints
also exist: `/camera-fixture` builds and verifies an in-memory fixture
`DecisionTrace`, and `/qwen-ping` may call DashScope when `ALIBABA_API_KEY` is
configured.

## Checked Local Evidence

Primary deterministic swarm evidence:

- `docs/engineering/swarm-demo-bundle-2026-06-15.md`
- `docs/engineering/swarm-suite-2026-06-15.md`
- `docs/engineering/swarm-scenario-registry-2026-06-15.md`
- `docs/engineering/swarm-trace-visualization-2026-06-15.md`
- `docs/engineering/current-status-2026-06-15.md`

The reviewed scenario registry is:

- `corridor`
- `center-block`
- `vertical-slalom`
- `horizontal-slalom`
- `double-chicane`

The current bundle claim is limited to four agents on deterministic integer
grids, with zero same-cell, swap, and obstacle-occupancy violations in the
trace-derived replay for the listed scenarios.

## Checked Live-Qwen Evidence

Primary live Qwen mission evidence:

- `docs/engineering/live-dashscope-swarm-mission-suite-post-hardening-2026-06-15.md`
- `docs/engineering/swarm-mission-objective-hardening-2026-06-15.md`
- `docs/engineering/swarm-mission-suite-tamper-2026-06-15.md`

Replay the fixture mission suite without API credentials:

```bash
python3 scripts/run_swarm_mission_suite.py \
  --trace-root runs/swarm/mission-suite \
  --report-out runs/swarm/mission_suite_report.json
python3 scripts/verify_swarm_mission_suite.py \
  --trace-root runs/swarm/mission-suite \
  --report runs/swarm/mission_suite_report.json \
  --report-out runs/swarm/mission_suite_verify_report.json
```

Replay live DashScope evidence only when `ALIBABA_API_KEY` is available:

```bash
set -a; . ./.env; set +a
python3 scripts/qwen_model_ping.py --models qwen-plus
python3 scripts/run_swarm_mission_suite.py \
  --mode dashscope \
  --model qwen-plus \
  --trace-root runs/swarm/live-mission-suite-after-objective-hardening \
  --report-out runs/swarm/live_mission_suite_after_objective_hardening_report.json
python3 scripts/verify_swarm_mission_suite.py \
  --trace-root runs/swarm/live-mission-suite-after-objective-hardening \
  --report runs/swarm/live_mission_suite_after_objective_hardening_report.json \
  --report-out runs/swarm/live_mission_suite_after_objective_hardening_verify_report.json
```

Do not print or commit API keys. Keep live-provider results bounded to the
model, date, command, and scenario registry recorded in the evidence docs.

## Architecture Diagram

See `docs/submission/architecture.md`.

Short architecture statement:

```text
Qwen proposes low-rate semantic intent. Local deterministic code binds that
intent to a reviewed scenario, runs the integer-grid swarm, emits one
DecisionTrace per agent, and verifies replay from persisted traces.
```

## Alibaba ECS Proof Status

Status: pending operator action.

Manual deployment checklist:

- `docs/engineering/alibaba-ecs-manual-deploy-2026-06-15.md`

The repo already contains the minimal stdlib backend and Dockerfile. The
submission must not claim completed Alibaba ECS deployment until the operator
runs the checklist, captures the public endpoint, and records the proof.

Proof checklist for the operator:

1. Provision ECS manually.
2. Deploy the repo or image.
3. Set `ALIBABA_API_KEY` as an environment secret on the host.
4. Run `python3 scripts/build_swarm_demo_bundle.py`.
5. Run `python3 scripts/serve_demo.py --host 0.0.0.0 --port 8000`.
6. Capture public responses for `/healthz`, `/readyz`, `/swarm-demo`, and
   `/swarm-demo/summary.json`.
7. Record endpoint, date, command transcript, and non-claims in a new evidence
   doc before using it in the hackathon submission.

## Demo Video Shot List

Use a short screen-recorded video. Keep it factual.

1. Show the repository root, `LICENSE`, and this manifest.
2. Run `python3 scripts/build_swarm_demo_bundle.py`.
3. Show `outcome GO`, `scenario_count 5`, and the generated `runs/demo/swarm`
   paths.
4. Open `runs/demo/swarm/index.html` and click through the five reviewed
   scenarios.
5. Show `runs/demo/swarm/summary.json` with scenario outcomes and replay
   counters.
6. Show `docs/submission/architecture.md` and point out that Qwen is not in the
   real-time loop.
7. Optional, if ECS proof exists: show the public `/swarm-demo` endpoint and
   `/readyz` response.

## Submission Text Draft

Accountable Swarm demonstrates accountable edge-cloud robotics with Qwen in a
bounded, auditable role. Qwen provides low-rate mission intent, while local
deterministic code binds the mission to reviewed scenarios, runs a four-agent
integer-grid swarm, enforces collision and obstacle guards, and emits
hash-chained DecisionTrace artifacts. The demo bundle is reproducible from one
local command and includes static replay pages plus machine-readable summaries
for the reviewed scenario registry.

## Final Non-Claims

- No physical robot behavior.
- No SO-101 operation.
- No 3D physics simulation.
- No latency claim.
- No reliability claim.
- No DimOS integration.
- No Alibaba ECS deployment proof until the operator checklist is completed.
- No Qwen real-time control.
- No Qwen onboard execution.
- No arbitrary-map planner claim.
- No larger-swarm claim beyond the listed deterministic four-agent integer-grid
  cases.
