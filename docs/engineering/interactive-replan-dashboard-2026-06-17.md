# Interactive Replan Dashboard

Date: 2026-06-17

Issue: [#93](https://github.com/omarespejel/accountable-swarm/issues/93)

## Thesis

The dashboard becomes materially stronger if a judge can change the scene and
watch the same reviewed deterministic planner recompute live, without moving
Qwen into motion control and without introducing a second planner in the
browser.

## Change

- Added a local-only `/replan` endpoint to the stdlib server.
- The endpoint validates a bounded canonical request body with:
  - grid size
  - four current agent cells
  - one hazard cell
  - zero or more obstacle cells
  - a bounded formation enum
  - optional bounded observations copied from verified dashboard evidence
- The endpoint re-enters the existing reservation planner, rebuilds agent
  `DecisionTrace` objects in memory, recomputes world-model rows, and returns a
  deterministic canonical JSON response. It does not write new trace files.
- The HTML dashboard now exposes:
  - `Add obstacle`
  - `Clear obstacles`
  - formation buttons for `x`, `surround`, `line`, and `diamond`
  - a live status line showing planner outcome or deterministic rejection
- Canvas clicks go to the Python truth surface through `/replan`; there is no
  JavaScript-side planner.

## GO Gate

```bash
python3 -m unittest tests.test_server tests.test_world_model_dashboard_renderer_cli

python3 -m scripts.render_world_model_dashboard_html \
  --data runs/dashboard/world_model_issue90_x/data.json \
  --html-out runs/dashboard/world_model_issue90_x/index.html \
  --summary-out runs/dashboard/world_model_issue90_x/summary.json

WORLD_MODEL_DASHBOARD_DIR=runs/dashboard/world_model_issue90_x \
python3 scripts/serve_demo.py --host 127.0.0.1 --port 8766

curl -s -X POST http://127.0.0.1:8766/replan \
  -H 'Content-Type: application/json' \
  --data '{"grid":{"w":7,"h":5},"agents":[{"id":"sim-agent-0","cell":[0,2]},{"id":"sim-agent-1","cell":[6,2]},{"id":"sim-agent-2","cell":[3,0]},{"id":"sim-agent-3","cell":[3,4]}],"hazard":[3,2],"obstacles":[[1,2]],"formation":"x","ticks":8}' \
  | jq '{schema_version,outcome,planner_metrics,first_tick:.timeline[0].agents}'
```

Manual browser preview:

- open `http://127.0.0.1:8766/world-model-dashboard`
- click a free grid cell to toggle an obstacle
- verify the status line changes to `Planner GO ...` or a deterministic reject
- verify the current-tick decisions and `World model hash` update

This preview is for operator inspection and screen recording only. The
reproducible evidence surface is the `curl` request above plus the endpoint and
renderer tests; manual browser clicks are not promoted as standalone evidence.

## Required Evidence

The checked surface is `GO` only when:

- identical `/replan` request bodies produce byte-identical JSON responses;
- `/replan` is rejected for non-loopback clients;
- the first reviewed obstacle interaction yields a genuine planner
  `REROUTE`, `MOVE`, or deterministic reject from the Python planner;
- the dashboard redraws from the returned timeline without reimplementing
  planning in JavaScript.

## Non-Claims

- No physical robot behavior or SO-101 operation.
- No learned world model or 3D physics simulation.
- No DimOS runtime execution or Open-RMF compatibility claim.
- No Qwen real-time control.
- No safety, latency, reliability, or Alibaba ECS deployment proof.
