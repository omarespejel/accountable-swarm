# accountable-swarm

Accountable Swarm is a Qwen Cloud EdgeAgent hackathon project for accountable
edge-cloud robotics. The first goal is not a large swarm. The first goal is a
reproducible decision trace:

```text
edge sensor frame -> Qwen keyframe check -> local decision -> hash-chained trace -> replay
```

The project is intentionally split into two tracks:

- **Submission repo:** this repository, with a clean license, a runnable GO gate,
  an Alibaba Cloud proof checklist, and judge-friendly setup.
- **Upstream work:** a separate DimOS fork branch for any `DroneFleetConnection`
  or multi-drone scene work that is useful to contribute back.

## Review Setup

This repo is configured for PR review by CodeRabbit and Qodo:

- CodeRabbit: `.coderabbit.yaml`
- Qodo: `.pr_agent.toml`
- Repo review rules: `AGENTS.md`
- Fresh-agent entrypoint: `.codex/START_HERE.md`
- Research operating model: `.codex/research/operating_model.yml`
- Bot triage policy: `docs/engineering/review-bot-policy.md`

The GitHub apps still need to be installed/enabled in their dashboards for the
repository. Repo-side config alone does not grant either bot access.

## Research Lab Setup

Start every non-trivial task from:

```bash
./scripts/local_gate.sh
```

Use GitHub issues as hypotheses with explicit GO/NO-GO gates. Public claims need
checked artifacts, exact commands, and explicit non-claims before promotion.

Optional installable CLI setup:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -e .
run-go-gate --image fixtures/hazard_marker.ppm --mode fixture --out runs/go_gate/trace.json
verify-trace runs/go_gate/trace.json
```

`./scripts/local_gate.sh` also creates a temporary virtual environment and
checks those installed entry points directly.

## Submission Manifest

The current judge-facing swarm path is collected in
`docs/submission/README.md`, with the architecture diagram in
`docs/submission/architecture.md`. The manifest links the one-command swarm demo
bundle, live-Qwen evidence, Alibaba ECS proof checklist, demo-video shot list,
and final non-claims.

Prepare the current local recording artifacts without provider credentials:

```bash
python3 scripts/prepare_demo_recording_pack.py
```

This writes `runs/demo/recording-pack/manifest.json` and
`runs/demo/recording-pack/shotlist.md`, then points to the generated animated
swarm replay and hazard-to-X-formation report. It is a recording convenience
over checked deterministic paths, not DimOS, SO-101, 3D physics, ECS proof, or
Qwen real-time control evidence.

## Current Build Gate

The first useful success is:

```text
one image/frame -> qwen3-vl-flash bbox JSON -> normalized-coordinate rescale
-> DecisionTrace JSON -> deterministic hash-chain replay
```

Fixture-mode local gate now runs this spine for two deterministic frames:
`fixtures/hazard_marker.ppm` emits `VETO`, and `fixtures/clear_frame.ppm` emits
`MOVE`. No swarm, SO-101, Qwen latency, reliability, or production-readiness
claim follows from that fixture evidence.

## Camera / Static-Frame Gate

The next gate uses the same accountable trace spine with an edge-frame source:

```bash
python3 scripts/run_camera_go_gate.py \
  --image fixtures/hazard_marker.ppm \
  --mode fixture \
  --trace-out runs/go_gate/camera_trace.json \
  --report-out runs/go_gate/camera_report.json
python3 -m scripts.verify_trace runs/go_gate/camera_trace.json
```

After `python3 -m pip install -e .`, the same gate is available as
`run-camera-go-gate`. `./scripts/local_gate.sh` validates that installed
entry point on the fixture frame.

Live Qwen mode requires a local `ALIBABA_API_KEY`:

```bash
run-camera-go-gate \
  --image runs/go_gate/hazard_marker.png \
  --mode dashscope \
  --trace-out runs/go_gate/camera_qwen_trace.json \
  --report-out runs/go_gate/camera_qwen_report.json
