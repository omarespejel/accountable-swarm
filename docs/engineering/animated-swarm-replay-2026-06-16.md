# Animated Swarm Replay 2026-06-16

## Thesis

The existing deterministic swarm demo bundle is strong evidence but weak video
material when presented only as static per-tick thumbnails. A self-contained
animated replay panel strengthens the submission package without expanding the
claim surface: the browser animation is generated from the same verified
`DecisionTrace` timeline and does not add control, planning, physics, or Qwen
authority.

## GO Gate

GO if:

- `scripts/render_swarm_trace_html.py` emits deterministic HTML across reruns;
- the page contains an animated canvas panel, play button, tick slider, and the
  static SVG trace frames;
- the animated panel is driven only by the verified timeline already used for
  static rendering;
- the generated page preserves the explicit non-claim:
  `deterministic 2D trace replay; no DimOS or 3D physics claim`;
- the demo bundle remains reproducible and reports `GO`.

## Commands

```bash
python3 -m unittest tests.test_swarm_trace_html_cli tests.test_swarm_demo_bundle_cli

python3 scripts/build_swarm_demo_bundle.py \
  --out-dir runs/demo/swarm-animated-check

SWARM_DEMO_BUNDLE_DIR="$PWD/runs/demo/swarm-animated-check" \
  python3 scripts/serve_demo.py --host 127.0.0.1 --port 8768
```

Then inspect:

```text
http://127.0.0.1:8768/swarm-demo/scenarios/center-block/replay.html
```

## Evidence

Local targeted validation:

```text
python3 -m unittest tests.test_swarm_trace_html_cli tests.test_swarm_demo_bundle_cli
# Ran 7 tests OK

git diff --check
```

Generated bundle smoke:

```text
python3 scripts/build_swarm_demo_bundle.py --out-dir runs/demo/swarm-animated-check
outcome GO
scenario_count 5
wrote runs/demo/swarm-animated-check/index.html
wrote runs/demo/swarm-animated-check/summary.json
```

Browser inspection through the local stdlib server showed:

```text
Replay panel present
Play button present
Tick slider present
Scope text present: deterministic 2D trace replay; no DimOS or 3D physics claim
Console error count: 0
```

## Non-Claims

- no physical robot behavior;
- no SO-101 operation;
- no 3D physics simulation;
- no DimOS integration;
- no live Qwen control;
- no latency or reliability claim;
- no arbitrary-map or larger-swarm claim;
- no video export pipeline claim.

