# World-Model Dashboard Data Pack

Date: 2026-06-16

Issue: [#75](https://github.com/omarespejel/accountable-swarm/issues/75)

## Thesis

The dashboard should not read loose simulator artifacts independently. It should
consume one checked data pack whose timeline is bound to verified
`DecisionTrace` files and verified `WorldModelState` hashes.

## Change

- Added `scripts.prepare_world_model_dashboard_pack`.
- Added the installed entrypoint `prepare-world-model-dashboard-pack`.
- Added a dashboard data schema, `world-model-dashboard-data.v1`.
- Added a pack report schema, `world-model-dashboard-pack-report.v1`.
- Verified persisted hazard traces, agent traces, and world-model timeline rows.
- Rejected a rehashed world-model timeline that no longer matches source agent
  trace commands.

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

python3 -m unittest tests.test_world_model_dashboard_pack_cli
```

## Required Evidence

The generated `manifest.json` is `GO` only when:

- source artifact paths stay inside the repository;
- the hazard report is a supported `GO` or `DEGRADED` report;
- the hazard `DecisionTrace` verifies;
- every agent `DecisionTrace` verifies;
- every `WorldModelState` row verifies;
- first and last world-model hashes match the hazard report;
- each world-model agent cell, goal, decision, and trace summary hash matches
  the source agent trace event at the same tick;
- generated data contains no API key material;
- generated data uses relative paths only.

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
