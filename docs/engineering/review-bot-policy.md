# Review Bot Policy

Checked on 2026-06-14:

- CodeRabbit supports repo-root `.coderabbit.yaml`, automatic review controls,
  path filters, and path-specific instructions.
- Qodo Code Review v2 supports repo-root `.pr_agent.toml` for Git integration
  behavior, review output, and custom instructions.

Repo-side files do not install the GitHub apps. CodeRabbit and Qodo must still
be enabled in their respective dashboards for `omarespejel/accountable-swarm`.

## Role

Qodo and CodeRabbit are cheap adversarial reviewers, not authorities.

They should bias toward:

- correctness and security;
- deterministic traces and reproducibility;
- physical-device safety;
- Qwen/API response validation;
- unsupported public claims;
- tests for malformed inputs and replay mismatch.

They should not drive:

- style-only churn;
- cosmetic rewrites;
- architectural expansion outside the issue scope.

## Triage Classes

`must_fix`

Real correctness, safety, security, reproducibility, evidence, or test-gap issue.
Fix locally, add validation, and push again.

`evidence_needed`

Plausible issue. Reproduce locally or inspect the current code before accepting
or rejecting.

`stale_or_false_positive`

Bot misunderstood, reviewed stale code, or inferred a non-existent path. Reply
briefly with evidence. Do not churn code.

`followup_issue`

Valid but outside current PR. Open an issue with GO/NO-GO framing.

`ignore`

Style-only feedback with no correctness, safety, compliance, or research impact.

## Quiet Window

After the latest Qodo, CodeRabbit, or human reviewer activity:

```text
wait 5 minutes
recheck comments
recheck review state
recheck merge state
then merge
```

The quiet window restarts after a new push or any actionable reviewer update.

## Required PR Body

Every PR must include exact local validation commands. The default is:

```bash
./scripts/local_gate.sh
```

Trusted-core changes must add targeted tests or explain why tests are not
applicable.
