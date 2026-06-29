# QwenGuard Submission Readiness Audit 2026-06-29

## Thesis

The QwenGuard Track 5 submission should have a deterministic final gate that
distinguishes scaffold generation from actual submission readiness. The gate
must stay `NARROW_CLAIM` until the operator supplies physical SO-101 evidence,
measured trial rows plus their deterministic summary, Alibaba ECS public
endpoint proof, and human-reviewed video claim labels.

## Why It Matters

The repo now has strong no-hardware preparation artifacts, but the hackathon
submission can only be promoted after operator-run evidence exists. A single
auditor gives future agents and reviewers a checked answer instead of relying on
status prose scattered across issues.

## Implementation

Added `scripts/audit_qwenguard_submission_readiness.py` and the
`audit-qwenguard-submission-readiness` entry point.

The auditor checks:

- claim-safe submission pack manifest is present and `GO`;
- SO-101 camera capture report is `GO`;
- fixture `decisiontrace.v2` verifies with `ALLOW` and no executed motion;
- degraded `decisiontrace.v2` verifies with `HOLD` and no executed motion;
- measured trial trace directory contains at least one verified trial trace;
- trial CSV contains at least one valid measured `TrialRecord` row bound to one
  of those verified measured-trial trace summaries;
- trial summary report is `GO`, points at the same trial CSV and trace
  directory, matches the current CSV SHA-256, and reports the same valid row
  count as the audit;
- ECS smoke report is `outcome: GO` with `proof_mode: ecs-public`;
- final video review note contains the required claim labels and explicit human
  signoff fields.

The readiness checks fail closed on malformed JSON, path escape attempts, and
self-asserted operator evidence. SO-101 camera readiness requires a referenced
frame artifact next to the camera report, measured trial rows must bind to a
measured-trial trace summary SHA verified during the same audit, and the trial
summary must be generated from those same rows and traces. ECS readiness
requires both pass-condition booleans and matching endpoint-check evidence. The
final video review check also rejects keyword-only notes, placeholder signoff
values, and secret-like material. It requires `Reviewed-by`, `Review-date`,
`Video-artifact`, `Privacy-reviewed`, `Claim-boundary-reviewed`,
`Mode-labels-reviewed`, `ECS-proof-reviewed`, `SO-101-footage-reviewed`, and
`Secrets-reviewed`. Local `Video-artifact` values must be repo-relative
existing video files; hosted artifacts may be recorded as HTTPS URLs.

## GO Gate

```bash
python3 -m scripts.audit_qwenguard_submission_readiness \
  --out runs/submission/qwenguard-readiness-report.json
```

This exits `0` only when every required artifact passes.

For the current pre-hardware state:

```bash
python3 -m scripts.audit_qwenguard_submission_readiness \
  --out runs/submission/qwenguard-readiness-report.json \
  --allow-narrow-claim
```

This writes a report with `outcome: NARROW_CLAIM`.

## Validation

```text
python3 -m unittest tests.test_qwenguard_submission_readiness_audit_cli tests.test_packaging
# Ran 13+ packaging tests OK

python3 -m scripts.audit_qwenguard_submission_readiness --out runs/submission/qwenguard-readiness-smoke.json --allow-narrow-claim
# outcome NARROW_CLAIM
```

## Non-Claims

- Not SO-101 connectivity or physical success evidence.
- Not ACT policy success.
- Not Alibaba ECS deployment proof.
- Not a safety, latency, reliability, or state-of-the-art claim.
- Not Qwen motor control or onboard-Qwen evidence.
- Not DimOS runtime control.