```

The report records five binary pass conditions: model response, JSON
validation, bbox rescaling, deterministic trace replay, and DecisionTrace schema
emission from the frame.

To turn that into a reproducible physical-lane artifact without committing raw
sensor imagery, build the sensor-frame proof pack:

```bash
prepare-sensor-frame-proof-pack \
  --image fixtures/hazard_marker.ppm \
  --mode fixture \
  --out-dir runs/physical/sensor-frame-proof
```

For a live sensor frame, replace `--image ...` with `--capture-webcam`. Captured
webcam frames are deleted after hashing by default unless
`--keep-captured-frame` is set.

For the SO-101-specific camera lane, the repo now exposes a trace-only probe:

```bash
capture-so101-camera-frame \
  --camera-name so101_overhead \
  --index-or-path 0 \
  --out runs/physical/so101_frame.png \
  --report-out runs/physical/so101_capture_report.json
```

On machines without the optional `lerobot` and `opencv` dependencies, this
returns a controlled `NO_GO` report instead of silently failing or widening the
claim boundary.

To prepare the operator-run setup pack for the actual SO-101 machine:

```bash
prepare-so101-operator-probe-pack \
  --out-dir runs/physical/so101-operator-pack \
  --camera-name so101_overhead \
  --camera-id 0
```

That pack writes a runbook and command script pinned to the current official
LeRobot installation and OpenCV camera flow.

## Simulated Swarm Gate

The first swarm-shaped gate is deterministic and local. It uses an integer grid,
not physics, to prove that multiple local actors can emit replayable
DecisionTrace artifacts while collision and swap guards stay outside the Qwen
loop.

```bash
python3 scripts/run_swarm_sim.py \
  --agents 2 \
  --ticks 8 \
  --trace-dir runs/swarm/n2 \
  --report-out runs/swarm/n2_report.json
python3 -m scripts.verify_trace runs/swarm/n2/sim-agent-0.json
python3 -m scripts.verify_trace runs/swarm/n2/sim-agent-1.json
```

The report includes a trace-derived replay section with final positions and
same-cell/swap collision counts.

Obstacle scenario:

```bash
python3 scripts/run_swarm_sim.py \
  --agents 2 \
  --ticks 9 \
  --scenario center-block \
  --trace-dir runs/swarm/center-block-n2 \
  --report-out runs/swarm/center_block_n2_report.json
```

The obstacle report additionally records obstacle coordinates and
trace-replayed obstacle-occupancy violations.

Four-agent obstacle scenario with the bounded deterministic reservation planner:

```bash
python3 scripts/run_swarm_sim.py \
  --agents 4 \
  --ticks 16 \
  --scenario center-block \
  --trace-dir runs/swarm/reservation-center-block-n4 \
  --report-out runs/swarm/reservation_center_block_n4_report.json
```

This currently produces `GO` for the scoped integer-grid case: all four agents
reach goals, with zero same-cell collisions, zero swaps, zero obstacle
occupancy violations, and trace-derived replay counters matching the simulator
report.

Second fixed obstacle layout:

```bash
python3 scripts/run_swarm_sim.py \
  --agents 4 \
  --ticks 16 \
  --scenario vertical-slalom \
  --trace-dir runs/swarm/vertical-slalom-n4 \
  --report-out runs/swarm/vertical_slalom_n4_report.json
```

This currently produces `GO` for the scoped two-obstacle integer-grid case.

Third fixed obstacle layout:

```bash
python3 scripts/run_swarm_sim.py \
  --agents 4 \
  --ticks 16 \
  --scenario horizontal-slalom \
  --trace-dir runs/swarm/horizontal-slalom-n4 \
  --report-out runs/swarm/horizontal_slalom_n4_report.json
```

This currently produces `GO` for the scoped horizontal two-obstacle
integer-grid case.

Five-obstacle double-chicane layout:

```bash
python3 scripts/run_swarm_sim.py \
  --agents 4 \
  --ticks 17 \
  --scenario double-chicane \
  --trace-dir runs/swarm/double-chicane-n4 \
  --report-out runs/swarm/double_chicane_n4_report.json
