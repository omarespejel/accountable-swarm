# Current Status 2026-06-15

This is the current repo state after the first 10-hour execution block began at
2026-06-15 00:37 JST.

## GO

- Research-lab operating model is merged on `main`.
- Fixture image to `DecisionTrace` replay works.
- Live `qwen3-vl-flash` generated-PNG keyframe to `DecisionTrace` works.
- `qwen-plus` and `qwen3.5-plus` model pings work through
  `scripts/qwen_model_ping.py`.
- Trace canonical JSON rejects raw floats.
- Camera/static-frame GO gate reports five binary pass conditions.
- Degraded/offline mode emits local `HOLD` trace without Qwen.
- Minimal stdlib HTTP server works locally.
- Deterministic N=2 integer-grid simulated swarm reaches both goals, emits one
  DecisionTrace per agent, replays final positions from traces, and reports zero
  same-cell or swap collisions.
- Exploratory deterministic N=4 integer-grid probe reaches goals and reports
  zero same-cell or swap collisions.
- Deterministic N=2 center-block obstacle scenario reaches both goals, reports
  zero same-cell collisions, zero swap collisions, zero obstacle occupancy
  violations, and replay recomputes obstacle occupancy from traces.

## NARROW_CLAIM

- Camera/static-frame gate is live-Qwen GO for a generated static frame, not a
  true webcam frame.
- One true webcam frame with target `person` passed locally after installing
  `imagesnap`, but the artifact is intentionally not committed and no physical
  robot claim follows from it.
- Alibaba ECS manual deploy path is ready, but actual ECS proof is pending.
- Physical-node safety contract exists, but no SO-101 connectivity or safe
  motion is proven.
- Deterministic N=4 center-block obstacle scenario avoids collisions and the
  obstacle but does not reach all goals with the current local guard.

## Open Blockers

- CodeRabbit status check fails because credits are exhausted, not because of a
  new code finding.
- True webcam capture now depends on local camera permission and `imagesnap`;
  this is machine state, not a judge-facing dependency.
- Local Docker CLI exists, but the Colima/Docker daemon socket is not running,
  so Docker image build was not executed locally.
- Alibaba ECS instance is not provisioned from this repo; the operator must run
  the manual deploy path.

## Validation Snapshot

Latest local gates during this block:

```text
./scripts/local_gate.sh
Ran 28 tests
OK
local gate passed
```

Live Qwen camera/static-frame gate:

```text
outcome GO
trace_summary_sha 214d4edb89537ecf6c8060b2e4fcd6053497aa20439b65cca8641ef8d0e011c8
```

Local server smoke:

```text
GET /healthz -> {"service":"accountable-swarm","status":"ok"}
GET /readyz -> {"default_vl_model":"qwen3-vl-flash","has_alibaba_api_key":true,"status":"ok"}
GET /camera-fixture -> trace_summary_sha 282a7982facaf066732b4a3dd1039529e0c8e5b8d54b2b1d458b0b8b7c6e5d2a
GET /qwen-ping?model=qwen-plus -> {"content_prefix":"OK.","model":"qwen-plus","status":"ok"}
```

Deterministic N=2 swarm gate:

```text
python3 scripts/run_swarm_sim.py --agents 2 --ticks 8 --trace-dir runs/swarm/n2 --report-out runs/swarm/n2_report.json
outcome GO
same_cell_collision_count 0
swap_collision_count 0
reroute_count 1
sim-agent-0 summary_sha a12de617ca2f821ba940d20388ec6bda7f333fd931df1658b3dbe1dd409233f7
sim-agent-1 summary_sha 48fa08de489df7f15bd52fadf8c09f8fca203c22debb9820bede603c909937de
replay same_cell_collision_count 0
replay swap_collision_count 0
```

Exploratory deterministic N=4 swarm probe:

```text
outcome GO
same_cell_collision_count 0
swap_collision_count 0
reroute_count 4
```

Deterministic N=2 center-block obstacle gate:

```text
python3 scripts/run_swarm_sim.py --agents 2 --ticks 9 --scenario center-block --trace-dir runs/swarm/center-block-n2-replay --report-out runs/swarm/center_block_n2_replay_report.json
outcome GO
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
reroute_count 2
sim-agent-0 summary_sha 972e065c57ce1fa897dadeb940a61350ff4941981da0ba0f2a7ff377d65ebca0
sim-agent-1 summary_sha 34ebe9efad6276c48d2a076c3630482c06b0cbf977c950849df2a35f4bc68cc3
```

Exploratory deterministic N=4 center-block obstacle probe:

```text
outcome NARROW_CLAIM
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
all_goals_reached false
```

## Next Work

1. Run the ECS manual deployment path on Alibaba Cloud and record proof.
2. Decide whether the next swarm step is a reservation-table planner for N=4
   center-block, a DimOS adapter sketch, or Qwen low-rate mission planner.
3. Convert webcam evidence into a redacted/fixture-safe artifact only if it is
   useful for the hackathon story.

## Non-Claims

Do not claim:

- true webcam capture;
- SO-101 operation;
- physical safety;
- latency or reliability;
- physics-backed or physical swarm behavior;
- Alibaba ECS deployment complete;
- Qwen onboard execution.
