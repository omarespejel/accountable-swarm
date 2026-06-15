# Hazard Formation Gate 2026-06-16

## Thesis

A Qwen-style 2D hazard bbox can be converted into a bounded local formation
planner input without putting Qwen in the control loop. The local planner then
routes four deterministic integer-grid agents into a reviewed formation around
the hazard and records replayable `DecisionTrace` artifacts.

## What Changed

- Added deterministic formation compilation for `surround`, `x`, `line`, and
  `diamond`.
- Added integer-only bbox-center to hazard-cell quantization.
- Added `scripts/run_hazard_formation_gate.py`.
- Added installed command `run-hazard-formation-gate`.
- Added degraded fallback where missing, invalid, or unavailable cloud
  perception emits local hold traces instead of planner motion.

## Commands

Fixture hazard-to-X formation gate:

```bash
python3 -m scripts.run_hazard_formation_gate \
  --image fixtures/hazard_marker.ppm \
  --mode fixture \
  --formation x \
  --trace-dir runs/hazard_formation/smoke_x \
  --report-out runs/hazard_formation/smoke_x_report.json
```

Expected signal:

```text
outcome GO
mode fixture
formation x
```

Degraded fallback:

```bash
python3 -m scripts.run_hazard_formation_gate \
  --image fixtures/hazard_marker.ppm \
  --mode degraded \
  --trace-dir runs/hazard_formation/degraded \
  --report-out runs/hazard_formation/degraded_report.json
```

Expected signal:

```text
outcome DEGRADED
```

## Evidence Boundary

The successful fixture gate shows:

- a validated fixture bbox is quantized to grid cell `{"x": 3, "y": 2}`;
- four agents are assigned to an `x` formation around that hazard;
- the hazard cell is treated as a planner obstacle;
- persisted hazard and agent traces replay deterministically from disk;
- trace-derived same-cell, swap, and obstacle-occupancy counts stay at zero.

The degraded gate shows:

- missing or unavailable cloud perception can be converted into a local hold
  decision;
- each agent emits a replayable hold trace;
- no cloud or physical success claim is needed for fallback behavior.

## Non-Claims

- No physical robot behavior.
- No SO-101 operation.
- No safety claim.
- No latency or reliability claim.
- No 3D grounding.
- No 3D physics simulation.
- No DimOS integration.
- No Qwen real-time control.
- No physical swarm claim.
- No arbitrary-map planner claim.
- No live Qwen hazard-perception claim unless `--mode dashscope` is run and
  recorded separately.

## Validation

```bash
python3 -m unittest tests.test_swarm_formations tests.test_swarm_hazard tests.test_hazard_formation_gate_cli
./scripts/local_gate.sh
```
