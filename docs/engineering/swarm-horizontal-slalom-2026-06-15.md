# Swarm Horizontal Slalom 2026-06-15

## Thesis

A third fixed obstacle layout can strengthen the simulated-swarm evidence
without broadening into arbitrary maps. The `horizontal-slalom` scenario is
still a deterministic integer-grid case, not a physics or hardware claim.

## Scenario

The scenario uses the existing 7x5 grid, existing four-agent start/goal layout,
and two static obstacles across the center row:

```text
(2, 2)
(4, 2)
```

This complements `vertical-slalom`, which places obstacles in the center
column. The bounded reservation planner remains the local motion authority.
Qwen is not in the control loop.

## Commands

```bash
python3 -m unittest tests.test_swarm_sim tests.test_swarm_suite_cli
python3 scripts/run_swarm_sim.py \
  --agents 4 \
  --ticks 16 \
  --scenario horizontal-slalom \
  --trace-dir runs/swarm/horizontal-slalom-n4 \
  --report-out runs/swarm/horizontal_slalom_n4_report.json
python3 scripts/run_swarm_suite.py \
  --trace-root runs/swarm/suite \
  --report-out runs/swarm/suite_report.json
./scripts/local_gate.sh
```

## Result

```text
outcome GO
agents 4
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
reroute_count 4
```

Report fields:

```text
all_goals_reached true
hold_count 38
final sim-agent-0 (6, 2)
final sim-agent-1 (0, 2)
final sim-agent-2 (3, 4)
final sim-agent-3 (3, 0)
replay.ticks_replayed 16
replay.same_cell_collision_count 0
replay.swap_collision_count 0
replay.obstacle_occupancy_violation_count 0
```

Trace summaries for the single-scenario command:

```text
sim-agent-0 594cd7d50b89fa809b251ed2d48deea45d8a066552213a67a66b382d9c606f9f
sim-agent-1 fb863f2f87a28b50d5dedb3140fa4e0bc3f5d3b55adf768fb17df027c3bba68f
sim-agent-2 27e4a3de380f54c8653c4bdc2bfb6ed8fdde19eab202c5d1bd91a3902939a2f7
sim-agent-3 4ce9200f856bcffd0cab3f77641dffc3fb937ef5105eafda770340f23761623b
```

## Suite Evidence

The deterministic swarm suite now includes:

```text
case n4-horizontal-slalom-go expected GO actual GO
```

Suite trace summaries for `n4-horizontal-slalom-go`:

```text
sim-agent-0 237440225ca798fc797f80791d9240b0b17d6ab62d4b2d55af88358a121ceaec
sim-agent-1 397f73e8b798779a3e2292252545c1ab56710bc515e5a2be10fbb9a67ac3ce3a
sim-agent-2 8d93ed711be9d41e1c29e513d16c65d0323d587a5df3d59b5b35f86bfc2899f6
sim-agent-3 5e9fa5167936787d3488f8996941fb4ce4a96a542a7662e7ab990b0cb7e161ef
```

## GO Gate

- `horizontal-slalom` is a named, fixed scenario.
- N=4, 16-tick run reports `GO`.
- All four agents reach goals.
- Simulator and trace replay report zero same-cell collisions, zero swap
  collisions, and zero obstacle occupancy violations.
- Suite includes the new expected-GO case.
- Non-fixed grid sizes are rejected.
- `./scripts/local_gate.sh` passes.

## Non-Claims

- No physical robot behavior.
- No SO-101 operation.
- No 3D physics simulation.
- No live Qwen mission assignment.
- No latency or reliability claim.
- No DimOS integration.
- No arbitrary-map planner claim.
- No larger-swarm claim beyond the listed deterministic integer-grid cases.