```

This currently produces `GO` for the scoped five-obstacle integer-grid case.
A 16-tick run for the same scenario intentionally remains `NARROW_CLAIM`.

This gate does not claim physical behavior, SO-101 operation, 3D physics,
latency, reliability, DimOS integration, Alibaba deployment, or a
general-purpose multi-agent planner.

## Low-Rate Mission Gate

The mission gate gives Qwen-style reasoning a bounded, low-rate role. A fixture
proposes a strict mission JSON envelope; DashScope text mode proposes only an
`objective` string. Local code binds the reviewed scenario, mission id, agent
count, and tick budget before the deterministic simulator runs.

```bash
python3 scripts/run_swarm_mission_gate.py \
  --mode fixture \
  --trace-dir runs/swarm/mission-fixture-n4 \
  --report-out runs/swarm/mission_fixture_n4_report.json
```

Fixture mode currently produces `GO` for `center-block`, `agent_count=4`, and
`ticks=16`. This does not place Qwen in the real-time loop and does not prove a
live Qwen mission assignment unless `--mode dashscope` is separately recorded.
The fixture can also request reviewed scenario-registry names, for example:

```bash
python3 scripts/run_swarm_mission_gate.py \
  --mode fixture \
  --mission-scenario horizontal-slalom \
  --trace-dir runs/swarm/mission-horizontal-slalom-fixture-n4 \
  --report-out runs/swarm/mission_horizontal_slalom_fixture_n4_report.json
```

This currently produces `GO` for the scoped horizontal-slalom mission fixture.

Live DashScope mission intent can be recorded for a reviewed scenario while
keeping the scenario, mission id, agent count, tick budget, and motion authority
local:

```bash
python3 scripts/run_swarm_mission_gate.py \
  --mode dashscope \
  --model qwen-plus \
  --mission-scenario center-block \
  --trace-dir runs/swarm/live-mission-center-block \
  --report-out runs/swarm/live_mission_center_block_report.json
```

The checked 2026-06-15 evidence shows `GO` for `qwen-plus` intent into the
reviewed `center-block` N=4 deterministic swarm gate. This is not a real-time
Qwen control claim, arbitrary mission claim, or physical robot claim.

Mission suite:

```bash
python3 scripts/run_swarm_mission_suite.py \
  --trace-root runs/swarm/mission-suite \
  --report-out runs/swarm/mission_suite_report.json
```

The suite defaults to fixture mission binding for every reviewed scenario in
the deterministic registry: `corridor`, `center-block`, `vertical-slalom`,
`horizontal-slalom`, and `double-chicane`. Suite `GO` means each child mission
gate was `GO`, every mission and agent trace reloaded from disk to the recorded
summary SHA, and
trace-derived replay counters stayed at zero for same-cell, swap, and obstacle
occupancy violations.

Live DashScope mission suite:

```bash
python3 scripts/run_swarm_mission_suite.py \
  --mode dashscope \
  --model qwen-plus \
  --trace-root runs/swarm/live-mission-suite \
  --report-out runs/swarm/live_mission_suite_report.json
python3 scripts/verify_swarm_mission_suite.py \
  --trace-root runs/swarm/live-mission-suite \
  --report runs/swarm/live_mission_suite_report.json \
  --report-out runs/swarm/live_mission_suite_verify_report.json
```

The prior checked 2026-06-15 evidence shows `GO` for live `qwen-plus` mission
intent across the then-reviewed four scenario-registry names. The refreshed
post-hardening 2026-06-15 evidence also shows `GO` for live `qwen-plus` mission
intent across the current five-scenario registry, including `double-chicane`.
This is still not a real-time Qwen control claim, arbitrary-map claim,
larger-swarm claim, or physical robot claim.

Mission-suite trace verification:

```bash
python3 scripts/verify_swarm_mission_suite.py \
  --trace-root runs/swarm/mission-suite \
  --report runs/swarm/mission_suite_report.json \
  --report-out runs/swarm/mission_suite_verify_report.json
