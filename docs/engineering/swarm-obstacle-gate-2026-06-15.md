# Swarm Obstacle Gate 2026-06-15

## Thesis

A deterministic static-obstacle scenario can strengthen the simulated swarm gate
by proving that local `MOVE`, `REROUTE`, and `HOLD` guards avoid both other
agents and blocked grid cells while preserving replayable DecisionTrace
evidence.

## Smallest Falsifying Experiment

Place a blocked center cell at `(3, 2)` in the current integer grid and run the
N=2 corridor crossing scenario long enough to force both agents off their direct
paths.

## Commands

```bash
python3 scripts/run_swarm_sim.py \
  --agents 2 \
  --ticks 9 \
  --scenario center-block \
  --trace-dir runs/swarm/center-block-n2-replay \
  --report-out runs/swarm/center_block_n2_replay_report.json
python3 -m unittest discover -s tests
./scripts/local_gate.sh
```

## Result

```text
outcome GO
agents 2
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
reroute_count 2
sim-agent-0 summary_sha 972e065c57ce1fa897dadeb940a61350ff4941981da0ba0f2a7ff377d65ebca0
sim-agent-1 summary_sha 34ebe9efad6276c48d2a076c3630482c06b0cbf977c950849df2a35f4bc68cc3
```

The report includes a trace-derived replay section:

```text
replay.same_cell_collision_count 0
replay.swap_collision_count 0
replay.obstacle_occupancy_violation_count 0
```

## N4 Exploratory Boundary

The original local-guard-only center-block obstacle scenario with four agents
was a `NARROW_CLAIM`:

```bash
python3 scripts/run_swarm_sim.py \
  --agents 4 \
  --ticks 20 \
  --scenario center-block \
  --trace-dir runs/swarm/center-block-n4-t20 \
  --report-out runs/swarm/center_block_n4_t20_report.json
```

```text
outcome NARROW_CLAIM
all_goals_reached false
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
reroute_count 56
```

This means the simple local guard avoids collision and obstacle occupancy but
is not a complete planner for four agents around a central obstacle. The
follow-up bounded reservation planner result is recorded in
`docs/engineering/swarm-reservation-planner-2026-06-15.md`.

## GO Gate

- N=2 `center-block` exits `0`.
- Report records at least two reroutes.
- Report records zero same-cell collisions.
- Report records zero swap collisions.
- Report records zero obstacle occupancy violations.
- Trace-derived replay records zero same-cell, swap, and obstacle occupancy
  violations.
- `./scripts/local_gate.sh` passes.

## Qodo Review Remediation

Qodo flagged four hardening points on PR #14:

- report JSON obstacles are dicts, while replay originally expected
  `GridPoint` objects;
- unsupported scenario validation needed a negative test;
- replay should enforce `summary_sha` verification, not only event-chain shape;
- the sequential guard needed to avoid reserving an unprocessed agent's current
  cell as a fallback edge case.

The implementation now normalizes replay obstacles from either `GridPoint` or
`{"x": int, "y": int}` dictionaries, calls `verify_trace()` inside replay,
adds negative scenario and unsigned-trace tests, and prevents earlier agents
from reserving later agents' current cells.

## CodeRabbit Review Remediation

CodeRabbit flagged two actionable items on PR #14:

- `replay_swarm_traces()` should require explicit obstacle context, even when
  the caller supplies an empty tuple;
- the engineering note should use the repo-standard `python3 -m unittest
  discover -s tests` command.

Both were applied before merge.

## Non-Claims

- No physical robot behavior.
- No SO-101 operation.
- No real-time latency or reliability claim.
- No 3D physics simulation.
- No DimOS integration.
- No Alibaba deployment proof.
- No learned, optimal, or complete multi-agent planner claim.
