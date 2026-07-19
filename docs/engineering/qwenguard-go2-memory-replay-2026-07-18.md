# QwenGuard Go2 memory replay

Date: 2026-07-18

## Decision

Ship a privacy-safe, deterministic post-run policy simulation built from one
recorded two-pass scene change. These four phases were not robot-runtime
transitions, and the replay does not demonstrate autonomous robot control:

```text
VERIFIED baseline -> PROVISIONAL change -> HOLD -> REVERIFY request
```

An ambiguous change remains `PROVISIONAL`. `HOLD` has no motor authority, and
`REVERIFY` requests another observation rather than certifying the change.

## Evidence boundary

`fixtures/qwenguard_memory/observations.json` contains only hashes, dimensions,
model-reported integer boxes, and provenance receipts. Raw images, raw databases,
absolute paths, people, and room identifiers are excluded.

The recorded source events describe a verified baseline belief at confidence
`500` and a moved update at `750`. Those values are internal Memory2 belief
confidence, not Qwen detection confidence. The post-run simulation applies a
more conservative policy to the receipts; it does not claim the source runtime
emitted `PROVISIONAL`, `HOLD`, or `REVERIFY` transitions.

The source pipeline stored the model's box integers without a verified rescale.
The fixture therefore preserves those values as receipts under
`model_reported_integer_bbox_unscaled`. It does not pass them to
`PerceptionEvent` as calibrated object geometry. Each trace perception covers the
full source frame and links to the frame through `sha256://...`.

`fixtures/qwenguard_memory/manifest.json` also records hashes and topic-row
counts for the two teleoperated Go2 captures. Those hashes are custody receipts;
they do not make the private source databases publicly verifiable. The semantic
frames came from the fixed independent Gemini 2 camera. The Go2 hashes are
separate context receipts, not the semantic frame source.

## Run and verify

From a clean clone:

```bash
python3 -m pip install -e .
run-qwenguard-memory-replay
verify-qwenguard-memory-replay
```

The first command writes:

```text
runs/submission/qwenguard-memory/trace.json
runs/submission/qwenguard-memory/report.json
```

The verifier rebuilds the expected replay from the checked fixture, verifies the
DecisionTrace hash chain, enforces the four transitions, and compares both
persisted artifacts byte-semantically. A correctly rehashed trace with a skipped
transition, extra command key, or motor authority still fails semantic
verification.

The same replay is available from the local demo server:

```text
GET /qwenguard-memory-fixture
```

The ECS smoke collector reconstructs and semantically verifies the returned
trace. The endpoint is deterministic and does not call a paid model. Live Qwen
Cloud proof remains a separate `/qwen-vl-fixture` check.

From the deployed commit on the ECS host, collect the sanitized public proof:

```bash
python3 -m scripts.collect_ecs_smoke_report \
  --base-url "http://<ecs-public-ip>:8000" \
  --proof-mode ecs-public \
  --commit "$(git rev-parse HEAD)" \
  --qwen-model qwen3-vl-flash \
  --ecs-region ap-southeast-1 \
  --ecs-instance-id "<ecs-instance-id>" \
  --ecs-public-ip "<ecs-public-ip>" \
  --out runs/ecs/ecs_smoke_report.json
```

The expected artifact is `runs/ecs/ecs_smoke_report.json`. A submission claim
requires `outcome: GO`; `local-smoke` output is not deployment proof.

## Checked invariants

- exactly four events at ticks 0 through 3;
- exact simulated `VERIFIED`, `PROVISIONAL`, `HOLD`, `REVERIFY` policy phases;
- baseline and conflicting frame and observation hashes differ;
- `HOLD` and `REVERIFY` retain the same conflicting receipt;
- every command has `motor_authority: none` and `motion_executed: false`;
- raw floats, boolean-as-integer values, duplicate JSON keys, unknown fixture
  fields, absolute output paths, and repository path traversal are rejected;
- trace and report output is canonical and deterministic.

## Claims

- Real Go2 camera, LiDAR-topic, odometry, and TF streams were recorded during
  teleoperation; the public manifest contains their database receipts.
- A Qwen-attributed pipeline persisted an ambiguous `moved` candidate from two
  fixed-camera observations.
- The public fixture deterministically demonstrates a no-motion post-run policy
  simulation and its hash-linked receipts.

## Non-claims

- no autonomous or Qwen-directed Go2 motion;
- no Qwen execution in the real-time motor loop;
- no claim that the simulated policy phases ran in the robot runtime;
- no human-labeled ground truth or independently verified Qwen accuracy;
- no calibrated image displacement or validated 3D grounding;
- no cross-device hardware synchronization;
- no Alibaba ECS deployment proof until the ECS collector is run on the final
  public commit and the required Workbench evidence is captured.
