# DimOS Replay Consumer

Issue: #73

## Thesis

Accountable Swarm should not claim DimOS integration until DimOS actually
consumes a project artifact. The next useful step after the bridge pack is a
deterministic replay consumer that validates the exported timeline, groups it
into DimOS-shaped streams, and records DimOS runtime availability separately.

## What This Adds

`scripts/run_dimos_replay_consumer.py` consumes:

```text
runs/dimos/<bridge-pack>/manifest.json
runs/dimos/<bridge-pack>/timeline.ndjson
```

It validates that:

- the bridge manifest uses `dimos-bridge-pack-report.v1`;
- the bridge outcome is `GO`;
- manifest `event_count`, `scenario_count`, `scenarios`, and artifact paths
  match the actual bridge pack and parsed timeline;
- each timeline line is canonical JSON;
- each timeline event uses `dimos-swarm-replay-event.v1`;
- raw floats and boolean scalars are rejected before replay grouping;
- event ticks are monotonic within each stream;
- `dimos_stream_hint` matches the scenario and agent id;
- event and trace hashes are 64-character lowercase hex strings;
- output paths stay inside the repository;
- the report contains no API key material.

The report groups events by `dimos_stream_hint` and emits deterministic stream
summaries with first/last ticks, first/last grid cells, event counts, and
decision sets.

## Local Command

```bash
python3 scripts/build_swarm_demo_bundle.py --out-dir runs/demo/dimos-replay-source
python3 scripts/prepare_dimos_bridge_pack.py \
  --source-bundle runs/demo/dimos-replay-source \
  --out-dir runs/dimos/replay-bridge-pack \
  --dimos-checkout /Users/espejelomar/StarkNet/dimos
python3 -m scripts.run_dimos_replay_consumer \
  --bridge-pack runs/dimos/replay-bridge-pack \
  --report-out runs/dimos/replay-consumer-report.json \
  --dimos-checkout /Users/espejelomar/StarkNet/dimos
```

Use `--require-dimos-runtime` only when validating actual runtime readiness.
Without it, the command exits successfully when the replay consumer is valid
even if the DimOS runtime is unavailable. The report still marks the broader
claim as `NARROW_CLAIM` when `dimos`, the `dimos` CLI, or `rerun` are missing.

## Current Local Observation

The local DimOS source checkout is available at:

```text
/Users/espejelomar/StarkNet/dimos
```

The current Accountable Swarm environment does not have:

```text
dimos Python import
dimos CLI
rerun Python import
```

Therefore the valid claim after this gate is:

```text
Accountable Swarm can export and consume verified swarm traces as a
DimOS-shaped replay stream contract.
```

The invalid claim remains:

```text
DimOS is running, visualizing, or controlling the swarm.
```

## GO Gate

This path is `GO` for the replay contract when:

- a verified bridge pack is consumed;
- the consumer report has `consumer_outcome: GO`;
- tampered, escaped, float-containing, or out-of-order timeline input is
  rejected by tests;
- `./scripts/local_gate.sh` runs the consumer through the installed entry point.

It remains `NARROW_CLAIM` for DimOS runtime execution until a separate command
starts DimOS/Rerun and records a checked artifact.

## Non-Claims

Do not interpret this artifact as evidence for:

- DimOS runtime execution;
- DimOS swarm control;
- Rerun recording proof;
- physical robot behavior or SO-101 operation;
- 3D physics simulation;
- Qwen real-time control;
- latency or reliability guarantees.
