# ECS Smoke Proof Collector 2026-06-15

Issue: https://github.com/omarespejel/accountable-swarm/issues/91

## Thesis

The Alibaba ECS proof should be collected with one repeatable command that
queries the deployed server endpoints and writes a sanitized JSON report.

## Why It Matters

Manual `curl` transcripts are easy to miss or over-claim. A proof collector
makes the deployment evidence machine-readable while keeping secrets and raw
provider responses out of git.

## Artifact

- `scripts/collect_ecs_smoke_report.py`
- package entry point: `collect-ecs-smoke-report`
- expected report path: `runs/ecs/ecs_smoke_report.json`

## GO Gate

The collector reports `GO` only when all of these pass:

- `/healthz` returns `status: ok` and `service: accountable-swarm`;
- `/readyz` returns `status: ok` and confirms an Alibaba API key is present;
- `/camera-fixture` returns a verified `VETO` DecisionTrace summary SHA;
- `/swarm-demo` serves HTML;
- `/swarm-demo/summary.json` reports `outcome: GO`;
- `/qwen-ping?model=qwen-plus` returns `status: ok`;
- the deployed commit SHA is recorded;
- `--proof-mode ecs-public` is used;
- ECS region, instance ID, and global public IP are recorded;
- the checked `--base-url` is a public endpoint, not localhost or a private IP;
- an IP-literal `--base-url` matches `--ecs-public-ip`.

Any failed condition produces `NARROW_CLAIM` and exits non-zero unless the
operator explicitly passes `--allow-narrow-claim`.

## Operator Command

Run this against the ECS public endpoint after the Docker container is running.
`local-smoke` mode and localhost are useful diagnostics, but they intentionally
produce `NARROW_CLAIM` rather than deployment proof.

```bash
mkdir -p runs/ecs
collect-ecs-smoke-report \
  --base-url "http://${ECS_PUBLIC_IP}:8000" \
  --commit "$(git rev-parse HEAD)" \
  --proof-mode ecs-public \
  --ecs-region "${ECS_REGION}" \
  --ecs-instance-id "${ECS_INSTANCE_ID}" \
  --ecs-public-ip "${ECS_PUBLIC_IP}" \
  --out runs/ecs/ecs_smoke_report.json
python3 -m json.tool runs/ecs/ecs_smoke_report.json
```

The same command can be run as a module if the package entry point is not
installed:

```bash
python3 -m scripts.collect_ecs_smoke_report \
  --base-url "http://${ECS_PUBLIC_IP}:8000" \
  --commit "$(git rev-parse HEAD)" \
  --proof-mode ecs-public \
  --ecs-region "${ECS_REGION}" \
  --ecs-instance-id "${ECS_INSTANCE_ID}" \
  --ecs-public-ip "${ECS_PUBLIC_IP}" \
  --out runs/ecs/ecs_smoke_report.json
```

## Local Validation

The collector is tested against a local fake ECS server:

```bash
python3 -m unittest tests.test_ecs_smoke_report_cli
```

Covered cases:

- full endpoint set plus public ECS metadata returns `GO`;
- localhost/default `local-smoke` mode returns `NARROW_CLAIM`;
- missing Qwen/API-key proof returns `NARROW_CLAIM` and exit code `4`;
- `--allow-narrow-claim` writes the report with exit code `0` for diagnostic
  capture.

## Non-Claims

- Not an Alibaba ECS deployment proof until run on an actual ECS instance.
- Not a public production hosting claim.
- Not a latency or reliability claim.
- Not physical robot behavior.
- Not SO-101 operation.
- Not Qwen onboard execution.
