# Live DashScope Swarm Mission Gate 2026-06-15

Issue: #35

## Thesis

A live DashScope/Qwen text model can provide low-rate mission intent while the
local deterministic swarm runner keeps scenario selection, agent count, tick
budget, planning, and motion authority bounded to reviewed simulator cases.

## Scope

This is a live model evidence gate for `qwen-plus` mission intent only. The live
model response is parsed as an `objective` string. Local code binds the
reviewed scenario, mission id, agent count, and tick budget before running the
deterministic integer-grid simulator.

## Commands

The API key was loaded from local environment state and was not printed or
committed.

```bash
set -a; . ./.env; set +a
python3 scripts/qwen_model_ping.py --models qwen-plus
python3 scripts/run_swarm_mission_gate.py \
  --mode dashscope \
  --model qwen-plus \
  --mission-scenario center-block \
  --trace-dir runs/swarm/live-mission-center-block \
  --report-out runs/swarm/live_mission_center_block_report.json
python3 scripts/verify_trace.py runs/swarm/live-mission-center-block/mission.json
python3 scripts/verify_trace.py runs/swarm/live-mission-center-block/agents/sim-agent-0.json
python3 scripts/verify_trace.py runs/swarm/live-mission-center-block/agents/sim-agent-1.json
python3 scripts/verify_trace.py runs/swarm/live-mission-center-block/agents/sim-agent-2.json
python3 scripts/verify_trace.py runs/swarm/live-mission-center-block/agents/sim-agent-3.json
env -u ALIBABA_API_KEY ./scripts/local_gate.sh
set -a; . ./.env; set +a; ./scripts/local_gate.sh
```

## Observed Output

```text
qwen-plus: OK

outcome GO
mode dashscope
scenario center-block
agent_count 4
mission_trace_summary_sha 5fb552f8dd758c71085cc1a1dfcc9db6f62ab35d39551d97211e306a600ebdb1
sim_report_outcome GO
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
wrote runs/swarm/live-mission-center-block
wrote runs/swarm/live_mission_center_block_report.json

verified runs/swarm/live-mission-center-block/mission.json
summary_sha 5fb552f8dd758c71085cc1a1dfcc9db6f62ab35d39551d97211e306a600ebdb1
verified runs/swarm/live-mission-center-block/agents/sim-agent-0.json
summary_sha 43af1fb934c620bfcd7995bac4538141c59652c7161cd6e577abc796633aa300
verified runs/swarm/live-mission-center-block/agents/sim-agent-1.json
summary_sha 8de4062160df5349f5809b9b58ff18eb7237adcee393c973cc164e1ddbac2284
verified runs/swarm/live-mission-center-block/agents/sim-agent-2.json
summary_sha 2a8bb7802957c6b3e13d42baa5481c5a6cb65dc17619278a8eeaca5502072932
verified runs/swarm/live-mission-center-block/agents/sim-agent-3.json
summary_sha 2bc65322b094a7f13bedbe30ba26181b5134a90f962378a66cb10922cceb9902

./scripts/local_gate.sh
Ran 85 tests
OK
local gate passed
```

The local gate passed both with `ALIBABA_API_KEY` unset and with the local
`.env` loaded. `tests/test_server.py` now explicitly clears the key for the
missing-key endpoint test.

## Report Summary

```text
schema_version swarm-mission-gate-report.v1
outcome GO
mode dashscope
model qwen-plus
mission center-block-n4
mission objective Route all agents to their opposing goals without same-cell, swap, or obstacle occupancy violations.
pass mission_json_validated true
pass mission_trace_replay_deterministic true
pass agent_traces_replay_deterministic true
pass sim_report_go true
pass agent_trace_replay_counts_zero true
sim same_cell_collision_count 0
sim swap_collision_count 0
sim obstacle_occupancy_violation_count 0
replay same_cell_collision_count 0
replay swap_collision_count 0
replay obstacle_occupancy_violation_count 0
```

## GO Gate

This gate is `GO` for the scoped live mission-intent claim:

- `qwen-plus` responded through DashScope.
- The response validated as intent-only mission JSON.
- The reviewed `center-block` scenario, agent count, mission id, and tick budget
  were bound locally.
- The local deterministic simulator returned `GO`.
- Persisted mission and agent traces verified from disk.
- Replay-derived same-cell, swap, and obstacle occupancy counts were zero.

## Non-Claims

- No physical robot behavior.
- No SO-101 operation.
- No 3D physics simulation.
- No latency or reliability claim.
- No DimOS integration.
- No Alibaba ECS deployment proof.
- No Qwen real-time control.
- No arbitrary-map or arbitrary-swarm-size claim.
