# Live DashScope Swarm Mission Suite After Objective Hardening 2026-06-15

Issue: #52

## Thesis

After mission objective text hardening, live `qwen-plus` mission intent can still
drive the full reviewed five-scenario swarm registry while local deterministic
code keeps scenario selection, mission id, agent count, tick budget, planning,
and collision checks bounded.

## Scope

This is a live model evidence gate for `qwen-plus` mission intent across the
current reviewed scenario registry:

- `corridor`
- `center-block`
- `vertical-slalom`
- `horizontal-slalom`
- `double-chicane`

For each case Qwen returns only an `objective` string. Local code binds the
reviewed scenario, mission id, agent count, and tick budget before running the
deterministic integer-grid simulator. The hardened objective validator rejects
hidden counts, scenario names, coordinates, arrays, structured payloads, and
control terms inside the objective text.

## Commands

The API key was loaded from local environment state and was not printed or
committed.

```bash
set -a; . ./.env; set +a
python3 scripts/qwen_model_ping.py --models qwen-plus
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

## Observed Output

```text
qwen-plus: OK

outcome GO
mode dashscope
model qwen-plus
case_count 5
case mission-corridor-dashscope-qwen-plus-n4-go scenario corridor expected GO actual GO
case mission-center-block-dashscope-qwen-plus-n4-go scenario center-block expected GO actual GO
case mission-vertical-slalom-dashscope-qwen-plus-n4-go scenario vertical-slalom expected GO actual GO
case mission-horizontal-slalom-dashscope-qwen-plus-n4-go scenario horizontal-slalom expected GO actual GO
case mission-double-chicane-dashscope-qwen-plus-n4-go scenario double-chicane expected GO actual GO
wrote runs/swarm/live-mission-suite-after-objective-hardening
wrote runs/swarm/live_mission_suite_after_objective_hardening_report.json

outcome GO
case_count 5
case mission-corridor-dashscope-qwen-plus-n4-go actual GO verified True
case mission-center-block-dashscope-qwen-plus-n4-go actual GO verified True
case mission-vertical-slalom-dashscope-qwen-plus-n4-go actual GO verified True
case mission-horizontal-slalom-dashscope-qwen-plus-n4-go actual GO verified True
case mission-double-chicane-dashscope-qwen-plus-n4-go actual GO verified True
wrote runs/swarm/live_mission_suite_after_objective_hardening_verify_report.json
```

## Pass Conditions

- every current reviewed scenario was covered;
- every child live mission-gate command exited successfully;
- every child mission-gate report was `GO`;
- every child report used mode `dashscope` and model `qwen-plus`;
- every persisted mission trace replayed to the recorded summary SHA;
- every persisted agent trace replayed to the recorded summary SHA;
- every trace-derived replay reported zero same-cell, swap, and
  obstacle-occupancy violations;
- the suite verifier reloaded persisted traces from disk and returned `GO`.

## Evidence

Mission trace summary SHAs:

```text
corridor           f68cff613d0e972a56b987422b993094d12f2a30b2703877956df226f86b13bf
center-block       3dec9df1f7ccc01fa78431ac681b855c38bea15835905d72d44c3d4196a0260a
vertical-slalom    3dd3122ce42f676acb32ce1d1b677fc9e901b2cde5f7c59e549af3e76caf813d
horizontal-slalom  03751acbd87cfd7859cac481497e45ff0bf1d0f71a341f7ff5209b6d27bc213a
double-chicane     28f545df248f7cc48f35fe50eb7944574f9d972c3d28bd0132bb1f2eebfe45e8
```

Agent trace summary SHAs:

```text
mission-corridor-dashscope-qwen-plus-n4-go
  sim-agent-0 74b94d2e813442be4b05fa5e6b81fe3fb91d4878e5ef86574a3bedddd678517c
  sim-agent-1 c4c507dde871a77d41dd80fd2992499895587bb41de93cb6f30d9e389bb611ee
  sim-agent-2 2710d20af5acad036c154519b9c72302d3413c39b0d7c6fde4230ff27f78e2c0
  sim-agent-3 5a3710f1324ff8d1383bbea948dce1459985ac03a44386ca280595b6d8fe9f0b

mission-center-block-dashscope-qwen-plus-n4-go
  sim-agent-0 43af1fb934c620bfcd7995bac4538141c59652c7161cd6e577abc796633aa300
  sim-agent-1 8de4062160df5349f5809b9b58ff18eb7237adcee393c973cc164e1ddbac2284
  sim-agent-2 2a8bb7802957c6b3e13d42baa5481c5a6cb65dc17619278a8eeaca5502072932
  sim-agent-3 2bc65322b094a7f13bedbe30ba26181b5134a90f962378a66cb10922cceb9902

mission-vertical-slalom-dashscope-qwen-plus-n4-go
  sim-agent-0 90aaa600b5717ecda5a96bd9a7a821eafa4270c31840ace2f8ac80f5c304da46
  sim-agent-1 e90eae1d3fc925898366ca9bf8a493b34eb78022239d427bb21ea1684d95e3dd
  sim-agent-2 4e90803b397f52150908e91cecd6c451fe6e0197d4d92901f129ad7ee8ad46ea
  sim-agent-3 1bc42f1f57341280de1e562d623d95e3e95d21b93ccf2d824b93840e0a0713c1

mission-horizontal-slalom-dashscope-qwen-plus-n4-go
  sim-agent-0 283e6069b0a2ee992b3dcca3dc1131f6532824e7ebf85831578534608adee90f
  sim-agent-1 434e1ba89dc0fbaae215595abf2cdffa6f950dcbac17944342215bee95ed8331
  sim-agent-2 79c6e6a6f938368496a2d1ef388b0fbe56468e241ea59c3cf01e23b9cd86dc95
  sim-agent-3 93f5a811f6f5631f684e3a3716abc7b01fee28bb2dd1bcb57906e6f74413ed92

mission-double-chicane-dashscope-qwen-plus-n4-go
  sim-agent-0 11d4192248137ed0563f5854ab2010412e95146a5df7a72ad6f2423e8391e12e
  sim-agent-1 0eff388c0df65b7fda62c71d0a437e4a5e41a3f17d1e399c077b6a5a04e74a07
  sim-agent-2 3a54d31550cb4d2540293d33223d61fff06228d2e175c3f36f2b12288eb93d1d
  sim-agent-3 fa0c5851820ec9b00c4ae23ef801f6187e64d4f3858b04ff70964ce52da4f0d1
```

## GO Gate

This gate is `GO` for live `qwen-plus` mission intent across the current
reviewed five-scenario registry. The claim is limited to the listed scenarios
and the deterministic integer-grid simulator.

## Non-Claims

- No physical robot behavior.
- No SO-101 operation.
- No 3D physics simulation.
- No latency or reliability claim.
- No DimOS integration.
- No Alibaba ECS deployment proof.
- No live Qwen mission assignment beyond the verified suite report.
- No arbitrary-map planner claim.
- No larger-swarm claim beyond the listed deterministic integer-grid cases.
