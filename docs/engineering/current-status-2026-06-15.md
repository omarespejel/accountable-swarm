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
- Minimal stdlib HTTP server serves existing deterministic swarm demo bundle
  artifacts through path-safe `/swarm-demo` endpoints.
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
  emits a mission `DecisionTrace`, then runs deterministic N=4 center-block and
  horizontal-slalom swarm gates with zero same-cell, swap, or obstacle occupancy
  violations.
- Live `qwen-plus` DashScope mission assignment validates an intent-only
  objective for the reviewed `center-block` scenario, emits a mission
  `DecisionTrace`, then runs the deterministic N=4 center-block swarm gate with
  zero same-cell, swap, or obstacle occupancy violations.
- Live `qwen-plus` DashScope mission suite validates intent-only objectives for
  every reviewed scenario-registry name, emits mission `DecisionTrace`
  artifacts, runs deterministic N=4 local swarm gates, verifies persisted
  mission and agent traces from disk, and reports zero same-cell, swap, or
  obstacle occupancy violations for each case.
- Fixture swarm mission suite runs the mission binding path for every reviewed
  scenario-registry name, with persisted mission and agent traces replayed from
  disk. Child mission-gate or artifact failures now emit a suite
  `NARROW_CLAIM` report instead of raw stderr/stdout excerpts.
- Swarm mission-suite trace verifier reports `GO` for clean persisted mission
  and agent traces, and reports `NARROW_CLAIM` after a copied agent trace is
  mutated without recomputing the hash chain.
- Deterministic swarm suite runs six scoped cases, including an expected
  `NARROW_CLAIM` canary, and verifies persisted agent traces from disk.
- Fixed swarm scenario registry centralizes current scenario names, obstacle
  policies, fixed-grid requirements, and reservation-planner use.
- Deterministic swarm trace visualization emits a static HTML/SVG replay and
  canonical summary from verified persisted N=4 center-block traces, with zero
  same-cell, swap, and obstacle-occupancy violations.
- One-command deterministic swarm demo bundle generates scenario reports,
  verified agent traces, static HTML/SVG replays, and a deterministic index
  for every reviewed scenario-registry name.

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
- The live mission assignment evidence is scoped to `qwen-plus` and the
  reviewed scenario registry: `corridor`, `center-block`, `vertical-slalom`,
  and `horizontal-slalom`. It is not an arbitrary mission, arbitrary-map, or
  real-time-control claim.
- The tamper gate is local hash-chain verification only. It is not a
  cryptographic authenticity, remote attestation, or compromised-filesystem
  claim.
- The swarm trace visualization is an inspection artifact over persisted
  integer-grid traces. It is not a physics, hardware, live-Qwen, latency,
  reliability, arbitrary-map, or larger-swarm claim.
- The swarm demo bundle is the current judge-friendly local simulation path.
  It is not evidence for physical robot behavior, SO-101 operation, 3D
  physics, live Qwen reasoning, latency, reliability, DimOS integration,
  arbitrary maps, or larger swarms.
- The swarm demo server endpoints serve existing local files only. They are not
  Alibaba ECS deployment proof and do not generate, mutate, or validate a
  bundle on request.

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
Ran 101 tests
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
curl -fsS http://127.0.0.1:8765/healthz
GET /healthz -> {"service":"accountable-swarm","status":"ok"}
curl -fsS http://127.0.0.1:8765/readyz
GET /readyz -> {"default_vl_model":"qwen3-vl-flash","has_alibaba_api_key":true,"status":"ok"}
curl -fsS http://127.0.0.1:8765/camera-fixture
GET /camera-fixture -> trace_summary_sha 282a7982facaf066732b4a3dd1039529e0c8e5b8d54b2b1d458b0b8b7c6e5d2a
curl -fsS "http://127.0.0.1:8765/qwen-ping?model=qwen-plus"
GET /qwen-ping?model=qwen-plus -> {"content_prefix":"OK.","model":"qwen-plus","status":"ok"}
curl -fsS http://127.0.0.1:8765/swarm-demo
GET /swarm-demo -> existing bundle index.html
curl -fsS http://127.0.0.1:8765/swarm-demo/summary.json
GET /swarm-demo/summary.json -> existing bundle summary.json
```

Deterministic swarm trace visualization:

```text
python3 scripts/render_swarm_trace_html.py --trace-dir runs/swarm/render-center-block --grid-width 7 --grid-height 5 --obstacle 3,2 --html-out runs/swarm/render-center-block.html --summary-out runs/swarm/render_center_block_visual_summary.json
outcome GO
agent_count 4
tick_count 16
html_sha256 686a328376478bc1bf76b9c59b7ed283f6889d5d48003fdc8928f9f80a231f60
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
```

One-command deterministic swarm demo bundle:

```text
python3 scripts/build_swarm_demo_bundle.py
outcome GO
scenario_count 4
index_sha256 8ed23bca34358627a9948b49d265c28cd7433997e39578c62b911e5ee333f688
```

```text
python3 - <<'PY'
import json
from pathlib import Path

summary = json.loads(Path("runs/demo/swarm/summary.json").read_text(encoding="utf-8"))
for case in summary["scenarios"]:
    print(case["scenario"], case["render_summary"]["outcome"], case["render_summary"]["html_sha256"])
