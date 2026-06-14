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
- `double-chicane`

It runs four local integer-grid agents for 17 ticks per scenario, persists
agent `DecisionTrace` files, renders each scenario from those persisted traces,
and writes an index page plus canonical JSON summary. The default is 17 because
`double-chicane` needs one more tick than the earlier reviewed obstacle
scenarios.

## Command

```bash
python3 scripts/build_swarm_demo_bundle.py
```

## Result

```text
outcome GO
scenario_count 5
index_sha256 b929f77827e69b9100e9883f78e7b882e7b161d67350a31a129d452f99c63368
wrote runs/demo/swarm/index.html
wrote runs/demo/swarm/summary.json
```

Scenario replay HTML hashes:

```bash
python3 - <<'PY'
import json
from pathlib import Path

summary = json.loads(Path("runs/demo/swarm/summary.json").read_text(encoding="utf-8"))
for case in summary["scenarios"]:
    print(
        case["scenario"],
        case["render_summary"]["outcome"],
        case["render_summary"]["html_sha256"],
    )
PY
```

```text
corridor GO b254699d286bf0edf94c2f522f88c2a30fb242b82e31077b800f2d27e8206bd4
center-block GO 737be22729f58b9d2ec9a5ba82398b20b1859f1f184e5a7bea06d9933129af90
vertical-slalom GO ad881d0b9f0771c0798aa5e7a4f9004c53b7d8fb71d684a08cae8a6b8783ab6f
horizontal-slalom GO 88d2393344cdf159acd18a9588dd779b7a914370e35b9b3b610e901e6e661639
double-chicane GO 06840a1c1c031147d86b9d2c35cf2220425dc905a8fcbeecc845377299098145
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
