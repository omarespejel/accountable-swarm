# Live DashScope Swarm Mission Suite 2026-06-15

Issue: #37

## Thesis

The low-rate live DashScope mission path can run across the then-reviewed swarm
scenario registry while local deterministic code keeps scenario selection,
mission id, agent count, tick budget, planning, and collision checks bounded.

## Scope

This is a live model evidence gate for `qwen-plus` mission intent across the
scenario registry reviewed at the time this evidence was recorded:

- `corridor`
- `center-block`
- `vertical-slalom`
- `horizontal-slalom`

For each case Qwen returns only an `objective` string. Local code binds the
reviewed scenario and runs the deterministic integer-grid simulator.

The current registry also includes `double-chicane`; rerun this live suite
before making a five-scenario live-Qwen claim.

## Commands

The API key was loaded from local environment state and was not printed or
committed.

```bash
set -a; . ./.env; set +a
python3 scripts/run_swarm_mission_suite.py \
  --mode dashscope \
  --model qwen-plus \
  --trace-root runs/swarm/live-mission-suite \
  --report-out runs/swarm/live_mission_suite_report.json
python3 scripts/verify_swarm_mission_suite.py \
  --trace-root runs/swarm/live-mission-suite \
  --report runs/swarm/live_mission_suite_report.json \
  --report-out runs/swarm/live_mission_suite_verify_report.json
```

## Observed Output

```text
outcome GO
mode dashscope
model qwen-plus
case_count 4
case mission-corridor-dashscope-qwen-plus-n4-go scenario corridor expected GO actual GO
case mission-center-block-dashscope-qwen-plus-n4-go scenario center-block expected GO actual GO
case mission-vertical-slalom-dashscope-qwen-plus-n4-go scenario vertical-slalom expected GO actual GO
case mission-horizontal-slalom-dashscope-qwen-plus-n4-go scenario horizontal-slalom expected GO actual GO
wrote runs/swarm/live-mission-suite
wrote runs/swarm/live_mission_suite_report.json

outcome GO
case_count 4
case mission-corridor-dashscope-qwen-plus-n4-go actual GO verified True
case mission-center-block-dashscope-qwen-plus-n4-go actual GO verified True
case mission-vertical-slalom-dashscope-qwen-plus-n4-go actual GO verified True
case mission-horizontal-slalom-dashscope-qwen-plus-n4-go actual GO verified True
wrote runs/swarm/live_mission_suite_verify_report.json
```

## Pass Conditions

- every then-reviewed scenario was covered;
- every child live mission-gate command exited successfully;
- every child mission-gate report was `GO`;
- every persisted mission trace replayed to the recorded summary SHA;
- every persisted agent trace replayed to the recorded summary SHA;
- every trace-derived replay reported zero same-cell, swap, and
  obstacle-occupancy violations;
- the suite verifier reloaded persisted traces from disk and returned `GO`.

## Evidence

Mission trace summary SHAs:

```text
corridor           258232a4d85386e60bcabdeeea8725873f24fb37a1a5b0803d9bc4cd566b21a6
center-block       5fb552f8dd758c71085cc1a1dfcc9db6f62ab35d39551d97211e306a600ebdb1
vertical-slalom    0a169281093230e58597f1b51f156e42fe0ad7f6576e8268c1e7a136aba9baaa
horizontal-slalom  5614eb0fed719780de5f88ba39de8010f952824a70a26ceedbd7d4a881cff7c8
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
```

## GO Gate

This gate is `GO` for live `qwen-plus` mission intent across the current
reviewed scenario registry. The claim is limited to the listed scenarios and
the deterministic integer-grid simulator.

## Non-Claims

- No physical robot behavior.
- No SO-101 operation.
- No 3D physics simulation.
- No latency or reliability claim.
- No DimOS integration.
- No Alibaba ECS deployment proof.
- No Qwen real-time control.
- No arbitrary-map planner claim.
- No larger-swarm claim beyond the listed deterministic integer-grid cases.
