# Swarm Mission Objective Hardening 2026-06-15

## Thesis

Qwen-style mission output must remain low-rate intent, not a hidden command
channel. The parser should reject obvious control metadata even when it is
embedded inside the single allowed `objective` string.

## Why It Matters

The local deterministic runner binds scenario, agent count, tick budget, and
motion authority. If the objective string can smuggle counts, scenario targets,
coordinates, waypoints, setpoints, or actuator terms, a future agent could
misread the trace as Qwen choosing control parameters.

## Change

`MissionSpec` now validates objective text in addition to strict JSON shape.
The validator rejects:

- digits or numeric counts;
- structured-control markers such as `{}`, `[]`, coordinates, or waypoints;
- registered scenario names used as selected targets;
- explicit control terms such as `agent_count`, `mission_id`, `setpoint`,
  `velocity`, `thrust`, `motor`, `command`, or `sim-agent-`.

The prompt also tells Qwen not to include digits. This keeps the only accepted
DashScope mission output as a high-level objective string; local code still
selects every executable field.

## Commands

```text
python3 -m unittest tests.test_swarm_mission tests.test_swarm_mission_gate_cli tests.test_swarm_mission_suite_cli
python3 scripts/run_swarm_mission_suite.py --trace-root runs/swarm/mission-suite --report-out runs/swarm/mission_suite_report.json
env -u ALIBABA_API_KEY ./scripts/local_gate.sh
```

## GO Gate

- Normal intent-only objective text still parses.
- Hidden agent counts, scenario names, coordinates, arrays, and control terms
  are rejected.
- Full fixture mission JSON uses the same objective validator.
- Existing fixture mission suite remains `GO`.
- Local gate remains `GO`.

## Non-Claims

- No live Qwen mission evidence.
- No semantic guarantee for arbitrary natural-language text.
- No physical robot behavior.
- No SO-101 operation.
- No 3D physics simulation.
- No latency or reliability claim.
- No DimOS integration.
