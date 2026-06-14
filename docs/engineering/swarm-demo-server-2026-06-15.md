# Swarm Demo Server 2026-06-15

## Thesis

The deterministic swarm demo bundle should be inspectable through the existing
stdlib demo server without cloud access or physical hardware. This gives a
reviewer a simple local path: build the bundle, start the server, open
`/swarm-demo`.

## Scope

The server is read-only for this gate. It serves an already-generated bundle
from `SWARM_DEMO_BUNDLE_DIR` or the repo-anchored default
`runs/demo/swarm`. It does not generate, mutate, or refresh bundle artifacts on
request.

## Commands

```bash
python3 scripts/build_swarm_demo_bundle.py
python3 scripts/serve_demo.py --host 127.0.0.1 --port 8765
```

Smoke endpoints:

```bash
curl -fsS http://127.0.0.1:8765/swarm-demo
curl -fsS http://127.0.0.1:8765/swarm-demo/summary.json
curl -fsS http://127.0.0.1:8765/swarm-demo/scenarios/corridor/replay.html
```

## Pass Conditions

- `GET /swarm-demo` serves bundle `index.html`;
- `GET /swarm-demo/summary.json` serves the canonical bundle summary;
- scenario replay HTML is served only from inside the configured bundle root;
- empty `SWARM_DEMO_BUNDLE_DIR` does not widen serving to the process CWD;
- roots without `index.html` and `summary.json` fail closed with
  `status: missing_bundle`;
- missing bundle files return JSON with `status: missing_bundle` and the exact
  build command;
- path traversal is rejected with `status: rejected`;
- files are streamed instead of loaded fully into memory;
- requests do not run Qwen, SO-101, DimOS, Docker, cloud APIs, or bundle
  generation.

## Evidence

Focused test:

```text
python3 -m unittest tests.test_server
Ran 7 tests
OK
```

## Non-Claims

- no physical robot behavior;
- no SO-101 operation;
- no 3D physics simulation;
- no live Qwen claim;
- no latency or reliability claim;
- no DimOS integration;
- no arbitrary-map or larger-swarm claim;
- no Alibaba ECS deployment proof.
