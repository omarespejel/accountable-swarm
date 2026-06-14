# Swarm Double-Chicane Scenario 2026-06-15

## Thesis

A fixed five-obstacle `double-chicane` scenario can strengthen the
deterministic swarm demo without widening the claim beyond reviewed
integer-grid scenarios. The scenario should pass at its reviewed tick budget
and stay `NARROW_CLAIM` when run one tick short.

## Scenario

The reviewed layout uses the fixed `7x5` grid with obstacles at:

```text
(2,1), (3,1), (4,2), (3,3), (2,3)
```

The scenario uses the bounded deterministic reservation planner. Its reviewed
default budget is 17 ticks. A 16-tick run is intentionally not enough for all
agents to reach their goals, and that boundary is tested.

## Commands

Focused unit tests:

```bash
python3 -m unittest tests.test_swarm_sim tests.test_swarm_suite_cli tests.test_swarm_mission tests.test_swarm_mission_suite_cli tests.test_swarm_demo_bundle_cli
```

Observed:

```text
Ran 58 tests in 113.230s
OK
```

Direct GO/NARROW boundary:

```bash
python3 scripts/run_swarm_sim.py \
  --agents 4 \
  --ticks 17 \
  --scenario double-chicane \
  --trace-dir runs/swarm/double-chicane-n4 \
  --report-out runs/swarm/double_chicane_n4_report.json
python3 scripts/run_swarm_sim.py \
  --agents 4 \
  --ticks 16 \
  --scenario double-chicane \
  --trace-dir runs/swarm/double-chicane-n4-short \
  --report-out runs/swarm/double_chicane_n4_short_report.json
```

Observed:

```text
outcome GO
agents 4
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
reroute_count 23

outcome NARROW_CLAIM
agents 4
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
reroute_count 23
```

Scenario suite:

```bash
python3 scripts/run_swarm_suite.py \
  --trace-root runs/swarm/suite \
  --report-out runs/swarm/suite_report.json
```

Observed:

```text
outcome GO
case_count 7
case n2-corridor-go expected GO actual GO
case n2-center-block-go expected GO actual GO
case n4-center-block-go expected GO actual GO
case n4-vertical-slalom-go expected GO actual GO
case n4-horizontal-slalom-go expected GO actual GO
case n4-double-chicane-go expected GO actual GO
case n4-center-block-short-narrow expected NARROW_CLAIM actual NARROW_CLAIM
```

`n4-double-chicane-go` trace summary SHAs:

```text
sim-agent-0 d63c0b106d53a9912ededf15f0d74b08670311c164be07f9da797cdc95ef4612
sim-agent-1 b071b8a80e76f301d4ce94b75965026d47d84f1b1ad67793c77927fc207051d0
sim-agent-2 40c9c96e83ce5648765937dabdcdfc74f02aca38394c5348f73c1376739755fe
sim-agent-3 6e86d52772fde0826446122a71409781b5b74f6567a3b8158d97c16983646446
```

Demo bundle:

```bash
python3 scripts/build_swarm_demo_bundle.py --out-dir runs/demo/swarm
```

Observed:

```text
outcome GO
scenario_count 5
index_sha256 b929f77827e69b9100e9883f78e7b882e7b161d67350a31a129d452f99c63368
wrote runs/demo/swarm/index.html
wrote runs/demo/swarm/summary.json
```

Scenario replay HTML hashes:

```text
corridor GO b254699d286bf0edf94c2f522f88c2a30fb242b82e31077b800f2d27e8206bd4
center-block GO 737be22729f58b9d2ec9a5ba82398b20b1859f1f184e5a7bea06d9933129af90
vertical-slalom GO ad881d0b9f0771c0798aa5e7a4f9004c53b7d8fb71d684a08cae8a6b8783ab6f
horizontal-slalom GO 88d2393344cdf159acd18a9588dd779b7a914370e35b9b3b610e901e6e661639
double-chicane GO 06840a1c1c031147d86b9d2c35cf2220425dc905a8fcbeecc845377299098145
```

## GO Gate

- `double-chicane` is present in the reviewed scenario registry.
- The fixed grid and obstacle coordinates are locked by unit tests.
- A 17-tick N=4 run reports `GO`.
- A 16-tick N=4 run reports `NARROW_CLAIM`.
- Persisted traces replay with zero same-cell collisions, zero swap
  collisions, and zero obstacle-occupancy violations.
- The scenario suite and demo bundle remain `GO`.

## Non-Claims

- No physical robot behavior.
- No SO-101 operation.
- No 3D physics simulation.
- No live Qwen mission assignment.
- No latency or reliability claim.
- No DimOS integration.
- No arbitrary-map planner claim.
- No larger-swarm claim beyond the listed deterministic integer-grid cases.
