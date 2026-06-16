# Alibaba ECS Manual Deploy Path 2026-06-15

Issue: https://github.com/omarespejel/accountable-swarm/issues/4

This is a manual deployment path. Do not give cloud-console credentials to an
agent. The operator provisions ECS, configures security groups, sets secrets,
and runs the commands.

## Sources Checked

- Alibaba Cloud ECS Docker install docs, last updated 2026-01-30:
  https://www.alibabacloud.com/help/en/ecs/user-guide/install-and-use-docker
- Alibaba Cloud ECS security group docs, last updated 2026-03-26:
  https://www.alibabacloud.com/help/en/ecs/user-guide/start-using-security-groups
- Alibaba Cloud Model Studio OpenAI-compatible chat docs, last updated
  2026-03-18:
  https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope
- Alibaba Cloud Model Studio first Qwen API call docs, last updated
  2026-03-24:
  https://www.alibabacloud.com/help/en/model-studio/first-api-call-to-qwen
- Alibaba Cloud Model Studio API key docs, last updated 2026-03-24:
  https://www.alibabacloud.com/help/en/model-studio/get-api-key

## ECS Operator Checklist

1. Prepare a non-secret operator proof pack from the commit you intend to
   deploy:

```bash
python3 scripts/prepare_ecs_operator_pack.py --commit "$(git rev-parse HEAD)"
```

This writes `runs/ecs/operator-pack/README.md`,
`runs/ecs/operator-pack/operator_commands.sh`,
`runs/ecs/operator-pack/.env.template`, and
`runs/ecs/operator-pack/manifest.json`. The pack is not itself proof; it is the
operator checklist and pinned command set for the ECS run.

1. Create an ECS Linux instance.
1. Install Docker using Alibaba's current ECS Docker guide.
1. Configure a security group:
   - allow SSH only from the operator IP;
   - allow TCP `8000` only from the operator IP for smoke testing;
   - do not open the demo port publicly for the first proof.
1. Clone the public repo:

```bash
git clone https://github.com/omarespejel/accountable-swarm.git
cd accountable-swarm
```

1. Create a local `.env` on the ECS host. Do not commit it:

```bash
umask 077
cat > .env <<'EOF'
ALIBABA_API_KEY=replace-with-operator-secret
QWEN_VL_MODEL=qwen3-vl-flash
EOF
```

1. Build and run:

```bash
docker build -t accountable-swarm:ecs .
docker run --rm --env-file .env -p 8000:8000 accountable-swarm:ecs
```

The Docker image builds the deterministic swarm demo bundle during
`docker build`, so a fresh container can serve `/swarm-demo` and
`/swarm-demo/summary.json` without depending on untracked local `runs/`
artifacts. The image pins `SWARM_DEMO_BUNDLE_DIR=/app/runs/demo/swarm` and
builds the bundle to that same path.

1. In another shell, run smoke checks:

```bash
curl -fsS http://127.0.0.1:8000/healthz
curl -fsS http://127.0.0.1:8000/readyz
curl -fsS http://127.0.0.1:8000/camera-fixture
curl -fsS http://127.0.0.1:8000/swarm-demo
curl -fsS http://127.0.0.1:8000/swarm-demo/summary.json
curl -fsS 'http://127.0.0.1:8000/qwen-ping?model=qwen-plus'
```

Then collect the sanitized machine-readable proof report:

```bash
mkdir -p runs/ecs
python3 -m scripts.collect_ecs_smoke_report \
  --base-url http://127.0.0.1:8000 \
  --commit "$(git rev-parse HEAD)" \
  --out runs/ecs/ecs_smoke_report.json
python3 -m json.tool runs/ecs/ecs_smoke_report.json
```

Alternatively, after generating the operator pack, run its command script from
the repository root on the ECS host:

```bash
runs/ecs/operator-pack/operator_commands.sh
```

## Expected Proof

The deployment proof is complete only when the operator records:

- ECS instance region and OS image, without secrets;
- commit SHA deployed;
- Docker image build command;
- `curl /healthz` output;
- `curl /camera-fixture` output with a 64-character `trace_summary_sha`;
- `curl /swarm-demo/summary.json` output with `outcome: GO`;
- `curl /qwen-ping?model=qwen-plus` output with `status: ok`;
- `runs/ecs/ecs_smoke_report.json` with top-level `outcome: GO`;
- screenshot or terminal log showing this ran on ECS.

## Local Server Smoke

The server path was smoke-tested locally before ECS provisioning:

```bash
set -a
. ./.env
set +a
python3 scripts/serve_demo.py --host 127.0.0.1 --port 8765
```

Smoke results:

```text
GET /healthz
{"service":"accountable-swarm","status":"ok"}

GET /readyz
{"default_vl_model":"qwen3-vl-flash","has_alibaba_api_key":true,"status":"ok"}

GET /camera-fixture
{"decision":"VETO","schema_version":"decisiontrace.v2","status":"ok","trace_summary_sha":"35152f4411566df7d2f886b17793a5339d197ea5c33e75b6c4b9a8ea19bfd81d"}

GET /qwen-ping?model=qwen-plus
{"content_prefix":"OK.","model":"qwen-plus","status":"ok"}
```

The ECS proof is still pending until the same checks run on an Alibaba ECS
instance.

## Non-Claims

This manual path does not prove:

- public production hosting;
- physical robot safety;
- SO-101 connectivity;
- physical swarm behavior;
- latency or reliability;
- Qwen onboard execution.
