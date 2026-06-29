# QwenGuard Readiness Operator Pack

Date: 2026-06-29

Issue: #106

## Thesis

The final Track 5 readiness gate should be operator-executable from one
generated, non-secret pack instead of scattered commands across SO-101,
Alibaba ECS, video review, and submission-audit docs.

## What Changed

Added `prepare-qwenguard-readiness-operator-pack`, which writes:

- `runs/submission/qwenguard-readiness-operator-pack/README.md`
- `runs/submission/qwenguard-readiness-operator-pack/operator_commands.sh`
- `runs/submission/qwenguard-readiness-operator-pack/manifest.json`

The generated command script has these phases:

- `bootstrap`
- `safe-software`
- `so101-camera`
- `record-success`
- `record-failure`
- `record-cloud-hold`
- `ecs-pack`
- `submission-pack`
- `video-review`
- `audit-narrow`
- `audit-final`
- `all-preflight`

`all-preflight` is intentionally safe before hardware: it generates the
physical, ECS, and submission packs; runs the no-motion fixture/degraded path;
and runs the readiness audit with `--allow-narrow-claim`.

## GO Gate

- The readiness operator pack writes a manifest with `outcome: GO`.
- The manifest keeps `submission_readiness: NARROW_CLAIM`.
- The generated shell script passes `bash -n`.
- The generated text contains no token-like material.
- The generated file paths are repo-relative.
- `all-preflight` runs without touching the SO-101 camera or requiring an ECS
  host.

## Non-Claims

- Not SO-101 connectivity proof.
- Not SO-101 camera success.
- Not physical trial success.
- Not ACT policy success.
- Not Alibaba ECS deployment proof.
- Not final submission readiness.
- Not Qwen motor control or onboard Qwen execution.
- Not DimOS runtime control.
- Not safety, latency, reliability, or production hosting.

## Local Validation

```bash
python3 -m unittest tests.test_qwenguard_readiness_operator_pack_cli tests.test_packaging
./scripts/local_gate.sh
```
