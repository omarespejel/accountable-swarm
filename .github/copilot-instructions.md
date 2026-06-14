# Accountable Swarm Repository Instructions

Start with `AGENTS.md` and `.codex/START_HERE.md`.

This repo is a research lab for accountable edge-cloud robotics. Treat issues as
hypotheses with GO/NO-GO gates, not generic task buckets.

Prioritize:

- deterministic `DecisionTrace` serialization and replay;
- Qwen response validation and normalized bbox handling;
- physical-device safety;
- secret handling;
- separation between cloud reasoning and local control;
- exact reproduction commands;
- public claim boundaries.

Do not:

- put Qwen, LLM, or VLM calls in hard real-time control paths;
- claim onboard Qwen without evidence;
- claim validated 3D grounding unless validated;
- claim physical safety, swarm success, latency, reliability, Alibaba
  deployment, or DimOS integration without checked artifacts;
- make style-only rewrites that widen the PR.

Before proposing a merge, verify the PR body includes exact local validation
commands and non-claims where relevant.
