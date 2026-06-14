# Swarm Trace Visualization 2026-06-15

## Thesis

A judge or teammate should be able to inspect swarm behavior from persisted
`DecisionTrace` artifacts without trusting an unrecorded simulator state. A
deterministic trace-to-HTML renderer strengthens the accountability claim by
turning verified per-agent traces into a static replay artifact and a canonical
JSON summary.

## Scope

This gate renders deterministic integer-grid swarm traces only. It requires
explicit grid dimensions and obstacle coordinates at render time. It does not
run Qwen, does not run DimOS, and does not execute physical hardware.

## Commands

```bash
python3 scripts/run_swarm_sim.py \
  --agents 4 \
  --ticks 16 \
  --scenario center-block \
  --trace-dir runs/swarm/render-center-block \
  --report-out runs/swarm/render_center_block_report.json

python3 scripts/render_swarm_trace_html.py \
  --trace-dir runs/swarm/render-center-block \
  --grid-width 7 \
  --grid-height 5 \
  --obstacle 3,2 \
  --html-out runs/swarm/render-center-block.html \
  --summary-out runs/swarm/render_center_block_visual_summary.json
```

## Result

```text
outcome GO
agent_count 4
tick_count 16
html_sha256 686a328376478bc1bf76b9c59b7ed283f6889d5d48003fdc8928f9f80a231f60
wrote runs/swarm/render-center-block.html
wrote runs/swarm/render_center_block_visual_summary.json
```

The simulator report also returned `GO` for the same run with zero same-cell,
swap, and obstacle-occupancy violations.

## Pass Conditions

- every `*.json` trace in `--trace-dir` loads as a `DecisionTrace`;
- every trace verifies through the local hash-chain verifier before rendering;
- each filename stem matches the trace actor id;
- every trace has the same tick count;
- every trace command is a `grid_step` command matching the requested grid;
- obstacle coordinates are unique and inside the requested grid;
- trace-derived replay reports zero same-cell, swap, and obstacle-occupancy
  violations for the checked center-block case;
- the generated HTML is deterministic across rerenders;
- the generated HTML does not include host-specific temporary paths;
- tampering with a persisted trace fails closed before any HTML or summary is
  written.

## Evidence

Focused test:

```text
python3 -m unittest tests.test_swarm_trace_html_cli
Ran 3 tests
OK
```

Manual render summary:

```text
schema_version swarm-trace-html-report.v1
outcome GO
agent_count 4
tick_count 16
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
html_sha256 686a328376478bc1bf76b9c59b7ed283f6889d5d48003fdc8928f9f80a231f60
```

## Non-Claims

- no physical robot behavior;
- no SO-101 operation;
- no 3D physics simulation;
- no latency or reliability claim;
- no DimOS integration;
- no live Qwen claim;
- no arbitrary-map or larger-swarm claim;
- no cryptographic authenticity claim beyond local hash-chain verification.
