# Accountable Swarm Handoff

Last updated: 2026-06-14 JST

## Active Thesis

Accountable Swarm is a hackathon robotics lab for Qwen Cloud EdgeAgent. The
demo spine keeps real-time action local and deterministic while using Qwen Cloud
for low-rate keyframe perception or mission reasoning. Any demo decision that
matters must be reproducible as a hash-chained `DecisionTrace`.

## Current Evidence State

Status: `NARROW_CLAIM`

What is checked locally:

- fixture-mode image-to-decision GO gate;
- Qwen-style `bbox_2d` parsing and normalized coordinate validation;
- deterministic `DecisionTrace` serialization and replay;
- physical-node trace-only safety contract;
- no-key DashScope failure path.

What is not checked yet:

- live DashScope / Qwen API call with `ALIBABA_API_KEY`;
- Alibaba Cloud deployment proof;
- SO-101 or webcam physical frame source;
- DimOS integration;
- multi-agent swarm behavior;
- latency, reliability, or safety claims.

## Active GitHub Work

- Issue #1: research ground truth and build hierarchy.
- Issue #2: 48-hour GO gate for Qwen keyframe to `DecisionTrace`.
- Issue #3: physical-node safety contract.
- Issue #4: Alibaba/Qwen proof path.
- PR #5: foundational GO-gate implementation.

Before creating new work, inspect the current PR and issues:

```bash
gh pr view 5 --comments
gh issue list --state open
```

## Next Agent Rules

- Start from the read order in `.codex/START_HERE.md`.
- Keep work issue-scoped and outcome-scoped: `GO`, `NO_GO`,
  `NARROW_CLAIM`, `FOLLOWUP_ISSUE`, or `KILL`.
- Add exact commands to PR bodies and evidence docs.
- Record any copied code, generated assets, model usage, or external services in
  `DISCLOSURE_LEDGER.md`.
- Do not merge while Qodo, CodeRabbit, or human review feedback is actionable.
- Wait five minutes after the latest relevant reviewer activity before merge.
