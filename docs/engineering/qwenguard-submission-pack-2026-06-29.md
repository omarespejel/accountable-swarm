# QwenGuard Submission Pack 2026-06-29

Issue: [#106](https://github.com/omarespejel/accountable-swarm/issues/106)

## Thesis

The Track 5 submission needs a single operator-facing pack that makes the
physical and cloud proof gaps explicit before the SO-101 is connected. This
strengthens the project by preventing the no-hardware software spine from being
accidentally promoted into a physical-device claim.

## Change

Added `scripts/prepare_qwenguard_submission_pack.py` and the
`prepare-qwenguard-submission-pack` console entry point.

The generated pack includes:

- `README.md`
- `architecture.md`
- `demo_script.md`
- `evidence_manifest.json`
- `manifest.json`

The pack is intentionally claim-safe:

- pack generation can be `GO`;
- submission readiness remains `NARROW_CLAIM`;
- SO-101 physical evidence remains pending;
- Alibaba ECS public endpoint proof and the human ECS proof review remain
  pending under issue #91.

## GO Gate

```bash
python3 -m unittest tests.test_qwenguard_submission_pack_cli

python3 -m scripts.prepare_qwenguard_submission_pack \
  --out-dir runs/submission/qwenguard-pack-smoke

python3 -m json.tool \
  runs/submission/qwenguard-pack-smoke/manifest.json >/tmp/qwenguard_submission_manifest_pretty.json
```

Expected boundaries:

- `manifest.outcome == "GO"`;
- `manifest.submission_readiness == "NARROW_CLAIM"`;
- all generated paths are repo-relative;
- generated text contains no secret-like material;
- physical SO-101, ECS proof, and human ECS proof-review artifacts are listed
  as required before submit.

## Non-Claims

- Not SO-101 connectivity proof.
- Not physical success evidence.
- Not ACT policy success.
- Not Qwen motor control.
- Not Qwen onboard execution.
- Not Alibaba ECS deployment proof.
- Not safety, latency, reliability, or state-of-the-art evidence.
