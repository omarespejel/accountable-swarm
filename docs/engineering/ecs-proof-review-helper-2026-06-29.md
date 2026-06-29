# ECS Proof Review Helper 2026-06-29

Issue: #91

## Thesis

The Alibaba ECS proof needs both a machine-readable smoke report and a
human-reviewed provider-context artifact. The smoke report proves the checked
endpoint behavior. The review note records that a human inspected the terminal
or screenshot evidence for Alibaba ECS context, public endpoint use, deployed
commit, security-group scope, and secret exposure.

## Change

Added `prepare-ecs-proof-review`, which writes
`runs/ecs/ecs_proof_review.md` only when:

- `runs/ecs/ecs_smoke_report.json` exists;
- the ECS smoke report is `outcome: GO` and `proof_mode: ecs-public`;
- the report asserts verified Alibaba ECS deployment context;
- the terminal or screenshot artifact is an HTTPS URL or an existing
  repo-relative transcript/screenshot/video artifact;
- local text transcripts contain no secret-like material;
- the operator provides all required confirmation flags;
- the generated review note contains no secret-like material.

## Command

```bash
python3 -m scripts.prepare_ecs_proof_review \
  --ecs-report runs/ecs/ecs_smoke_report.json \
  --terminal-artifact runs/ecs/ecs_terminal_proof.txt \
  --reviewed-by YOUR_NAME \
  --review-date YYYY-MM-DD \
  --confirm-report-go \
  --confirm-alibaba-context \
  --confirm-public-endpoint \
  --confirm-deployed-commit \
  --confirm-security-group \
  --confirm-secrets
```

## Non-Claims

- Not an Alibaba ECS proof by itself.
- Not a production hosting claim.
- Not public availability.
- Not latency or reliability.
- Not physical robot behavior.
- Not SO-101 operation.
- Not Qwen onboard execution.