```

This verifier walks the persisted mission and agent traces referenced by the
suite report. It returns `GO` for clean artifacts and `NARROW_CLAIM` if a trace
is mutated without recomputing the hash chain and summary SHA.

## Swarm Trace Visualization

The trace renderer turns persisted agent `DecisionTrace` files into a static
HTML/SVG replay and canonical JSON summary. It verifies traces before
rendering and fails closed if a trace was mutated.

```bash
python3 scripts/run_swarm_sim.py \
  --agents 4 \
  --ticks 16 \
  --scenario center-block \
  --trace-dir runs/swarm/render-center-block \
  --report-out runs/swarm/render_center_block_report.json
python3 scripts/render_swarm_trace_html.py \
  --trace-dir runs/swarm/render-center-block \
  --grid-width 7 \
  --grid-height 5 \
  --obstacle 3,2 \
  --html-out runs/swarm/render-center-block.html \
  --summary-out runs/swarm/render_center_block_visual_summary.json
```

The checked 2026-06-15 evidence shows `GO` for the N=4 center-block trace
replay artifact with zero same-cell, swap, and obstacle-occupancy violations
and deterministic HTML SHA
`686a328376478bc1bf76b9c59b7ed283f6889d5d48003fdc8928f9f80a231f60`.
This is not a physical, physics, latency, live-Qwen, arbitrary-map, or
larger-swarm claim.

## One-Command Swarm Demo Bundle

The demo bundle command generates scenario reports, verified agent traces,
animated replay pages, static per-tick SVG frames, and a deterministic index
from the reviewed local scenario registry:

```bash
python3 scripts/build_swarm_demo_bundle.py
```

The checked 2026-06-15 evidence shows `GO` across `corridor`,
`center-block`, `vertical-slalom`, `horizontal-slalom`, and `double-chicane`,
with bundle index SHA
`b929f77827e69b9100e9883f78e7b882e7b161d67350a31a129d452f99c63368`.
This command is the current swarm-first judge path. It does not require live
Qwen, SO-101, webcam access, DimOS, Docker, or cloud credentials.
Use `--out-dir` only when you want to override the default `runs/demo/swarm`
output location.

Each scenario replay page includes a browser canvas animation driven by the
same verified `DecisionTrace` timeline as the static frames. It is recordable
demo material, not a DimOS, 3D physics, live-Qwen-control, latency, or
physical-robot claim.

## Hazard Formation Gate

The hazard formation gate links the perception and swarm surfaces without
putting Qwen in the control loop:

```bash
python3 -m scripts.run_hazard_formation_gate \
  --image fixtures/hazard_marker.ppm \
  --mode fixture \
  --formation x \
  --trace-dir runs/hazard_formation/smoke_x \
  --report-out runs/hazard_formation/smoke_x_report.json
```

The checked fixture path converts a Qwen-style bbox into an integer-grid hazard
cell, assigns four agents to an `x` formation around it, routes them with the
local reservation planner, and verifies persisted hazard and agent traces from
disk. Degraded mode emits local `HOLD` traces when cloud perception is
unavailable or invalid:

```bash
python3 -m scripts.run_hazard_formation_gate \
  --image fixtures/hazard_marker.ppm \
  --mode degraded \
  --trace-dir runs/hazard_formation/degraded \
  --report-out runs/hazard_formation/degraded_report.json
```

This is not physical robot behavior, 3D grounding, DimOS integration, latency,
reliability, safety, or Qwen real-time control.

Live DashScope keyframe hazard perception can be recorded when
`ALIBABA_API_KEY` is available in the local environment:

```bash
python3 scripts/make_hazard_fixture.py runs/go_gate/hazard_marker.png
python3 -m scripts.run_hazard_formation_gate \
  --image runs/go_gate/hazard_marker.png \
  --mode dashscope \
  --model qwen3-vl-flash \
  --formation x \
  --trace-dir runs/hazard_formation/live_dashscope_x \
  --report-out runs/hazard_formation/live_dashscope_x_report.json
