# Swarm Mission Suite 2026-06-15

## Thesis

The low-rate mission path should be exercised as a scenario-registry suite, not
only as a one-off fixture command. The suite strengthens the accountable swarm
claim by proving that reviewed mission scenarios can be selected, traced,
persisted, and replayed deterministically without placing Qwen in the
real-time control loop.

## Scope

This is a fixture-only mission assignment gate. It calls
`scripts/run_swarm_mission_gate.py` once per reviewed mission scenario and then
reloads the generated mission and agent traces from disk.

Current covered mission scenarios:

- `corridor`
- `center-block`
- `vertical-slalom`
- `horizontal-slalom`

## Command

```bash
python3 scripts/run_swarm_mission_suite.py \
  --trace-root runs/swarm/mission-suite \
  --report-out runs/swarm/mission_suite_report.json
```

## Result

```text
outcome GO
case_count 4
case mission-corridor-fixture-n4-go scenario corridor expected GO actual GO
case mission-center-block-fixture-n4-go scenario center-block expected GO actual GO
case mission-vertical-slalom-fixture-n4-go scenario vertical-slalom expected GO actual GO
case mission-horizontal-slalom-fixture-n4-go scenario horizontal-slalom expected GO actual GO
wrote runs/swarm/mission-suite
wrote runs/swarm/mission_suite_report.json
```

## Pass Conditions

- all fixture mission cases matched expected `GO`;
- every child mission-gate command exited successfully;
- every persisted mission trace replayed to the recorded summary SHA;
- every persisted agent trace replayed to the recorded summary SHA;
- every simulator report was `GO`;
- every trace-derived replay reported zero same-cell, swap, and
  obstacle-occupancy violations;
- every reviewed mission scenario from the registry was covered.

## Evidence

Mission trace summary SHAs:

```text
corridor           8aa35324b9b2b36e2f17b22b348b8febe6d0829dec3781a085e7c484c819b8a8
center-block       82e2138ee3f93e3468ebb04dd179c5c304688cc2ff243dbf129985d56927fcde
vertical-slalom    4b9203963703f4b7960a690ed0b3691babfdf424311596a6d866cec0639d3afc
horizontal-slalom  2a75abfc4cdf17f903f80787c23689819b2af4b891ae0e8113c5c8a1232f849a
```

Agent trace summary SHAs:

```text
mission-corridor-fixture-n4-go
  sim-agent-0 74b94d2e813442be4b05fa5e6b81fe3fb91d4878e5ef86574a3bedddd678517c
  sim-agent-1 c4c507dde871a77d41dd80fd2992499895587bb41de93cb6f30d9e389bb611ee
  sim-agent-2 2710d20af5acad036c154519b9c72302d3413c39b0d7c6fde4230ff27f78e2c0
  sim-agent-3 5a3710f1324ff8d1383bbea948dce1459985ac03a44386ca280595b6d8fe9f0b

mission-center-block-fixture-n4-go
  sim-agent-0 43af1fb934c620bfcd7995bac4538141c59652c7161cd6e577abc796633aa300
  sim-agent-1 8de4062160df5349f5809b9b58ff18eb7237adcee393c973cc164e1ddbac2284
  sim-agent-2 2a8bb7802957c6b3e13d42baa5481c5a6cb65dc17619278a8eeaca5502072932
  sim-agent-3 2bc65322b094a7f13bedbe30ba26181b5134a90f962378a66cb10922cceb9902

mission-vertical-slalom-fixture-n4-go
  sim-agent-0 90aaa600b5717ecda5a96bd9a7a821eafa4270c31840ace2f8ac80f5c304da46
  sim-agent-1 e90eae1d3fc925898366ca9bf8a493b34eb78022239d427bb21ea1684d95e3dd
  sim-agent-2 4e90803b397f52150908e91cecd6c451fe6e0197d4d92901f129ad7ee8ad46ea
  sim-agent-3 1bc42f1f57341280de1e562d623d95e3e95d21b93ccf2d824b93840e0a0713c1

mission-horizontal-slalom-fixture-n4-go
  sim-agent-0 283e6069b0a2ee992b3dcca3dc1131f6532824e7ebf85831578534608adee90f
  sim-agent-1 434e1ba89dc0fbaae215595abf2cdffa6f950dcbac17944342215bee95ed8331
  sim-agent-2 79c6e6a6f938368496a2d1ef388b0fbe56468e241ea59c3cf01e23b9cd86dc95
  sim-agent-3 93f5a811f6f5631f684e3a3716abc7b01fee28bb2dd1bcb57906e6f74413ed92
```

## Non-Claims

- no live Qwen mission assignment;
- no physical robot behavior;
- no SO-101 operation;
- no 3D physics simulation;
- no latency or reliability claim;
- no DimOS integration;
- no arbitrary-map planner claim;
- no larger-swarm claim beyond the listed deterministic integer-grid cases.
