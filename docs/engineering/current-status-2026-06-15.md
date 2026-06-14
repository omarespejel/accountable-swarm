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
- Deterministic N=4 vertical-slalom obstacle scenario reaches all goals with
  the bounded reservation planner, reports zero same-cell collisions, zero swap
  collisions, zero obstacle occupancy violations, and replay recomputes those
  counts from traces.
- Deterministic N=4 horizontal-slalom obstacle scenario reaches all goals with
  the bounded reservation planner, reports zero same-cell collisions, zero swap
  collisions, zero obstacle occupancy violations, and replay recomputes those
  counts from traces.
- Low-rate fixture mission assignment validates a strict mission JSON,
  emits a mission `DecisionTrace`, then runs the deterministic N=4 center-block
  swarm gate with zero same-cell, swap, or obstacle occupancy violations.
- Deterministic swarm suite runs six scoped cases, including an expected
  `NARROW_CLAIM` canary, and verifies persisted agent traces from disk.
- Fixed swarm scenario registry centralizes current scenario names, obstacle
  policies, fixed-grid requirements, and reservation-planner use.

## NARROW_CLAIM

- Camera/static-frame gate is live-Qwen GO for a generated static frame, not a
  true webcam frame.
- One true webcam frame with target `person` passed locally after installing
  `imagesnap`, but the artifact is intentionally not committed and no physical
  robot claim follows from it.
- Alibaba ECS manual deploy path is ready, but actual ECS proof is pending.
- Physical-node safety contract exists, but no SO-101 connectivity or safe
  motion is proven.
- The reservation planner result is scoped to the listed fixed integer-grid
  scenarios; it is not evidence for arbitrary maps, larger swarms,
  physics-backed behavior, latency, or reliability.
- The mission assignment gate is fixture-mode GO only. It is not a live Qwen
  mission-assignment claim unless `--mode dashscope` is separately recorded.

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
Ran 63 tests
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

Deterministic N=4 vertical-slalom obstacle gate with bounded reservation
planner:

```text
python3 scripts/run_swarm_sim.py --agents 4 --ticks 16 --scenario vertical-slalom --trace-dir runs/swarm/vertical-slalom-n4 --report-out runs/swarm/vertical_slalom_n4_report.json
outcome GO
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
reroute_count 12
sim-agent-0 summary_sha be89e9a4823f005e1dcf9dfa203d5ca3ab56f46e969700565a5ca51dec413a4b
sim-agent-1 summary_sha 7e7b9a70a5665bf840e53345f1a3c2962ab3312bb5d2632e67c1f497a3802404
sim-agent-2 summary_sha 877e34acd6cd996c95ce256a6b0c23b28f13083306d19e9098e12c79fdc61eb7
sim-agent-3 summary_sha e444e2f6fb11a91b0ac39f8cf2e7a47c96374dda3f3e4395d31a08d3b0eac918
```

Deterministic N=4 horizontal-slalom obstacle gate with bounded reservation
planner:

```text
python3 scripts/run_swarm_sim.py --agents 4 --ticks 16 --scenario horizontal-slalom --trace-dir runs/swarm/horizontal-slalom-n4 --report-out runs/swarm/horizontal_slalom_n4_report.json
outcome GO
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
reroute_count 4
sim-agent-0 summary_sha 594cd7d50b89fa809b251ed2d48deea45d8a066552213a67a66b382d9c606f9f
sim-agent-1 summary_sha fb863f2f87a28b50d5dedb3140fa4e0bc3f5d3b55adf768fb17df027c3bba68f
sim-agent-2 summary_sha 27e4a3de380f54c8653c4bdc2bfb6ed8fdde19eab202c5d1bd91a3902939a2f7
sim-agent-3 summary_sha 4ce9200f856bcffd0cab3f77641dffc3fb937ef5105eafda770340f23761623b
```

Low-rate fixture mission gate:

```text
python3 scripts/run_swarm_mission_gate.py --mode fixture --trace-dir runs/swarm/mission-fixture-n4 --report-out runs/swarm/mission_fixture_n4_report.json
outcome GO
mode fixture
scenario center-block
agent_count 4
mission_trace_summary_sha 82e2138ee3f93e3468ebb04dd179c5c304688cc2ff243dbf129985d56927fcde
sim_report_outcome GO
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
```

Deterministic swarm suite:

```text
python3 scripts/run_swarm_suite.py --trace-root runs/swarm/suite --report-out runs/swarm/suite_report.json
outcome GO
case_count 6
case n2-corridor-go expected GO actual GO
case n2-center-block-go expected GO actual GO
case n4-center-block-go expected GO actual GO
case n4-vertical-slalom-go expected GO actual GO
case n4-horizontal-slalom-go expected GO actual GO
case n4-center-block-short-narrow expected NARROW_CLAIM actual NARROW_CLAIM
```

## Next Work

1. Run the ECS manual deployment path on Alibaba Cloud and record proof.
2. Continue swarm-first work before physical hardware: either live DashScope
   mission assignment or richer simulated scenario fixtures.
3. Keep SO-101 and physical-node work pending until the simulated-swarm GO/NO-GO
   gates are stronger.
4. Convert webcam evidence into a redacted/fixture-safe artifact only if it is
   useful for the hackathon story.

## Non-Claims

Do not claim:

- true webcam capture;
- SO-101 operation;
- physical safety;
- latency or reliability;
- physics-backed or physical swarm behavior;
- live Qwen mission assignment;
- Alibaba ECS deployment complete;
- Qwen onboard execution.
