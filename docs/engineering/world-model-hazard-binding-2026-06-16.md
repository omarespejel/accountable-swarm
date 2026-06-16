# World Model Hazard Binding 2026-06-16

Issue: #75

## Thesis

The hazard-to-formation gate should not jump directly from a Qwen-style bbox to
motion reports. It should first create an explicit accountable world model that
records the observation, hazard cell, agent cells/goals, reservations, and
deterministic `world_model_sha` values.

## What Changed

- `scripts/run_hazard_formation_gate.py` now writes
  `world_model_timeline.jsonl` inside the trace directory.
- Each timeline row is a canonical `WorldModelState`.
- The hazard formation report now includes a `world_model` section with:
  - timeline path;
  - export trace path and export `DecisionTrace` summary SHA;
  - state count;
  - first and last `world_model_sha`;
  - replay-determinism pass condition;
  - predicted conflict count.
- Each `WorldAgentState` also carries the per-tick `decision_event_sha` for the
  source agent `DecisionEvent`, while preserving the whole-trace
  `decision_trace_sha`.
- Fixture and degraded modes both emit world-model evidence.
- Degraded mode records a `degraded` observation and an empty hazard set while
  preserving safe HOLD behavior.

## Commands

```bash
python3 -m unittest tests.test_hazard_formation_gate_cli tests.test_world_model
python3 -m scripts.run_hazard_formation_gate \
  --image fixtures/hazard_marker.ppm \
  --mode fixture \
  --formation x \
  --trace-dir runs/hazard_formation/world_model_x \
  --report-out runs/hazard_formation/world_model_x_report.json
```

Expected signal:

```text
outcome GO
mode fixture
formation x
```

## Evidence Boundary

This stack layer proves that the existing hazard-formation path emits a
replayable explicit world-model timeline with export provenance. The dashboard
architecture is delivered across issue #75 as a stack: this PR emits the
timeline, the next data-pack layer verifies it against source traces, and the
renderer layer consumes that verified pack.

The current `predicted_conflict_count` is expected to be zero for the reviewed
fixture path. Conflict prediction/heatmap work follows in a separate PR.

## Non-Claims

- No learned world model.
- No physical robot behavior.
- No SO-101 operation.
- No physical swarm claim.
- No 3D physics simulation.
- No DimOS runtime execution or DimOS swarm control.
- No Open-RMF compatibility or regulatory UTM claim.
- No Qwen real-time control.
- No safety, latency, or reliability claim.