```

The checked 2026-06-16 live run produced `outcome GO`, quantized Qwen's hazard
bbox to grid cell `{"x": 3, "y": 2}`, compiled an `x` formation, and verified
the hazard plus four agent traces. See
`docs/engineering/live-dashscope-hazard-formation-2026-06-16.md`.

## Swarm Scenario Suite

The suite reruns the deterministic swarm cases and includes one intentional
`NARROW_CLAIM` canary so the report catches overclaiming:

```bash
python3 scripts/run_swarm_suite.py \
  --trace-root runs/swarm/suite \
  --report-out runs/swarm/suite_report.json
```

The suite currently expects `GO` for N=2 corridor, N=2 center-block, N=4
center-block, N=4 vertical-slalom, N=4 horizontal-slalom, and N=4
double-chicane, and expects `NARROW_CLAIM` for a deliberately too-short N=4
center-block run. Suite `GO` means those
expectations matched and persisted agent traces replayed deterministically from
disk.

## Minimal Backend

For manual Alibaba ECS proof, run the stdlib demo server:

```bash
python3 scripts/serve_demo.py --host 127.0.0.1 --port 8000
```

Smoke endpoints:

```text
GET /healthz
GET /readyz
GET /camera-fixture
GET /qwen-ping?model=qwen-plus
GET /swarm-demo
GET /swarm-demo/summary.json
```

Run `python3 scripts/build_swarm_demo_bundle.py` before opening
`/swarm-demo`. The `/swarm-demo` routes serve existing bundle artifacts
read-only and do not generate or mutate bundle state on request. Auxiliary
smoke endpoints also exist: `/camera-fixture` builds and verifies an in-memory
fixture `DecisionTrace`, and `/qwen-ping` may call DashScope when
`ALIBABA_API_KEY` is configured.

See `docs/engineering/alibaba-ecs-manual-deploy-2026-06-15.md`.

## Current Status

See `docs/engineering/current-status-2026-06-15.md` for the current GO /
NARROW_CLAIM matrix. The short version:

- Qwen and DecisionTrace spine: GO.
- Camera/static-frame live Qwen gate: GO for generated static frame.
- Fixture GO-gate P1 hardening: local gate runs hazard->`VETO` and
  clear->`MOVE`, then verifies both traces.
- Deterministic N=2 integer-grid simulated swarm: GO.
- Deterministic N=2 center-block obstacle scenario: GO.
- Deterministic N=4 center-block obstacle scenario: GO for the scoped
  integer-grid reservation-planner gate.
- Deterministic N=4 vertical-slalom obstacle scenario: GO for the scoped
  integer-grid reservation-planner gate.
- Deterministic N=4 horizontal-slalom obstacle scenario: GO for the scoped
  integer-grid reservation-planner gate.
- Deterministic N=4 double-chicane obstacle scenario: GO at 17 ticks and
  NARROW_CLAIM at 16 ticks.
- Larger simulated swarm counts: intentionally unsupported today; N=5 is
  rejected before trace/report artifacts are written.
- Low-rate fixture mission assignment into N=4 center-block and
  horizontal-slalom swarm gates: GO.
- Mission objective text hardening: intent strings with hidden counts,
  coordinates, scenarios, arrays, or control terms are rejected.
- Live `qwen-plus` mission intent into the reviewed N=4 center-block swarm
  gate: GO.
- Live `qwen-plus` mission suite across the reviewed five-scenario registry:
  GO, including `double-chicane`, after objective-text hardening.
- Deterministic swarm scenario suite with expected-NARROW canary: GO.
- Deterministic animated/static swarm trace visualization from verified
  persisted traces: GO.
- One-command deterministic swarm demo bundle across the reviewed scenario
  registry: GO.
- Read-only stdlib server endpoints for the deterministic swarm demo bundle:
  GO.
- Hazard bbox to formation planner gate: GO in fixture mode, with degraded
  local hold fallback.
- SO-101, physics/DimOS swarm, and Alibaba ECS deployment: not yet proven.
