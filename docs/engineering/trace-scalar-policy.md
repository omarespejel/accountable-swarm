# Trace Scalar Policy

DecisionTrace hashes must be reproducible across machines and Python versions.

## Rule

Do not put raw floats in hashed trace payloads.

Encode measurements as:

- integers in declared units, for example `latency_ms`, `depth_mm`,
  `score_milli`, `confidence_ppm`, or `pose_x_mm`; or
- decimal strings with an explicit quantization policy.

The current trace gate enforces this by rejecting floats in `canonical_json()`.
Qwen bbox confidence-like response fields are consumed at parse time and stored
as integer `score_milli` values in `PerceptionEvent`.

`score_milli` is part of `decisiontrace.v2` hashed payloads. Earlier
`decisiontrace.v1` artifacts are not silently upgraded because that would change
their event and summary hashes.

## Why

The current keyframe trace only stores strings, integers, lists, and objects.
That is stable. Future camera, depth, confidence, pose, latency, or swarm fields
will be tempting to store as floats. Raw floats make cross-runtime replay and
hash stability easier to break.

## Non-Claims

This policy does not prove sensor accuracy, latency, calibration, pose quality,
or physical safety. It only keeps trace serialization deterministic.