PY
corridor GO 69321792e399a9313e7062655b93c408ee9ea8d379f3810149f3ce291f79ad35
center-block GO 0a6b66dca4e478628b9c91880b40f1b0097391c534c3d7407736ff7c67815f66
vertical-slalom GO 83d6fd2c622a61f6fd65b23c9a70375321ffb856a55c6b76190c5149dd11e04b
horizontal-slalom GO 20587a02144999f625062b2fc8f359aacf6cfc288aff63fbacf7f06ea72e01a6
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

Registry-bound horizontal-slalom fixture mission gate:

```text
python3 scripts/run_swarm_mission_gate.py --mode fixture --mission-scenario horizontal-slalom --trace-dir runs/swarm/mission-horizontal-slalom-fixture-n4 --report-out runs/swarm/mission_horizontal_slalom_fixture_n4_report.json
outcome GO
mode fixture
scenario horizontal-slalom
agent_count 4
mission_trace_summary_sha 2a75abfc4cdf17f903f80787c23689819b2af4b891ae0e8113c5c8a1232f849a
sim_report_outcome GO
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
```

Fixture swarm mission suite:

```text
python3 scripts/run_swarm_mission_suite.py --trace-root runs/swarm/mission-suite --report-out runs/swarm/mission_suite_report.json
outcome GO
case_count 4
case mission-corridor-fixture-n4-go scenario corridor expected GO actual GO
case mission-center-block-fixture-n4-go scenario center-block expected GO actual GO
case mission-vertical-slalom-fixture-n4-go scenario vertical-slalom expected GO actual GO
case mission-horizontal-slalom-fixture-n4-go scenario horizontal-slalom expected GO actual GO
```

Swarm mission-suite trace verifier:

```text
python3 scripts/verify_swarm_mission_suite.py --trace-root runs/swarm/tamper-clean --report runs/swarm/tamper_clean_report.json --report-out runs/swarm/tamper_clean_verify_report.json
outcome GO
case_count 4
case mission-corridor-fixture-n4-go actual GO verified True
case mission-center-block-fixture-n4-go actual GO verified True
case mission-vertical-slalom-fixture-n4-go actual GO verified True
case mission-horizontal-slalom-fixture-n4-go actual GO verified True

python3 scripts/verify_swarm_mission_suite.py --trace-root runs/swarm/tamper-agent --report runs/swarm/tamper_clean_report.json --report-out runs/swarm/tamper_agent_verify_report.json
outcome NARROW_CLAIM
case_count 4
case mission-corridor-fixture-n4-go actual GO verified False
case mission-center-block-fixture-n4-go actual GO verified True
case mission-vertical-slalom-fixture-n4-go actual GO verified True
case mission-horizontal-slalom-fixture-n4-go actual GO verified True
failed_trace_kinds agent:sim-agent-0
```

Live DashScope mission gate:

```text
python3 scripts/qwen_model_ping.py --models qwen-plus
qwen-plus: OK

python3 scripts/run_swarm_mission_gate.py --mode dashscope --model qwen-plus --mission-scenario center-block --trace-dir runs/swarm/live-mission-center-block --report-out runs/swarm/live_mission_center_block_report.json
outcome GO
mode dashscope
scenario center-block
agent_count 4
mission_trace_summary_sha 5fb552f8dd758c71085cc1a1dfcc9db6f62ab35d39551d97211e306a600ebdb1
sim_report_outcome GO
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0

python3 scripts/verify_trace.py runs/swarm/live-mission-center-block/mission.json
summary_sha 5fb552f8dd758c71085cc1a1dfcc9db6f62ab35d39551d97211e306a600ebdb1
```

Live DashScope mission suite:

```text
python3 scripts/run_swarm_mission_suite.py --mode dashscope --model qwen-plus --trace-root runs/swarm/live-mission-suite --report-out runs/swarm/live_mission_suite_report.json
outcome GO
mode dashscope
model qwen-plus
case_count 4
case mission-corridor-dashscope-qwen-plus-n4-go scenario corridor expected GO actual GO
case mission-center-block-dashscope-qwen-plus-n4-go scenario center-block expected GO actual GO
case mission-vertical-slalom-dashscope-qwen-plus-n4-go scenario vertical-slalom expected GO actual GO
case mission-horizontal-slalom-dashscope-qwen-plus-n4-go scenario horizontal-slalom expected GO actual GO

python3 scripts/verify_swarm_mission_suite.py --trace-root runs/swarm/live-mission-suite --report runs/swarm/live_mission_suite_report.json --report-out runs/swarm/live_mission_suite_verify_report.json
outcome GO
case_count 4
case mission-corridor-dashscope-qwen-plus-n4-go actual GO verified True
case mission-center-block-dashscope-qwen-plus-n4-go actual GO verified True
case mission-vertical-slalom-dashscope-qwen-plus-n4-go actual GO verified True
case mission-horizontal-slalom-dashscope-qwen-plus-n4-go actual GO verified True
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
2. Continue swarm-first work before physical hardware with richer simulated
   scenario fixtures, trace visualization, or suite-level negative live-model
   parser hardening.
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
- live Qwen mission assignment beyond the scoped `qwen-plus` reviewed-scenario
  suite evidence;
- Alibaba ECS deployment complete;
- Qwen onboard execution.
