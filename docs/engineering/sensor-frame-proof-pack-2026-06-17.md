# Sensor-Frame Proof Pack 2026-06-17

Issue: https://github.com/omarespejel/accountable-swarm/issues/3

## Thesis

The webcam or static-image fallback should be a first-class, reproducible
artifact instead of a remembered local note. The proof surface must preserve
the current physical-node safety boundary: frame in, deterministic
`DecisionTrace` out, no autonomous motion, and no committed private imagery by
default.

## What changed

Added `scripts/prepare_sensor_frame_proof_pack.py`.

The command:

```bash
python3 -m scripts.prepare_sensor_frame_proof_pack \
  --image fixtures/hazard_marker.ppm \
  --mode fixture \
  --out-dir runs/physical/sensor-frame-proof
```

produces:

- `trace.json`
- `report.json`
- `manifest.json`

The manifest records:

- source basename, dimensions, size, and SHA-256;
- camera-go-gate trace and report paths;
- trace/report hash agreement;
- the five pass conditions from the camera gate;
- explicit non-claims.

If `--capture-webcam` is used, the captured frame is deleted after hashing by
default unless `--keep-captured-frame` is set.

## Why this matters

Issue `#3` already had a true webcam pass in local notes, but it was not a
checked, repeatable pack artifact. This closes that process gap without
claiming SO-101, physical motion, or safety evidence.

## Local validation

```bash
python3 -m unittest tests.test_sensor_frame_proof_pack_cli tests.test_camera_go_gate_cli tests.test_physical_contract
python3 -m scripts.prepare_sensor_frame_proof_pack --image fixtures/hazard_marker.ppm --mode fixture --out-dir runs/physical/sensor-frame-proof-smoke
git diff --check
```

## Non-Claims

This does not prove:

- physical robot behavior;
- SO-101 operation;
- webcam privacy safety beyond the delete-after-hash default;
- latency or reliability;
- cloud deployment;
- swarm behavior.
