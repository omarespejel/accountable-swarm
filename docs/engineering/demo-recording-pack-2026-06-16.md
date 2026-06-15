# Demo Recording Pack

Issue: #59

Date: 2026-06-16

## Purpose

Create one reproducible local command for the current judge-facing recording
surface. The pack is a convenience wrapper around already-reviewed gates:

- deterministic swarm demo bundle generation;
- fixture hazard-to-X-formation gate;
- manifest and shot-list generation.

The pack exists so the demo video can be recorded from exact artifacts instead
of ad hoc terminal history.

## Command

Run from the repository checkout root:

```bash
python3 scripts/prepare_demo_recording_pack.py
```

Equivalent installed entrypoint:

```bash
prepare-demo-recording-pack
```

The installed entrypoint still expects the current working directory to be an
`accountable-swarm` checkout containing `pyproject.toml` and
`fixtures/hazard_marker.ppm`; it is not a standalone wheel-only demo runner.

Expected files:

```text
runs/demo/recording-pack/manifest.json
runs/demo/recording-pack/shotlist.md
runs/demo/swarm/index.html
runs/demo/swarm/summary.json
runs/hazard_formation/recording_x_report.json
runs/hazard_formation/recording_x/hazard.json
```

The manifest records the exact child commands, return codes, generated artifact
paths, local server URLs, recording beats, pass conditions, and non-claims.

## Recording Boundary

The default pack is fixture-first. It does not require `ALIBABA_API_KEY`, and it
does not re-run live DashScope evidence. Live Qwen hazard-to-formation evidence
is recorded separately in
`docs/engineering/live-dashscope-hazard-formation-2026-06-16.md`.

The demo story supported by this pack is:

```text
Qwen-style keyframe bbox or live Qwen evidence -> local hazard cell ->
deterministic X formation -> replayable DecisionTrace artifacts.
```

## Non-Claims

- no physical robot behavior;
- no SO-101 operation;
- no 3D physics simulation;
- no DimOS integration;
- no Qwen real-time control;
- no Qwen onboard execution;
- no completed Alibaba ECS deployment proof;
- no latency or reliability claim.

## Validation

Targeted validation for this change:

```bash
python3 -m unittest tests.test_demo_recording_pack_cli tests.test_packaging
git diff --check
```

Full repository validation remains:

```bash
./scripts/local_gate.sh
```
