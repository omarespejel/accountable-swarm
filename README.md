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

This gate does not claim physical behavior, SO-101 operation, 3D physics,
latency, reliability, DimOS integration, or Alibaba deployment.

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
- SO-101, physics/DimOS swarm, and Alibaba ECS deployment: not yet proven.
