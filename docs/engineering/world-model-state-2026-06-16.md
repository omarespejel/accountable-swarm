# World Model State 2026-06-16

Issue: #75

## Thesis

The swarm dashboard needs a first-class truth artifact between Qwen evidence and
rendered motion. `WorldModelState` is that artifact: a canonical, explicit,
integer-only belief state that records observations, hazards, agent cells,
goals, reservations, predicted conflicts, and a deterministic `world_model_sha`.

This is not a learned world model or a physics simulator. It is an accountable
state ledger for visualizing and auditing local deconfliction decisions.

## What Changed

- Added `accountable_swarm/world_model.py`.
- Added `WorldObservation`, `WorldAgentState`, `WorldReservation`,
  `PredictedConflict`, and `WorldModelState`.
- Added deterministic world-model hashing via existing trace canonical JSON
  utilities.
- Added explicit rejection of raw floats and booleans in hashed world-model
  payloads.
- Added loader/verifier helpers for replaying persisted world-model JSON.
- Added tests for hash replay, order stability, tamper rejection, malformed
  observations, duplicate agents/reservations, out-of-bounds cells, invalid
  observation sources, invalid conflicts, and raw scalar rejection.

## Commands

```bash
python3 -m unittest tests.test_world_model
```

Expected signal:

```text
Ran 12 tests
OK
```

Full repository validation remains:

```bash
./scripts/local_gate.sh
```

## Evidence Boundary

This first PR proves only the world-model data contract. It does not yet bind
Qwen hazard output into the planner, emit a world-model timeline, or render a
dashboard. Those follow in #75.

## Non-Claims

- No learned world model.
- No video-generation model.
- No physical robot behavior.
- No SO-101 operation.
- No physical swarm claim.
- No 3D physics simulation.
- No DimOS runtime execution or DimOS swarm control.
- No Open-RMF compatibility or regulatory UTM claim.
- No Qwen real-time control.
- No safety, latency, or reliability claim.
