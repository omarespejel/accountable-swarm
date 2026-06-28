# ECS Operator Proof Pack 2026-06-16

Issue: #91

## Thesis

The ECS proof path should be operator-run, but the repo can still reduce proof
capture risk by generating a non-secret pack with the exact pinned commit,
commands, evidence slots, and code-file links needed for the hackathon.

## GO Gate

The new pack generator is GO when:

- it writes `runs/ecs/operator-pack/manifest.json`;
- it writes an operator runbook and command script;
- it writes a `.env.template` with non-secret configuration placeholders;
- the manifest pins a valid Git commit;
- the command script requires ECS region, ECS instance ID, ECS public IP, and
  a public endpoint base URL before collecting proof;
- the command script invokes `collect_ecs_smoke_report` in `ecs-public` mode;
- generated text and manifest contain no key material;
- tests cover the GO path and malformed-commit NARROW path.

## Command

```bash
python3 scripts/prepare_ecs_operator_pack.py --commit "$(git rev-parse HEAD)"
```

Expected local output:

```text
outcome GO
manifest runs/ecs/operator-pack/manifest.json
runbook runs/ecs/operator-pack/README.md
commands runs/ecs/operator-pack/operator_commands.sh
env_template runs/ecs/operator-pack/.env.template
```

## Operator Boundary

This pack is not the ECS proof. The actual proof still requires the operator to
provision Alibaba ECS, fill `.env` on the ECS host, run Docker, and collect
`runs/ecs/ecs_smoke_report.json` with `outcome: GO` and
`proof_mode: ecs-public`. A localhost smoke report is only `NARROW_CLAIM`.

## Non-Claims

- not an ECS deployment proof;
- not a production hosting claim;
- not public availability;
- not latency or reliability;
- not physical robot behavior;
- not SO-101 operation;
- not Qwen onboard execution.
