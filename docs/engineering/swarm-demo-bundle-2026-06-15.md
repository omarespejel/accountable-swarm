# Swarm Demo Bundle 2026-06-15

## Thesis

A reviewer should be able to run one local command and get a complete
deterministic swarm demo bundle: scenario reports, verified agent traces,
static HTML/SVG replays, and a bundle summary. This improves the hackathon
submission path without introducing physical hardware, cloud state, or hidden
simulator state.

## Scope

The bundle covers the reviewed deterministic scenario registry:

- `corridor`
- `center-block`
- `vertical-slalom`
- `horizontal-slalom`

It runs four local integer-grid agents for 16 ticks per scenario, persists
agent `DecisionTrace` files, renders each scenario from those persisted traces,
and writes an index page plus canonical JSON summary.

## Command

```bash
python3 scripts/build_swarm_demo_bundle.py
```

## Result

```text
outcome GO
scenario_count 4
index_sha256 8ed23bca34358627a9948b49d265c28cd7433997e39578c62b911e5ee333f688
wrote runs/demo/swarm/index.html
wrote runs/demo/swarm/summary.json
```

Scenario replay HTML hashes:

```text
corridor            69321792e399a9313e7062655b93c408ee9ea8d379f3810149f3ce291f79ad35
center-block        0a6b66dca4e478628b9c91880b40f1b0097391c534c3d7407736ff7c67815f66
vertical-slalom     83d6fd2c622a61f6fd65b23c9a70375321ffb856a55c6b76190c5149dd11e04b
horizontal-slalom   20587a02144999f625062b2fc8f359aacf6cfc288aff63fbacf7f06ea72e01a6
```

Every scenario report returned `GO` with zero same-cell, swap, and
obstacle-occupancy violations.

## Pass Conditions

- every reviewed deterministic scenario is included;
- every child simulation report is `GO`;
- every child render summary is `GO`;
- every persisted trace verifies through the renderer before HTML is written;
- trace-derived replay counts are zero for same-cell, swap, and
  obstacle-occupancy violations;
- generated file paths in `summary.json` are relative to the bundle root;
- generated `index.html` and `summary.json` contain no host-specific absolute
  paths;
- rerunning the command in separate temp directories produces identical index
  HTML and summary JSON;
- a too-short scenario run returns non-zero and records `NARROW_CLAIM`.

## Evidence

Focused test:

```text
python3 -m unittest tests.test_swarm_demo_bundle_cli
Ran 4 tests
OK
```

Manual host-path check:

```text
grep -R "/Users/espejelomar\|/var/folders\|/tmp" -n runs/demo/swarm/index.html runs/demo/swarm/summary.json || true
```

No matches were returned.

## Non-Claims

- no physical robot behavior;
- no SO-101 operation;
- no 3D physics simulation;
- no live Qwen claim;
- no latency or reliability claim;
- no DimOS integration;
- no arbitrary-map or larger-swarm claim.
