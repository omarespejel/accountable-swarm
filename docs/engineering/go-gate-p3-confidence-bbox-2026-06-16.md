# GO-Gate P3 Confidence and Bbox Hardening

Date: 2026-06-16 JST

## Thesis

Future camera and model traces need confidence-like scalar fields without
breaking deterministic replay. Qwen responses may include raw float confidence
values, but hashed `DecisionTrace` payloads must only store integer units.

Tiny normalized bboxes also need a reviewed pixel policy so valid positive-area
0-1000 detections do not collapse to invalid zero-area pixel boxes on small
frames.

## Outcome

Status: `GO`

The Qwen bbox parser now accepts optional `score`, `confidence`,
`score_milli`, or `confidence_milli` fields. Unit scores are consumed at parse
time and quantized into `score_milli` in `0..1000`. `PerceptionEvent` persists
only the integer `score_milli` value and rejects raw floats, booleans, and
out-of-range values before trace hashing.

This is an explicit `DecisionTrace` schema change to `decisiontrace.v2`. Old
`decisiontrace.v1` artifacts are rejected with a clear unsupported-schema error
instead of being silently rehashed with an injected confidence field.

`rescale_norm_1000_bbox` now clamps any valid positive-area normalized bbox to a
positive-area pixel bbox inside the image, including edge cases where a tiny
normalized bbox rounds to the same pixel coordinate.

## Checked Surface

- `accountable_swarm/qwen/bbox.py`
- `accountable_swarm/trace/models.py`
- `scripts/run_go_gate.py`
- `scripts/run_camera_go_gate.py`
- `scripts/run_hazard_formation_gate.py`
- `accountable_swarm/server.py`
- `tests/test_qwen_bbox.py`
- `tests/test_trace.py`

## Validation

```text
python3 -m unittest tests.test_trace tests.test_go_gate_cli tests.test_qwen_bbox tests.test_ecs_smoke_report_cli
# Ran 41 tests OK
```

Full local gate:

```text
./scripts/local_gate.sh
tomllib unavailable; skipping .pr_agent.toml parse
# packaging install, fixture GO-gate, camera GO-gate, hazard formation,
# ECS operator pack, DimOS bridge pack, and unittest discovery
# Ran 194 tests OK
local gate passed
```

## Non-Claims

- No physical robot, webcam, SO-101, or motion claim.
- No live Qwen accuracy, latency, reliability, or safety claim.
- No DimOS execution or integration claim.
- No calibrated confidence semantics beyond deterministic integer trace storage.
- No 3D grounding claim.
