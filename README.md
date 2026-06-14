# accountable-swarm

Accountable Swarm is a Qwen Cloud EdgeAgent hackathon project for accountable
edge-cloud robotics. The first goal is not a large swarm. The first goal is a
reproducible decision trace:

```text
edge sensor frame -> Qwen keyframe check -> local decision -> hash-chained trace -> replay
```

The project is intentionally split into two tracks:

- **Submission repo:** this repository, with a clean license, a runnable GO gate,
  Alibaba Cloud proof artifacts, and judge-friendly setup.
- **Upstream work:** a separate DimOS fork branch for any `DroneFleetConnection`
  or multi-drone scene work that is useful to contribute back.

## Review Setup

This repo is configured for PR review by CodeRabbit and Qodo:

- CodeRabbit: `.coderabbit.yaml`
- Qodo: `.pr_agent.toml`
- Repo review rules: `AGENTS.md`
- Bot triage policy: `docs/engineering/review-bot-policy.md`

The GitHub apps still need to be installed/enabled in their dashboards for the
repository. Repo-side config alone does not grant either bot access.

## Current Build Gate

The first useful success is:

```text
one image/frame -> qwen3-vl-flash bbox JSON -> normalized-coordinate rescale
-> DecisionTrace JSON -> deterministic hash-chain replay
```

No swarm, SO-101, Qwen latency, reliability, or production-readiness claim is
made until this gate passes with checked-in evidence.
