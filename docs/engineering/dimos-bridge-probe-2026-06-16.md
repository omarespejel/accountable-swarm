# DimOS Bridge Probe

Issue: #68

## Thesis

Accountable Swarm should not claim DimOS integration until a DimOS command
actually consumes the project artifact. The useful near-term step is a bridge
pack: verified `DecisionTrace` swarm timelines exported into a deterministic
JSONL shape that a DimOS/Rerun runner can consume later.

## What This Adds

`scripts/prepare_dimos_bridge_pack.py` consumes an existing swarm demo bundle,
loads every referenced agent trace, verifies the trace hash chain, and writes:

```text
runs/dimos/bridge-pack/manifest.json
runs/dimos/bridge-pack/timeline.ndjson
```

The timeline is integer-only. Each line includes:

- scenario name;
- tick;
- agent id;
- integer grid cell;
- local decision;
- event hash;
- trace summary hash;
- a DimOS stream hint.

The manifest also probes DimOS availability without starting DimOS:

- optional source checkout file presence;
- `dimos` Python import availability;
- `dimos` CLI availability.

## Local Command

```bash
python3 scripts/build_swarm_demo_bundle.py --out-dir runs/demo/dimos-bridge-source
python3 scripts/prepare_dimos_bridge_pack.py \
  --source-bundle runs/demo/dimos-bridge-source \
  --out-dir runs/dimos/bridge-pack \
  --dimos-checkout /path/to/local/dimos
```

The `--dimos-checkout` argument is optional. When used, point it at a local
DimOS source checkout; omit it when only the trace export should be checked.

## GO Gate

The branch is `GO` when:

- all input traces verify before export;
- the bridge timeline is written as deterministic NDJSON;
- manifest and timeline contain no key material;
- generated artifact paths are repo-relative;
- local gate runs the bridge exporter from an installed entry point.

DimOS runtime availability is reported separately. A missing DimOS runtime does
not invalidate the bridge artifact, but it prevents any DimOS execution claim.

## Current Local Observation

At branch creation time, a local DimOS source checkout was available for file
presence probing, but `dimos` was not importable from the current Accountable
Swarm environment and no `dimos` CLI was on `PATH`.

That means the valid claim is:

```text
Accountable Swarm can export verified swarm traces into a DimOS-ready bridge
pack.
```

The invalid claim remains:

```text
DimOS is running or simulating the swarm.
```

## Non-Claims

Do not interpret the bridge pack as evidence for:

- DimOS execution or swarm integration;
- Rerun recording proof;
- physical robot behavior or SO-101 operation;
- 3D physics simulation;
- Qwen real-time control;
- latency or reliability guarantees.
