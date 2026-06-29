# QwenGuard Trial Summary Hardening 2026-06-29

## Thesis

Issue #123 found that the trial summarizer was the only component allowed to
promote measured SO-101 rows into aggregate success counts, but it trusted too
little trace metadata. A valid hash chain alone was not enough to prove that a
CSV row described the claimed trial.

## Change

Trial summaries now bind each CSV row to the verified `decisiontrace.v2` payload
with these additional checks:

- `trace.run_id == qwenguard-trial-{trial_id}`;
- all events use perception event id `{trial_id}-perception`;
- `motion_executed` and `control_label` are re-derived from the trace action
  event, not trusted from the CSV;
- attempted physical outcomes require `motion_executed=true` and
  `control_label` in `TELEOP` or `AUTONOMOUS`;
- `cloud_hold` and `unsafe_hold` remain no-motion HOLD outcomes;
- duplicate `trace_summary_sha` values across rows are rejected as non-unique
  evidence.

The recorder and summarizer both call the shared trial semantic validator in
`accountable_swarm.qwenguard.trial`.

## Report Language

The summary report now labels aggregate rates as:

```text
operator-attested measured rows only; not automatic physical-success proof
```

`trial_readiness=READY` means the rows and traces are internally consistent.
It does not by itself prove safety, reliability, generalization, or physical
success beyond the operator-attested rows.

## Regression Probes

The test suite now covers the three audit probes:

- a recomputed success trace with `motion_executed=false` and
  `control_label=SCRIPTED`;
- a trace copied under another trial id where `run_id` and perception id do not
  match the CSV row;
- one trace summary reused by multiple CSV rows.

Each probe yields `NARROW_CLAIM`.

## Validation

```bash
python3 -m unittest \
  tests.test_qwenguard_trial \
  tests.test_record_qwenguard_trial_cli \
  tests.test_summarize_qwenguard_trials_cli
```

## Non-Claims

- This does not create real SO-101 evidence.
- This does not prove physical success.
- This does not certify safety, latency, or reliability.
- This does not put Qwen in the motor loop.
