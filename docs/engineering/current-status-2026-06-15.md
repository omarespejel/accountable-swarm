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
- Deterministic N=4 center-block obstacle scenario reaches all goals with the
  bounded reservation planner, reports zero same-cell collisions, zero swap
  collisions, zero obstacle occupancy violations, and replay recomputes those
  counts from traces.

## NARROW_CLAIM

- Camera/static-frame gate is live-Qwen GO for a generated static frame, not a
  true webcam frame.
- One true webcam frame with target `person` passed locally after installing
  `imagesnap`, but the artifact is intentionally not committed and no physical
  robot claim follows from it.
- Alibaba ECS manual deploy path is ready, but actual ECS proof is pending.
- Physical-node safety contract exists, but no SO-101 connectivity or safe
  motion is proven.
- The reservation planner result is scoped to the fixed integer-grid
  `center-block` scenario; it is not evidence for arbitrary maps, larger
  swarms, physics-backed behavior, latency, or reliability.

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
Ran 43 tests
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

Deterministic N=4 center-block obstacle gate with bounded reservation planner:

```text
python3 scripts/run_swarm_sim.py --agents 4 --ticks 16 --scenario center-block --trace-dir runs/swarm/reservation-center-block-n4 --report-out runs/swarm/reservation_center_block_n4_report.json
outcome GO
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
reroute_count 11
sim-agent-0 summary_sha 8483b3c9d5009ca9d4b389edbb6b27aa4175cc7b5d4f60845ace327eac652a80
sim-agent-1 summary_sha 69eebbc9173944af9061b39934aa64d5e02cdad944d75f3cc501d5085722a030
sim-agent-2 summary_sha 7486044106f38dc24c83ed2901c028a4e53a829925849a7af11bb1c0abfb0d36
sim-agent-3 summary_sha 2dce3509c5028ab0542ef9e3426b70b49b6f189ed8783ead0e68d48898845f32
```

## Next Work

1. Run the ECS manual deployment path on Alibaba Cloud and record proof.
2. Decide whether the next swarm step is Qwen low-rate mission assignment,
   richer scenario fixtures, or a DimOS adapter sketch.
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
