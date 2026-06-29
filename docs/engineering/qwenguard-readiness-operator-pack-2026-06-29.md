# QwenGuard Readiness Operator Pack

Date: 2026-06-29

Issue: #106

## Thesis

The final Track 5 readiness gate should be operator-executable from one
generated, non-secret pack instead of scattered commands across SO-101,
Alibaba ECS, ECS proof review, video review, and submission-audit docs.

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
- `summarize-trials`
- `ecs-pack`
- `ecs-review`
- `submission-pack`
- `video-review`
- `next-steps`
- `audit-narrow`
- `audit-final`
- `all-preflight`

`next-steps` is a no-side-effect phase that prints the remaining operator
sequence and expected artifact paths. It is the preferred first command for a
fresh operator session because it keeps SO-101, Alibaba ECS, ECS proof review,
final video review, and final audit work in one checked order.

`all-preflight` is the checked no-camera/no-ECS-host phase: in local tests it
generates the physical, ECS, and submission packs, runs the existing
physical-pack `all-safe` phase, and writes a readiness audit with
`--allow-narrow-claim`.

`ecs-review` writes `runs/ecs/ecs_proof_review.md` only after the operator
supplies reviewer/date metadata plus a terminal, screenshot, or video artifact
from the public Alibaba ECS proof. The final readiness audit now requires that
note in addition to `runs/ecs/ecs_smoke_report.json`.

## GO Gate

- The readiness operator pack manifest records `outcome: GO` and
  `submission_readiness: NARROW_CLAIM`.
- The generated shell script passes `bash -n` in the generator and tests.
- The generated text is checked by the repo's secret-pattern scanner.
- The manifest file paths are repo-relative.
- The focused test suite runs `all-preflight` without camera hardware or an ECS
  host.
- The generated `next-steps` phase prints only operator commands and expected
  repo-relative evidence paths; it does not request raw secrets or claim final
  readiness.

## Current Operator Sequence

Run this first from the repository root:

```bash
python3 -m scripts.prepare_qwenguard_readiness_operator_pack \
  --out-dir runs/submission/qwenguard-readiness-operator-pack-current \
  --commit "$(git rev-parse HEAD)"
bash runs/submission/qwenguard-readiness-operator-pack-current/operator_commands.sh next-steps
```

The next non-scaffold work is:

1. Hardware evidence on the supervised SO-101 machine:
   - `so101-camera`
   - `record-success`
   - `record-cloud-hold`
   - `summarize-trials`
2. Alibaba ECS evidence from issue #91:
   - run the generated ECS pack on the ECS host;
   - copy back sanitized `runs/ecs/ecs_smoke_report.json`;
   - copy or link a terminal/screenshot/video proof artifact with no secrets.
3. Human review notes:
   - `ecs-review`
   - `video-review`
4. Final readiness:
   - `audit-final`

Until those operator artifacts exist, the expected final readiness state is
`NARROW_CLAIM`.

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
