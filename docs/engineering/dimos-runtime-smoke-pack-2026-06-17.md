# DimOS Runtime Smoke Pack 2026-06-17

Issue: https://github.com/omarespejel/accountable-swarm/issues/88

## Thesis

The bridge pack and replay consumer already prove a deterministic
DimOS-shaped replay contract. The next claim-safe step is an operator pack that
pins the replay artifact inputs and exact commands for a local DimOS runtime
smoke without claiming swarm control or 3D simulation.

## What changed

Added:

- `scripts/collect_dimos_runtime_smoke_report.py`
- `scripts/prepare_dimos_runtime_smoke_pack.py`
- targeted CLI tests for both surfaces

The pack command:

```bash
python3 -m scripts.prepare_dimos_runtime_smoke_pack \
  --bridge-pack runs/dimos/replay-bridge-pack \
  --out-dir runs/dimos/runtime-smoke-pack
```

emits:

- `README.md`
- `operator_commands.sh`
- `manifest.json`

The operator commands:

1. sync the reviewed local DimOS checkout with `uv sync --frozen`,
2. run the replay-consumer precheck against the verified bridge pack,
3. collect a machine-readable runtime smoke report.

## Current local result

`NARROW_CLAIM` for runtime execution on this machine.

What is present locally:

- a real local DimOS source checkout at `/Users/espejelomar/StarkNet/dimos`;
- a verified Accountable Swarm bridge pack / replay consumer path.

What is not present in the current Accountable Swarm environment:

- a DimOS virtual environment under the local checkout;
- `dimos` CLI availability from that checkout;
- `rerun` importability through the reviewed DimOS environment.

So the checked current claim is:

```text
Accountable Swarm can prepare a reproducible, non-secret DimOS runtime smoke
pack pinned to verified replay artifacts.
```

The unchecked claim remains:

```text
DimOS runtime successfully consumed and visualized the replay artifact.
```

## Local validation

```bash
python3 -m unittest tests.test_collect_dimos_runtime_smoke_report_cli tests.test_prepare_dimos_runtime_smoke_pack_cli
python3 -m scripts.prepare_dimos_runtime_smoke_pack --bridge-pack runs/dimos/replay-bridge-pack --out-dir runs/dimos/runtime-smoke-pack-smoke
git diff --check
```

## Non-Claims

This does not prove:

- DimOS swarm control;
- DimOS 3D simulation;
- Rerun recording proof;
- physical robot behavior;
- SO-101 operation;
- latency or reliability.
