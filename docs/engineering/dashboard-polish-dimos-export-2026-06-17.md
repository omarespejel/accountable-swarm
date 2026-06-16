# Dashboard Polish With DimOS-ready Export 2026-06-17

## Thesis

The judge-facing dashboard should make the accountable control split legible in
one screen: source-frame evidence from Qwen, deterministic local deconfliction,
per-agent `DecisionTrace` inspection, and a claim-safe DimOS-ready export
status.

## Why This Change Exists

The earlier world-model dashboard already proved the data contract and replay
integrity, but it still read like an engineering page. The next step was to
upgrade the same artifact instead of introducing a new surface:

- package the source frame into the dashboard output when a reviewed image is
  available;
- render the source frame and persisted bbox alongside the top-down planner
  state;
- expose a per-agent `DecisionTrace` inspector for the selected tick;
- surface the DimOS bridge-pack status as replay/export evidence only.

This keeps the public artifact stronger without widening claims to 3D physics,
hardware operation, or DimOS execution.

## Commands

```bash
python3 -m unittest \
  tests.test_world_model_dashboard_pack_cli \
  tests.test_world_model_dashboard_renderer_cli \
  tests.test_demo_recording_pack_cli

python3 -m scripts.prepare_demo_recording_pack \
  --out-dir runs/demo/recording-pack-polish-check

./scripts/local_gate.sh
```

## Result

- `scripts.prepare_world_model_dashboard_pack` now accepts:
  - `--source-image`
  - `--dimos-bridge-manifest`
- the dashboard pack copies a reviewed source image into `assets/` and records a
  relative `image.asset_path`;
- the dashboard data contract now includes an optional `dimos_export` summary
  derived from a verified `dimos-bridge-pack-report.v1` manifest;
- `scripts.prepare_demo_recording_pack` now generates a DimOS bridge pack before
  the dashboard pack and threads the manifest into the rendered dashboard;
- the HTML dashboard now shows:
  - a Qwen source-frame pane with the persisted bbox overlay;
  - a per-agent tick selector in the decision list;
  - a `DecisionTrace Inspector` panel with decision, reason, command cells,
    reservations, and predicted conflicts;
  - a `DimOS-ready Export` panel with bridge/runtime/overall outcomes and
    event/scenario counts.

## Evidence

Checked local artifacts:

- `runs/demo/recording-pack-polish-check/manifest.json`
- `runs/demo/recording-pack-polish-check/shotlist.md`
- `runs/dashboard/recording_x/data.json`
- `runs/dashboard/recording_x/index.html`
- `runs/dimos/recording_x_bridge/manifest.json`

The updated dashboard DOM shows all four upgraded surfaces together:

- `Qwen Source Frame`
- `DecisionTrace Inspector`
- `DimOS-ready Export`
- the prior top-down world-model replay

## Non-claims

- no DimOS runtime execution;
- no Rerun recording proof;
- no physical robot behavior or SO-101 operation;
- no 3D physics simulation;
- no learned world model;
- no Qwen real-time control;
- no Alibaba ECS deployment proof.
