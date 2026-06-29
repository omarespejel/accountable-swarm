# QwenGuard Trial Summary

Issue: #106

Umbrella: #95

## Scope

This change adds `summarize-qwenguard-trials`, a post-session evidence helper
for the QwenGuard SO-101 path.

The summarizer reads:

```text
runs/physical/qwenguard_trials/trial_results.csv
runs/physical/qwenguard_trials/traces/*.json
```

It verifies every CSV row against the matching `decisiontrace.v2` JSON trace,
then writes a deterministic machine-readable summary:

```text
runs/physical/qwenguard_trials/trial_summary.json
```

## Claim Boundary

- `GO` means the measured trial rows are internally consistent and trace-bound.
- `GO` does not prove SO-101 safety, reliability, latency, or generalization.
- `GO` does not put Qwen in the motor loop.
- Empty or missing physical evidence remains `NARROW_CLAIM`.

## Reported Counts

The summary reports integer-only counts and rates:

- total measured trials;
- attempted trials;
- success count;
- failure count;
- no-motion count;
- cloud-hold count;
- outcome taxonomy counts;
- selector, gate, policy, cloud, object-layout, and evaluator-label counts;
- success rates in milli-units, not raw floats.

## Default Commands

After recording trials with `record-qwenguard-trial`, run:

```bash
summarize-qwenguard-trials
```

For pre-hardware dry runs, write a narrow report without failing the surrounding
operator script:

```bash
summarize-qwenguard-trials --allow-narrow-claim
```

## Validation

```bash
python3 -m unittest \
  tests.test_summarize_qwenguard_trials_cli \
  tests.test_record_qwenguard_trial_cli \
  tests.test_packaging
```

Run the full local gate before merge:

```bash
./scripts/local_gate.sh
```
