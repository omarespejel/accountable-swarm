# Swarm Scenario Registry 2026-06-15

## Thesis

Fixed swarm scenarios should have one reviewed source of truth for their names,
obstacle policy, fixed-grid requirements, and reservation-planner use.

## Why It Matters

The project is continuing simulated-swarm work before physical hardware. As
scenario count grows, split metadata can create claim drift: the same scenario
name could map to different CLI choices, obstacle layouts, planner behavior, or
evidence boundaries.

## Change

The simulator now keeps current scenario metadata in a small code-owned
registry:

- `corridor`: no obstacle, no reservation planner;
- `center-block`: center obstacle, reservation planner enabled;
- `vertical-slalom`: fixed 7x5 grid, fixed obstacles `(3,1)` and `(3,3)`,
  reservation planner enabled;
- `horizontal-slalom`: fixed 7x5 grid, fixed obstacles `(2,2)` and `(4,2)`,
  reservation planner enabled.

The CLI derives `--scenario` choices from the registry. The old split obstacle
helper was removed, and tests now lock the current registry contents.

## Commands

```text
python3 -m unittest tests.test_swarm_sim tests.test_swarm_suite_cli
python3 scripts/run_swarm_suite.py --trace-root runs/swarm/suite --report-out runs/swarm/suite_report.json
```

Observed:

```text
Ran 24 tests
OK

outcome GO
case_count 6
case n2-corridor-go expected GO actual GO
case n2-center-block-go expected GO actual GO
case n4-center-block-go expected GO actual GO
case n4-vertical-slalom-go expected GO actual GO
case n4-horizontal-slalom-go expected GO actual GO
case n4-center-block-short-narrow expected NARROW_CLAIM actual NARROW_CLAIM
```

## GO Gate

- Scenario metadata has one code-owned source of truth.
- Existing six-case deterministic swarm suite remains `GO`.
- Non-default fixed-scenario grids remain rejected.

## Non-Claims

- No arbitrary-map planning claim.
- No larger-swarm claim.
- No physics-backed or physical robot claim.
- No latency, reliability, or safety claim.
- No live Qwen mission-assignment claim.
