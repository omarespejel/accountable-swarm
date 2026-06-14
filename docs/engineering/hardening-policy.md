# Hardening Policy

Trusted-core work is anything that can change safety, evidence, or public claim
meaning.

## Trusted-Core Surfaces

- `accountable_swarm/trace/**`
- `accountable_swarm/qwen/**`
- `accountable_swarm/physical/**`
- future `accountable_swarm/swarm/**`
- `scripts/**`
- `tests/**`
- `.codex/**`
- `.github/**`
- `.coderabbit.yaml`
- `.pr_agent.toml`
- `docs/engineering/**`
- `docs/security/**`
- `DISCLOSURE_LEDGER.md`

## Required Bias

Prefer fail-closed behavior over permissive parsing.

High-priority hardening targets:

- malformed Qwen output;
- Qwen3-VL normalized `0..1000` coordinate handling;
- image-size mismatch;
- deterministic canonical JSON and hash-chain replay;
- stale or missing `prev_sha`;
- trace tampering;
- API-key leakage;
- physical movement without explicit operator arming;
- docs that imply a stronger claim than evidence supports.

## Local Validation

Run:

```bash
./scripts/local_gate.sh
```

Add targeted tests whenever a PR changes:

- trace serialization;
- parser validation;
- Qwen client behavior;
- physical safety contracts;
- path handling;
- evidence generation;
- public-claim wording.

## Bot Review Policy

Qodo and CodeRabbit are adversarial review signals, not authorities. Concrete
findings in `must_fix` or `evidence_needed` classes block merge until resolved
or disproven with evidence.

Do not merge until:

- local validation passed;
- no actionable Qodo findings remain;
- no actionable CodeRabbit findings remain;
- no actionable human threads remain;
- five minutes have passed since the latest relevant reviewer activity.

## Follow-Up Discipline

When a valid risk is outside the current PR, open a `Hardening follow-up` issue
with:

- observed risk;
- evidence or location;
- why not current PR;
- smallest fix or test;
- GO/NO-GO condition;
- local validation plan.

Do not widen a PR just because the risk is interesting.
