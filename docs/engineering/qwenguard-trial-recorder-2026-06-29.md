# QwenGuard Trial Recorder

Issue: #103

Readiness gate: #106

## Scope

This change adds `record-qwenguard-trial`, a physical-session evidence helper
for the SO-101 QwenGuard path.

The recorder writes one `decisiontrace.v2` JSON trace per measured physical
attempt and appends the matching `TrialRecord` row to:

```text
runs/physical/qwenguard_trials/trial_results.csv
```

The CSV row uses the trace summary SHA recomputed by the verifier. Operators no
longer need to hand-copy trace hashes from separate files.

## Claim Boundary

- This is operator-recorded evidence plumbing.
- It does not prove SO-101 connectivity, ACT success, safety, or reliability.
- It does not put Qwen in the motor loop.
- It does not make a DimOS physical-control claim.

## Default Commands

```bash
record-qwenguard-trial \
  --trial-id trial-001 \
  --outcome success \
  --motion-executed true \
  --control-label AUTONOMOUS \
  --confirm-operator-attestation
```

`--confirm-operator-attestation` is required for every measured trial row. It
records that a human operator is intentionally creating operator-attested
physical/degraded evidence; it is not automatic physical success proof.

The trial summarizer re-validates this evidence before it can become an
aggregate `READY` report. It rejects rows whose verified trace has the wrong
`run_id`, wrong perception event id, duplicate `trace_summary_sha`, no executed
motion for attempted outcomes, or `SCRIPTED` control for attempted physical
success/failure rows. The detailed hardening note is
`docs/engineering/qwenguard-trial-summary-hardening-2026-06-29.md`.

The generated physical GO pack exposes the same path through:

```bash
QWENGUARD_TRIAL_ID=trial-001 \
  bash runs/physical/qwenguard-physical-go-pack/operator_commands.sh record-success
```

For the degraded-network take:

```bash
QWENGUARD_TRIAL_ID=trial-cloud-hold-001 \
  bash runs/physical/qwenguard-physical-go-pack/operator_commands.sh record-cloud-hold
```

## Validation

```bash
python3 -m unittest \
  tests.test_record_qwenguard_trial_cli \
  tests.test_qwenguard_physical_go_pack_cli \
  tests.test_qwenguard_submission_pack_cli \
  tests.test_qwenguard_submission_readiness_audit_cli \
  tests.test_packaging
```

Run the full local gate before merge:

```bash
./scripts/local_gate.sh
```
