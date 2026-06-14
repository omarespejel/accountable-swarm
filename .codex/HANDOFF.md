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
- deterministic N=2 integer-grid simulated swarm emits one DecisionTrace per
  agent, reaches goals, and reports zero same-cell or swap collisions.
- deterministic N=2 center-block obstacle scenario reaches goals, reports zero
  obstacle occupancy, and replay recomputes obstacle occupancy from traces.
- deterministic N=4 center-block obstacle scenario reaches goals with the
  bounded reservation planner, reports zero same-cell collisions, zero swap
  collisions, zero obstacle occupancy, and replay recomputes those counts from
  traces.
- low-rate fixture mission assignment validates strict mission JSON, emits a
  mission `DecisionTrace`, then runs the deterministic N=4 center-block swarm
  gate with trace-replayed zero same-cell, swap, and obstacle occupancy counts.
- deterministic swarm scenario suite reruns N=2/N=4 scoped cases, includes an
  expected `NARROW_CLAIM` canary, and verifies persisted agent traces from disk.
- exploratory deterministic N=4 integer-grid probe passes locally, but is not a
  physical, physics, latency, reliability, or larger-swarm claim.
- local-guard-only deterministic N=4 center-block obstacle probe remains useful
  as the prior `NARROW_CLAIM`: it avoids collisions and obstacle occupancy but
  does not reach all goals without the bounded planner.

What is not checked yet:

- Alibaba Cloud deployment proof from an actual ECS instance;
- SO-101 physical frame source;
- DimOS integration;
- physics-backed multi-agent swarm behavior;
- latency, reliability, or safety claims.
- live Qwen mission assignment.

## Active GitHub Work

- Issue #1: research ground truth and build hierarchy.
- Issue #3: physical-node safety contract.
- Issue #4: Alibaba/Qwen proof path.
- Issue #19: deterministic swarm scenario suite.
- Issue #2, #6, #11, #13, #15, and #17 are closed as GO.
- PR #5, #7, #8, #9, #10, #12, #14, #16, and #18 are merged.

Before creating new work, inspect the current PR and issues:

```bash
gh pr list --state open
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
