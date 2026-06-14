# START_HERE

This is the fast local entrypoint for a fresh agent working in this repository.

Read these files before relying on memory, prior chat, or old branch state:

1. `AGENTS.md`
2. `.codex/START_HERE.md`
3. `.codex/research/north_star.yml`
4. `.codex/research/operating_model.yml`
5. `.codex/research/README.md`
6. `.codex/HANDOFF.md`
7. `docs/engineering/reproducibility.md`
8. `docs/engineering/hardening-policy.md`
9. `docs/security/threat-model.md`
10. `docs/engineering/no-claims.md`
11. `docs/engineering/review-bot-policy.md`
12. current active GitHub issue or PR
13. `git status --short --branch`

## Current Local Gate

Run from the repository root:

```bash
./scripts/local_gate.sh
```

If the gate fails, fix the failure or record the blocker before widening the
task. Do not treat GitHub Actions as the normal research loop.

## Default Question

Every non-trivial change must answer:

```text
Did this strengthen, falsify, narrow, or harden the accountable edge-cloud
robotics thesis?
```

If the answer is unclear, open or update a GO/NO-GO issue before editing code.
