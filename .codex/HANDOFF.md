# Accountable Swarm Handoff

Last updated: 2026-06-15 JST

## Active Thesis

Accountable Swarm is a hackathon robotics lab for Qwen Cloud EdgeAgent. The
demo spine keeps real-time action local and deterministic while using Qwen Cloud
for low-rate keyframe perception or mission reasoning. Any demo decision that
matters must be reproducible as a hash-chained `DecisionTrace`.

## Current Evidence State

Status: `GO` for live Qwen API/model availability and single-keyframe
DecisionTrace; `NARROW_CLAIM` for the broader robotics demo.

What is checked locally:

- fixture-mode image-to-decision GO gate;
- Qwen-style `bbox_2d` parsing and normalized coordinate validation;
- deterministic `DecisionTrace` serialization and replay;
- physical-node trace-only safety contract;
- no-key DashScope failure path.
- live `qwen3-vl-flash` DashScope trace from generated PNG fixture;
- minimal `qwen-plus` and `qwen3.5-plus` Commander/text pings.
- trace canonical JSON rejects raw floats; future measurements must use integer
  units or decimal strings.
- camera/static-frame GO gate passes live `qwen3-vl-flash` with all five binary
  pass conditions and summary
  `214d4edb89537ecf6c8060b2e4fcd6053497aa20439b65cca8641ef8d0e011c8`.
- minimal stdlib HTTP server and Dockerfile exist for manual Alibaba ECS proof;
  operator still needs to provision ECS and run the smoke checks.

What is not checked yet:

- Alibaba Cloud deployment proof from an actual ECS instance;
- SO-101 or true webcam physical frame source;
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
