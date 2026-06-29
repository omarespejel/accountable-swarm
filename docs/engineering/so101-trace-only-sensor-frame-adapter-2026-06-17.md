# SO-101 Trace-Only Sensor-Frame Adapter 2026-06-17

Issue: https://github.com/omarespejel/accountable-swarm/issues/81

## Thesis

The next hardware-specific step after the webcam/static-image fallback is an
SO-101 camera-frame adapter that stays trace-only and reuses the existing
camera-go-gate/DecisionTrace spine.

## Current Result

`NO_GO` on this machine for the live capture path, but with a controlled probe
artifact and an explicit dependency boundary.

Added:

- `accountable_swarm/physical/so101.py`
- `scripts/capture_so101_camera_frame.py`
- `tests/test_so101_camera_capture_cli.py`

The probe:

```bash
python3 -m scripts.capture_so101_camera_frame \
  --camera-name so101_overhead \
  --index-or-path 0 \
  --out runs/physical/so101_frame.png \
  --report-out runs/physical/so101_capture_report.json
```

emits a report even when the optional dependencies are unavailable.

`--out` and `--report-out` must be repo-relative paths in the same directory.
Absolute paths, `..` segments, and split frame/report directories are rejected
before any artifact is written, so physical evidence stays inside the auditable
checkout and the report can unambiguously reference the captured frame by
basename.

## Why the current result is NO_GO

This machine does not currently have the optional `lerobot` or `opencv`
packages installed, and there is no checked SO-101 camera device path in the
repo. That means we can prepare the adapter surface and controlled failure
path, but not claim a live SO-101 frame capture yet.

## What is checked

- numeric camera IDs are normalized deterministically;
- frame/report artifact paths are repo-relative and cannot escape the checkout;
- the probe emits a controlled `NO_GO` report when optional dependencies are
  absent;
- the trace-only motion boundary remains explicit.

## Local validation

```bash
python3 -m unittest tests.test_so101_camera_capture_cli
git diff --check
```

## Non-Claims

This does not prove:

- SO-101 connectivity;
- SO-101 camera success;
- autonomous SO-101 motion;
- ACT policy success;
- safety, latency, or reliability;
- physical swarm behavior.
