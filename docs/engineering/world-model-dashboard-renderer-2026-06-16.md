# World-Model Dashboard Renderer

Date: 2026-06-16

Issue: [#75](https://github.com/omarespejel/accountable-swarm/issues/75)

## Thesis

The demo needs a recordable visual that makes the accountability chain visible:
Qwen keyframe evidence, deterministic local planning, world-model hashes, and
per-agent `DecisionTrace` event hashes. The renderer should consume only the
verified dashboard data pack, not loose simulator files.

## Change

- Added `scripts.render_world_model_dashboard_html`.
- Added the installed entrypoint `render-world-model-dashboard-html`.
- Added a renderer report schema, `world-model-dashboard-html-report.v1`.
- Rendered a self-contained interactive HTML dashboard from
  `world-model-dashboard-data.v1`.
- Validated that world-model event hashes remain bound to source agent event
  hashes before rendering.
- Rejected unsupported schemas, raw floats, absolute paths, and secret-looking
  payloads.

## GO Gate

```bash
python3 -m scripts.run_hazard_formation_gate \
  --image fixtures/hazard_marker.ppm \
  --mode fixture \
  --formation x \
  --trace-dir runs/hazard_formation/world_model_x \
  --report-out runs/hazard_formation/world_model_x_report.json

python3 -m scripts.prepare_world_model_dashboard_pack \
  --trace-dir runs/hazard_formation/world_model_x \
  --hazard-report runs/hazard_formation/world_model_x_report.json \
  --out-dir runs/dashboard/world_model_x

python3 -m scripts.render_world_model_dashboard_html \
  --data runs/dashboard/world_model_x/data.json \
  --html-out runs/dashboard/world_model_x/index.html \
  --summary-out runs/dashboard/world_model_x/summary.json

python3 -m unittest tests.test_world_model_dashboard_renderer_cli
```

## Required Evidence

The generated `summary.json` is `GO` only when:

- the input uses `world-model-dashboard-data.v1`;
- the timeline is non-empty;
- every frame has a valid `world_model_sha`;
- each rendered agent event hash matches the world-model decision-event hash;
- Qwen evidence and planner metrics are present;
- non-claims include the no-Qwen-real-time-control boundary;
- the rendered HTML SHA-256 is recorded.

## Non-Claims

- No physical robot behavior.
- No SO-101 operation.
- No learned world model.
- No 3D physics simulation.
- No DimOS runtime execution.
- No Open-RMF compatibility claim.
- No Qwen real-time control.
- No safety, latency, or reliability claim.
- No Alibaba ECS deployment proof.
