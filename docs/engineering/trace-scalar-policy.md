# Trace Scalar Policy

DecisionTrace hashes must be reproducible across machines and Python versions.

## Rule

Do not put raw floats in hashed trace payloads.

Encode measurements as:

- integers in declared units, for example `latency_ms`, `depth_mm`,
  `confidence_ppm`, or `pose_x_mm`; or
- decimal strings with an explicit quantization policy.

The current trace gate enforces this by rejecting floats in `canonical_json()`.

## Why

The current keyframe trace only stores strings, integers, lists, and objects.
That is stable. Future camera, depth, confidence, pose, latency, or swarm fields
will be tempting to store as floats. Raw floats make cross-runtime replay and
hash stability easier to break.

## Non-Claims

This policy does not prove sensor accuracy, latency, calibration, pose quality,
or physical safety. It only keeps trace serialization deterministic.
