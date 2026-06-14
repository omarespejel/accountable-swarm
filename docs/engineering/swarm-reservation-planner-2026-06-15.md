# Swarm Reservation Planner 2026-06-15

## Thesis

A bounded deterministic reservation planner can turn the current N=4
`center-block` obstacle scenario from `NARROW_CLAIM` into `GO` while preserving
the DecisionTrace replay and collision-accounting invariants.

## Prior Boundary

Before this experiment, the N=4 center-block run avoided same-cell collisions,
swap collisions, and obstacle occupancy, but did not reach all four goals:

```text
outcome NARROW_CLAIM
all_goals_reached false
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
```

That made the local guard useful as a safety boundary but not complete enough
for the four-agent obstacle crossing.

## Smallest Falsifying Experiment

Add a bounded deterministic planner that searches a joint integer-grid state
space for the existing four-agent center-block scenario. The planner may use
only integer grid positions, static obstacles, same-cell reservations, and
swap-reservation checks. It must emit the same per-agent `DecisionTrace` shape
as the existing simulator.

## Commands

```bash
python3 -m unittest tests.test_swarm_sim
python3 scripts/run_swarm_sim.py \
  --agents 4 \
  --ticks 16 \
  --scenario center-block \
  --trace-dir runs/swarm/reservation-center-block-n4 \
  --report-out runs/swarm/reservation_center_block_n4_report.json
./scripts/local_gate.sh
```

## Result

```text
outcome GO
agents 4
all_goals_reached true
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
reroute_count 11
hold_count 34
```

Trace summaries:

```text
sim-agent-0 8483b3c9d5009ca9d4b389edbb6b27aa4175cc7b5d4f60845ace327eac652a80
sim-agent-1 69eebbc9173944af9061b39934aa64d5e02cdad944d75f3cc501d5085722a030
sim-agent-2 7486044106f38dc24c83ed2901c028a4e53a829925849a7af11bb1c0abfb0d36
sim-agent-3 2dce3509c5028ab0542ef9e3426b70b49b6f189ed8783ead0e68d48898845f32
```

Trace-derived replay section:

```text
replay.same_cell_collision_count 0
replay.swap_collision_count 0
replay.obstacle_occupancy_violation_count 0
```

Final positions:

```text
sim-agent-0 (6, 2)
sim-agent-1 (0, 2)
sim-agent-2 (3, 4)
sim-agent-3 (3, 0)
```

## Gate

- N=4 `center-block` exits `0`.
- Report records `all_goals_reached true`.
- Report records zero same-cell collisions.
- Report records zero swap collisions.
- Report records zero obstacle occupancy violations.
- Trace-derived replay records zero same-cell, swap, and obstacle occupancy
  violations.
- Report records one 64-hex trace summary per agent.
- Existing N=2 corridor and N=2 center-block gates still pass.
- Expansion-budget exhaustion stays `NARROW_CLAIM`, not `GO`.
- `./scripts/local_gate.sh` passes.

## Non-Claims

- No physical robot behavior.
- No SO-101 operation.
- No real-time latency or reliability claim.
- No 3D physics simulation.
- No DimOS integration.
- No Alibaba deployment proof.
- No learned, optimal, or general-purpose multi-agent planner claim.
- No claim that arbitrary maps or larger swarms are solved.
- No claim that Qwen is in the real-time loop.
