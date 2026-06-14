# accountable-swarm

Accountable Swarm is a Qwen Cloud EdgeAgent hackathon project for accountable
edge-cloud robotics. The first goal is not a large swarm. The first goal is a
reproducible decision trace:

```text
edge sensor frame -> Qwen keyframe check -> local decision -> hash-chained trace -> replay
```

The project is intentionally split into two tracks:

- **Submission repo:** this repository, with a clean license, a runnable GO gate,
  Alibaba Cloud proof artifacts, and judge-friendly setup.
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

## Current Build Gate

The first useful success is:

```text
one image/frame -> qwen3-vl-flash bbox JSON -> normalized-coordinate rescale
-> DecisionTrace JSON -> deterministic hash-chain replay
```

No swarm, SO-101, Qwen latency, reliability, or production-readiness claim is
made until this gate passes with checked-in evidence.

## Camera / Static-Frame Gate

The next gate uses the same accountable trace spine with an edge-frame source:

```bash
python3 scripts/run_camera_go_gate.py \
  --image fixtures/hazard_marker.ppm \
  --mode fixture \
  --trace-out runs/go_gate/camera_trace.json \
  --report-out runs/go_gate/camera_report.json
python3 scripts/verify_trace.py runs/go_gate/camera_trace.json
```

Live Qwen mode requires a local `ALIBABA_API_KEY`:

```bash
python3 scripts/run_camera_go_gate.py \
  --image runs/go_gate/hazard_marker.png \
  --mode dashscope \
  --trace-out runs/go_gate/camera_qwen_trace.json \
  --report-out runs/go_gate/camera_qwen_report.json
```

The report records five binary pass conditions: model response, JSON
validation, bbox rescaling, deterministic trace replay, and DecisionTrace schema
emission from the frame.

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
python3 scripts/verify_trace.py runs/swarm/n2/sim-agent-0.json
python3 scripts/verify_trace.py runs/swarm/n2/sim-agent-1.json
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

## Swarm Scenario Suite

The suite reruns the deterministic swarm cases and includes one intentional
`NARROW_CLAIM` canary so the report catches overclaiming:

```bash
python3 scripts/run_swarm_suite.py \
  --trace-root runs/swarm/suite \
  --report-out runs/swarm/suite_report.json
```

The suite currently expects `GO` for N=2 corridor, N=2 center-block, N=4
center-block, N=4 vertical-slalom, and N=4 horizontal-slalom, and expects
`NARROW_CLAIM` for a
deliberately too-short N=4 center-block run. Suite `GO` means those
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
```

See `docs/engineering/alibaba-ecs-manual-deploy-2026-06-15.md`.

## Current Status

See `docs/engineering/current-status-2026-06-15.md` for the current GO /
NARROW_CLAIM matrix. The short version:

- Qwen and DecisionTrace spine: GO.
- Camera/static-frame live Qwen gate: GO for generated static frame.
- Deterministic N=2 integer-grid simulated swarm: GO.
- Deterministic N=2 center-block obstacle scenario: GO.
- Deterministic N=4 center-block obstacle scenario: GO for the scoped
  integer-grid reservation-planner gate.
- Deterministic N=4 vertical-slalom obstacle scenario: GO for the scoped
  integer-grid reservation-planner gate.
- Deterministic N=4 horizontal-slalom obstacle scenario: GO for the scoped
  integer-grid reservation-planner gate.
- Low-rate fixture mission assignment into N=4 center-block and
  horizontal-slalom swarm gates: GO.
- Deterministic swarm scenario suite with expected-NARROW canary: GO.
- SO-101, physics/DimOS swarm, and Alibaba ECS deployment: not yet proven.
