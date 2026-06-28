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
explicit world-model timeline -> replay-verifiable report and dashboard
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

Open the generated replay artifact:

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

Prepare the world-model dashboard artifact:

DashScope mode requires `ALIBABA_API_KEY` in the environment and records Qwen
keyframe perception plus bounded mission choice. For an offline/no-key run, use
`--mode fixture --mission-source fixture` with the same commands and keep the
resulting artifact labeled as fixture evidence.

```bash
python3 -m scripts.run_hazard_formation_gate \
  --image fixtures/hazard_marker.ppm \
  --mode dashscope \
  --mission-source dashscope \
  --model qwen3-vl-flash \
  --mission-model qwen3-vl-flash \
  --formation x \
  --trace-dir runs/hazard_formation/world_model_x \
  --report-out runs/hazard_formation/world_model_x_report.json

python3 -m scripts.prepare_world_model_dashboard_pack \
  --trace-dir runs/hazard_formation/world_model_x \
  --hazard-report runs/hazard_formation/world_model_x_report.json \
  --out-dir runs/dashboard/world_model_x

python3 -m scripts.render_world_model_dashboard_html \
  --data runs/dashboard/world_model_x/data.json \
  --html-out runs/dashboard/world_model_x/index.html \
  --summary-out runs/dashboard/world_model_x/summary.json
```

Open the generated dashboard:

```text
runs/dashboard/world_model_x/index.html
```

This dashboard is the recommended recording surface for the accountable
world-model path because it shows Qwen evidence, deterministic local planning,
the bounded mission choice, world-model hashes, and per-agent trace hashes in
one page. If `ALIBABA_API_KEY` is unavailable, switch `--mode fixture
--mission-source fixture` and keep the same local validation surface.

## Checked Local Evidence

Primary deterministic swarm evidence:

- `docs/engineering/swarm-demo-bundle-2026-06-15.md`
- `docs/engineering/swarm-suite-2026-06-15.md`
- `docs/engineering/swarm-scenario-registry-2026-06-15.md`
- `docs/engineering/swarm-trace-visualization-2026-06-15.md`
- `docs/engineering/dimos-bridge-probe-2026-06-16.md` (optional bridge
  export only; no DimOS execution claim)
- `docs/engineering/current-status-2026-06-15.md`

The reviewed scenario registry is:

- `corridor`
- `center-block`
- `vertical-slalom`
- `horizontal-slalom`
- `double-chicane`

The current bundle claim is limited to four agents on deterministic integer
grids, with zero same-cell, swap, and obstacle-occupancy violations in the
trace-derived replay for the listed scenarios. Each scenario replay page now
contains a recordable animated panel plus static per-tick SVG frames generated
from the same verified persisted traces.

Primary hazard-to-formation evidence:

- `docs/engineering/hazard-formation-gate-2026-06-16.md`
- `docs/engineering/hazard-formation-replay-pack-2026-06-16.md`
- `docs/engineering/world-model-state-2026-06-16.md`
- `docs/engineering/world-model-hazard-binding-2026-06-16.md`
- `docs/engineering/world-model-dashboard-pack-2026-06-16.md`
- `docs/engineering/world-model-dashboard-renderer-2026-06-16.md`
- `docs/engineering/live-dashscope-hazard-formation-2026-06-16.md`

Replay the fixture hazard-to-X gate:

```bash
python3 -m scripts.run_hazard_formation_gate \
  --image fixtures/hazard_marker.ppm \
  --mode fixture \
  --formation x \
  --trace-dir runs/hazard_formation/smoke_x \
  --report-out runs/hazard_formation/smoke_x_report.json
```

This checked path maps a Qwen-style 2D bbox to an integer-grid hazard cell,
assigns four agents to formation slots, and verifies persisted hazard and agent
traces from disk. It is not 3D grounding, physical behavior, or Qwen real-time
control.

