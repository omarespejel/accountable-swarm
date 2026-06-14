# Swarm Vertical Slalom 2026-06-15

## Thesis

A second fixed obstacle layout can strengthen the simulated-swarm evidence
without broadening into arbitrary maps. The `vertical-slalom` scenario is still
a deterministic integer-grid case, not a physics or hardware claim.

## Scenario

The scenario uses the existing 7x5 grid, existing four-agent start/goal layout,
and two static obstacles:

```text
(3, 1)
(3, 3)
```

The bounded reservation planner remains the local motion authority. Qwen is not
in the control loop.

## Commands

```bash
python3 -m unittest tests.test_swarm_sim tests.test_swarm_suite_cli
python3 scripts/run_swarm_sim.py \
  --agents 4 \
  --ticks 16 \
  --scenario vertical-slalom \
  --trace-dir runs/swarm/vertical-slalom-n4 \
  --report-out runs/swarm/vertical_slalom_n4_report.json
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
reroute_count 12
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
sim-agent-0 be89e9a4823f005e1dcf9dfa203d5ca3ab56f46e969700565a5ca51dec413a4b
sim-agent-1 7e7b9a70a5665bf840e53345f1a3c2962ab3312bb5d2632e67c1f497a3802404
sim-agent-2 877e34acd6cd996c95ce256a6b0c23b28f13083306d19e9098e12c79fdc61eb7
sim-agent-3 e444e2f6fb11a91b0ac39f8cf2e7a47c96374dda3f3e4395d31a08d3b0eac918
```

## Suite Evidence

The deterministic swarm suite now includes:

```text
case n4-vertical-slalom-go expected GO actual GO
```

Suite trace summaries for `n4-vertical-slalom-go`:

```text
sim-agent-0 1167514b0a9701f51e98cfd9803e7ef076127209c40e32c90dd437ab5472e4ef
sim-agent-1 ebf15386eae44d9d026aaf96cfec1ff98c0a54c300035679b5fbbfa4d00e898d
sim-agent-2 eae8cbbbadace55a4e99cca4f71ec982fcd34545758f42f4ce23ad861cd98f6c
sim-agent-3 1ab461c6c6673c47541280dc895bff4a3a8d541e61fce5acc74d27c5f119e66d
```

## GO Gate

- `vertical-slalom` is a named, fixed scenario.
- N=4, 16-tick run reports `GO`.
- All four agents reach goals.
- Simulator and trace replay report zero same-cell collisions, zero swap
  collisions, and zero obstacle occupancy violations.
- Suite includes the new expected-GO case.
- Unknown scenarios are still rejected.
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
