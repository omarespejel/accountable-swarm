# Swarm Mission Gate 2026-06-15

## Thesis

A low-rate Qwen-style mission assignment can be validated into a bounded local
swarm run without putting Qwen in the real-time control loop. The local
deterministic simulator remains the only motion authority.

## Scope

This gate uses fixture mode as the checked GO path. DashScope mode is wired to
the same strict parser, but no live Qwen mission-assignment claim is made until
a live run is separately recorded.

## Mission Contract

The accepted mission response is a strict JSON object with exactly these keys:

```text
schema_version
mission_id
scenario
agent_count
ticks
objective
```

Validation rejects malformed JSON, extra keys, unsupported scenarios,
unsupported agent counts, raw floats, boolean-as-integer fields, and unsafe
tick budgets.

## Commands

```bash
python3 -m unittest tests.test_swarm_mission tests.test_swarm_mission_gate_cli
python3 scripts/run_swarm_mission_gate.py \
  --mode fixture \
  --trace-dir runs/swarm/mission-fixture-n4 \
  --report-out runs/swarm/mission_fixture_n4_report.json
./scripts/local_gate.sh
```

## Result

```text
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

Agent trace summaries:

```text
sim-agent-0 43af1fb934c620bfcd7995bac4538141c59652c7161cd6e577abc796633aa300
sim-agent-1 8de4062160df5349f5809b9b58ff18eb7237adcee393c973cc164e1ddbac2284
sim-agent-2 2a8bb7802957c6b3e13d42baa5481c5a6cb65dc17619278a8eeaca5502072932
sim-agent-3 2bc65322b094a7f13bedbe30ba26181b5134a90f962378a66cb10922cceb9902
```

Pass conditions:

```text
mission_json_validated true
mission_trace_replay_deterministic true
agent_traces_replay_deterministic true
sim_report_go true
agent_trace_replay_counts_zero true
```

## GO Gate

- Fixture mission JSON validates.
- Mission trace verifies and replays to the same summary SHA.
- Local deterministic simulator runs only after validation.
- Simulator report outcome is `GO`.
- Per-agent traces verify.
- Trace-derived replay records zero same-cell collisions, zero swap collisions,
  and zero obstacle occupancy violations.
- `./scripts/local_gate.sh` passes.

## Non-Claims

- No physical robot behavior.
- No SO-101 operation.
- No 3D physics simulation.
- No latency or reliability claim.
- No DimOS integration.
- No Alibaba deployment proof.
- No learned policy.
- No arbitrary-map or larger-swarm solution.
- No claim that Qwen is in the real-time loop.
- No live Qwen mission-assignment claim.