The recording pack also renders the generated agent traces into
`runs/hazard_formation/recording_x_replay/index.html`, with the hazard cell
shown as the obstacle. This makes the perception-to-formation path visible
without changing the claim boundary.

When `ALIBABA_API_KEY` is available, the live hazard-to-formation proof uses
`qwen3-vl-flash` on a generated PNG keyframe and the same model for the bounded
mission JSON. The checked 2026-06-16 run returned `outcome GO`, bbox
`[241,238,756,759]`, hazard cell `{"x":3,"y":2}`, and replay-verified hazard
plus four agent traces. The mission JSON is locally validated against the
allow-list before planning. This remains keyframe perception and low-rate
mission reasoning feeding deterministic local planning, not live Qwen control.

## Checked Live-Qwen Evidence

Primary live Qwen mission evidence:

- `docs/engineering/live-dashscope-swarm-mission-suite-post-hardening-2026-06-15.md`
- `docs/engineering/live-dashscope-hazard-formation-2026-06-16.md`
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

Replay live DashScope evidence only when `ALIBABA_API_KEY` is available. Obtain
the key from the operator's Alibaba Cloud DashScope console, then either export
it in the shell or place it in a local untracked `.env` file as
`ALIBABA_API_KEY=...`.

If using `.env`, load it before running the live commands:

```bash
set -a; . ./.env; set +a
```

Then run:

```bash
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
- `docs/engineering/ecs-operator-proof-pack-2026-06-16.md`

Prepare the non-secret operator pack before provisioning or while preparing the
ECS session:

```bash
python3 scripts/prepare_ecs_operator_pack.py --commit "$(git rev-parse HEAD)"
```

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

Use a short screen-recorded video. Keep it factual. The detailed recording
guide is `docs/submission/demo-video-shotlist-2026-06-16.md`.

Prepare the local recording pack:

```bash
python3 scripts/prepare_demo_recording_pack.py
```

By default the recording pack now prefers live DashScope for the hazard and
bounded mission path when `ALIBABA_API_KEY` is present, and otherwise falls
back to fixture mode without changing the local deterministic replay surface.

Expected high-level output:

```text
outcome GO
manifest runs/demo/recording-pack/manifest.json
shotlist runs/demo/recording-pack/shotlist.md
```

1. Show the repository root, `LICENSE`, and this manifest.
2. Run `python3 scripts/build_swarm_demo_bundle.py`.
3. Show `outcome GO`, `scenario_count 5`, and the generated `runs/demo/swarm`
   paths.
4. Open `runs/demo/swarm/index.html` and click through the five reviewed
   scenarios.
5. Show `runs/demo/swarm/summary.json` with scenario outcomes and replay
   counters.
6. Open `runs/hazard_formation/recording_x_replay/index.html` and show the
   hazard cell obstacle plus the four-agent X formation replay.
7. Open `runs/dashboard/recording_x/index.html` and show the Qwen bbox, bounded
   mission choice, local planner, world-model hash, and per-agent
   `DecisionTrace` hashes.
8. Show `runs/hazard_formation/recording_x_report.json` with bbox, hazard cell,
   bounded mission choice, formation, assigned goals, and trace hashes.
9. Show `docs/submission/architecture.md` and point out that Qwen is not in the
   real-time loop.
10. Optional, if the DimOS bridge pack exists: show its manifest and state that
   it is a verified replay export, not DimOS execution.
11. Optional, if ECS proof exists: show the public `/swarm-demo`,
    `/hazard-formation`, `/world-model-dashboard`, and `/readyz` responses.

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
- DimOS is not executed or integrated; bridge-export artifacts are optional and
  do not prove DimOS consumed the trace.
- No Alibaba ECS deployment proof until the operator checklist is completed.
- No Qwen real-time control.
- No Qwen onboard execution.
- No arbitrary-map planner claim.
- No larger-swarm claim beyond the listed deterministic four-agent integer-grid
  cases.
