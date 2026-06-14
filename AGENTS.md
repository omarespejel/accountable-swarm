# Accountable Swarm Agent Rules

This repository is a hackathon robotics lab for Qwen Cloud EdgeAgent.

It is not run like a normal feature repo. Every meaningful change must answer:

> Did this strengthen, falsify, or narrow the accountable edge-cloud autonomy thesis?

## Current Thesis

We can demonstrate accountable edge-cloud robotics by keeping real-time action
local and deterministic while using Qwen Cloud for low-rate mission reasoning
and keyframe semantic perception. Every decision promoted in the demo must have
a replayable, deterministic DecisionTrace.

## Boundaries

- Fresh agents must read `.codex/START_HERE.md` before relying on memory or old
  thread context.
- Keep Qwen, LLMs, and VLMs out of real-time control loops.
- Qwen may produce mission intent, semantic labels, and keyframe bbox evidence.
- Local controllers, safety guards, fallback behavior, and collision checks must
  be deterministic and testable.
- Do not claim Qwen runs onboard unless a checked artifact proves it.
- Do not claim 3D grounding unless the output is validated. The default claim is
  2D bbox/label from Qwen plus depth or known geometry from the simulator/device.
- Do not claim swarm success, SO-101 success, latency, reliability, safety,
  state-of-the-art performance, or Alibaba deployment until evidence exists.
- Treat physical-device code as safety-sensitive.
- Use fixture/webcam/SO-101 gates before expanding to drone swarm complexity.

## Research Lanes

1. **Default lane**
   - Stable repo scaffolding, schemas, gates, docs, and judge-facing quickstart.

2. **Experimental lane**
   - Qwen prompt experiments, SO-101 adapters, simulated swarm, DimOS integration,
     Rerun visualization, and Alibaba deployment wiring.

3. **Claim lane**
   - Any text intended for Devpost, README claims, demo script, deck, blog, or
     public social post.

4. **Hardening lane**
   - DecisionTrace determinism, hash-chain replay, coordinate normalization,
     key handling, physical safety, path safety, and generated artifact integrity.

## Trusted-Core Paths

Changes under these paths require stronger review and validation:

- `accountable_swarm/**`
- `scripts/**`
- `tests/**`
- `examples/**`
- `docs/engineering/**`
- `docs/security/**`
- `docs/research/**`
- `.github/**`
- `.coderabbit.yaml`
- `.pr_agent.toml`
- `DISCLOSURE_LEDGER.md`

## Bot Review Policy

Qodo and CodeRabbit are adversarial reviewers, not authorities.

Classify bot findings before merging:

- `must_fix`: real correctness, safety, security, reproducibility, evidence, or
  test-gap issue.
- `evidence_needed`: plausible issue; inspect and reproduce locally before
  accepting or rejecting.
- `stale_or_false_positive`: bot misunderstood or reviewed stale code; reply
  briefly with evidence.
- `followup_issue`: valid but outside current PR scope; open an issue with
  GO/NO-GO framing.
- `ignore`: style-only feedback with no correctness, safety, compliance, or
  research impact.

Do not merge with unresolved `must_fix` or `evidence_needed` findings.

## Merge Discipline

- Work on branches; keep `main` stable.
- Use small PRs with exact validation commands.
- Prefer rebase merges.
- Wait 5 minutes after the latest Qodo, CodeRabbit, or human review activity
  before merging.
- Do not use bot approval as a substitute for local validation.

## Required Local Gate

Run this before opening a PR and before merging:

```bash
./scripts/local_gate.sh
```

Add targeted tests for the surface touched by the PR.

## Handoff Discipline

- `.codex/research/north_star.yml` is the thesis and forbidden-claims source of
  truth.
- `.codex/research/operating_model.yml` is the workflow source of truth.
- `.codex/HANDOFF.md` records active evidence, blockers, and open work.
- Failed experiments must land as `NO_GO`, `NARROW_CLAIM`,
  `FOLLOWUP_ISSUE`, or `KILL`; do not rewrite them as vague progress.
