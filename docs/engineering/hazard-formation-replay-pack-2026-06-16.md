# Hazard Formation Replay Pack - 2026-06-16

## Thesis

The hazard-to-formation path should be visible in the judge recording, not only
present as JSON. A recording pack can render the persisted four-agent formation
traces into a deterministic HTML replay while preserving the project boundary:
Qwen or fixture perception selects a keyframe hazard, local code quantizes it
into a grid cell, and deterministic agents move through verified traces.

## Local Command

```bash
python3 scripts/prepare_demo_recording_pack.py
python3 scripts/serve_demo.py --host 127.0.0.1 --port 8000
```

Then inspect:

```text
http://127.0.0.1:8000/hazard-formation
http://127.0.0.1:8000/hazard-formation/summary.json
```

## GO Gate

- `prepare_demo_recording_pack.py` runs the hazard formation gate.
- It renders the generated agent traces under `runs/hazard_formation/recording_x/agents`.
- The bbox-derived hazard cell is passed to the renderer as an obstacle.
- The recording manifest records the hazard replay HTML and summary paths.
- `serve_demo.py` serves the generated replay read-only at `/hazard-formation`.
- The server rejects path traversal and fails closed when replay markers are
  missing.

## Current Boundary

This is a deterministic 2D replay artifact. It is useful for the demo video
because it makes the perception-to-formation chain visible, but it does not
prove DimOS execution, physical robot behavior, 3D physics, Qwen real-time
control, safety, latency, or reliability.

## Non-Claims

- No DimOS execution or integration claim.
- No physical robot or SO-101 operation claim.
- No 3D physics simulation claim.
- No Qwen real-time control claim.
- No latency, reliability, or safety claim.
