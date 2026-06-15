# Alibaba / DashScope Proof 2026-06-14

Issue: https://github.com/omarespejel/accountable-swarm/issues/4

This document records the non-secret Alibaba / DashScope proof path. It does
not contain API keys, cloud-console state, or committed provider responses.

## Code Surfaces

- `accountable_swarm/qwen/client.py`
- `scripts/run_go_gate.py`
- `scripts/run_camera_go_gate.py`
- `scripts/qwen_model_ping.py`
- `accountable_swarm/server.py`
- `docs/engineering/alibaba-ecs-manual-deploy-2026-06-15.md`

## Required Local Secret

Set the key outside git:

```bash
export ALIBABA_API_KEY=replace-with-operator-secret
```

Or use a local untracked `.env`:

```bash
umask 077
cat > .env <<'EOF'
ALIBABA_API_KEY=replace-with-operator-secret
QWEN_VL_MODEL=qwen3-vl-flash
EOF
```

## Model Availability Checks

These commands were validated locally with an untracked key:

```bash
python3 scripts/qwen_model_ping.py --models qwen-plus qwen3.5-plus
```

Observed model availability:

```text
qwen-plus: OK
qwen3.5-plus: OK
```

## Live Vision GO-Gate Check

Generate the fixture image and call DashScope:

```bash
python3 scripts/make_hazard_fixture.py runs/go_gate/hazard_marker.png
python3 -m scripts.run_go_gate \
  --image runs/go_gate/hazard_marker.png \
  --mode dashscope \
  --model "${QWEN_VL_MODEL:-qwen3-vl-flash}" \
  --out runs/go_gate/qwen_live_trace.json
python3 -m scripts.verify_trace runs/go_gate/qwen_live_trace.json
```

Observed trace verification:

```text
summary_sha a88d76bfee2dc8ec86725fa369b60d8c50b577214accf41c9613b709f78c5440
verified runs/go_gate/qwen_live_trace.json
```

## Live Mission Suite Check

The current reviewed mission suite uses `qwen-plus` for low-rate mission
intent, then local deterministic code owns scenario binding, simulation, and
trace replay:

```bash
python3 scripts/run_swarm_mission_suite.py \
  --mode dashscope \
  --model qwen-plus \
  --trace-root runs/swarm/live-mission-suite-after-objective-hardening \
  --report-out runs/swarm/live_mission_suite_after_objective_hardening_report.json
python3 scripts/verify_swarm_mission_suite.py \
  --trace-root runs/swarm/live-mission-suite-after-objective-hardening \
  --report runs/swarm/live_mission_suite_after_objective_hardening_report.json \
  --report-out runs/swarm/live_mission_suite_after_objective_hardening_verify_report.json
```

Observed status:

```text
outcome GO
mode dashscope
model qwen-plus
case_count 5
```

## ECS Proof Boundary

The local DashScope proof is complete. The Alibaba ECS deployment proof remains
pending until the operator runs
`docs/engineering/alibaba-ecs-manual-deploy-2026-06-15.md` on an actual ECS
instance and records endpoint, region, deployed commit, command transcript, and
non-secret smoke responses.

## Non-Claims

- No production hosting claim.
- No Alibaba ECS deployment proof yet.
- No latency or reliability claim.
- No physical robot behavior.
- No SO-101 operation.
- No Qwen onboard execution.
