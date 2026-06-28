# QwenGuard SO-101 Software Spine 2026-06-28

## Thesis

QwenGuard separates cloud semantic reasoning from local motion authority for
the SO-101 demo:

```text
marked cube candidates -> Qwen selector JSON -> local validator
  -> local outcome gate -> local ACT policy intent -> Qwen evaluator
  -> hash-chained decisiontrace.v2
```

This PR builds the claim-safe software spine before hardware is connected. It
does not move the SO-101.

## What changed

- Added `accountable_swarm.qwenguard.selector`.
  - Qwen must select a local Set-of-Mark `target_mark_id`.
  - The selector validates relation, references, bbox, confidence, and evidence.
  - It rejects unknown marks, unsupported relations, missing references, and raw
    float confidence.
  - The local marked candidate remains the source of truth for `target_label`;
    model-provided labels must match the candidate label exactly.
  - `between` requires exactly two distinct reference marks.
- Added `accountable_swarm.qwenguard.evaluator`.
  - The evaluator validates before/after outcome JSON.
  - Outcomes are bounded to `success`, `failure`, or `uncertain`.
  - Failure types are bounded and locally checked.
- Added `accountable_swarm.qwenguard.outcome_gate`.
  - V0 is a deterministic rule gate, not a learned or video-generative world
    model.
  - It returns `ALLOW`, `HOLD`, or `RETRY` plus
    `predicted_success_milli`, `risk_level`, and reasons.
- Added `accountable_swarm.qwenguard.traces`.
  - Selector, gate, action intent, and evaluator events are written into
    `decisiontrace.v2`.
  - No-motion health checks record `motion_executed: false`.
- Added `accountable_swarm.qwenguard.trial`.
  - Trial records support later Qwen-vs-heuristic, gate-on/off, and cloud
    degraded ablations.
- Added `scripts/run_qwenguard_no_motion_health_check.py`.
  - Fixture mode validates selector -> gate -> evaluator -> trace.
  - Degraded mode validates cloud-unavailable -> HOLD.
- Added `scripts/prepare_so101_training_pack.py`.
  - Generates a non-secret operator runbook, command script, and trial CSV
    header for tomorrow's SO-101/ACT session.

## Checked local artifacts

Fixture no-motion health check:

```bash
python3 -m scripts.run_qwenguard_no_motion_health_check \
  --image fixtures/hazard_marker.ppm \
  --mode fixture \
  --policy-available \
  --simulate-safe-motion-authority \
  --fixture-outcome success \
  --trace-out runs/qwenguard/no_motion_trace.json \
  --report-out runs/qwenguard/no_motion_report.json

python3 -m scripts.verify_trace runs/qwenguard/no_motion_trace.json
```

Result:

```text
outcome GO
gate_decision ALLOW
trace_summary_sha 5161920e949b369b73aae52557cccede17a05dda80e90c1d9da0fc52d282a38c
```

Important: this is ALLOW intent inside a no-motion health check. No physical
motion is executed or claimed.

Degraded no-motion health check:

```bash
python3 -m scripts.run_qwenguard_no_motion_health_check \
  --image fixtures/hazard_marker.ppm \
  --mode degraded \
  --policy-available \
  --simulate-safe-motion-authority \
  --trace-out runs/qwenguard/degraded_trace.json \
  --report-out runs/qwenguard/degraded_report.json

python3 -m scripts.verify_trace runs/qwenguard/degraded_trace.json
```

Result:

```text
outcome DEGRADED
gate_decision HOLD
trace_summary_sha 6d7be5d5246f10aafd1af79ee0c7df398fe8aa57bb6e9832073e31621e791042
```

Blocked fixture path:

```bash
python3 -m scripts.run_qwenguard_no_motion_health_check \
  --image fixtures/hazard_marker.ppm \
  --mode fixture \
  --trace-out runs/qwenguard/blocked_trace.json \
  --report-out runs/qwenguard/blocked_report.json
```

Result:

```text
outcome NARROW_CLAIM
gate_decision HOLD
gate_allows_action False
```

SO-101 training pack:

```bash
python3 -m scripts.prepare_so101_training_pack \
  --out-dir runs/physical/qwenguard_so101_training_pack

bash -n runs/physical/qwenguard_so101_training_pack/operator_commands.sh
```

Result:

```text
schema_version qwenguard-so101-training-pack.v1
task pick the red cube left of the green cube and place it in the bin
```

## Targeted validation

```bash
python3 -m unittest \
  tests.test_qwenguard_selector \
  tests.test_qwenguard_evaluator \
  tests.test_qwenguard_outcome_gate \
  tests.test_qwenguard_traces \
  tests.test_qwenguard_health_check_cli \
  tests.test_so101_training_pack_cli \
  tests.test_qwenguard_trial \
  tests.test_qwen_client \
  tests.test_trace
```

Result:

```text
Ran 53 tests in 0.675s
OK
```

Full local gate:

```bash
./scripts/local_gate.sh
```

Result:

```text
Ran 294 tests in 196.221s
OK
local gate passed
```

## GO / NO-GO

Current outcome: `GO` for the no-hardware software spine.

GO evidence:

- Set-of-Mark selector validates fixture relation.
- Selector/evaluator evidence is bounded before validation and stored in trace
  commands as SHA-256 plus character count, not raw model prose.
- Evaluator schema validates fixture and degraded paths.
- Outcome gate emits deterministic `ALLOW` and degraded `HOLD`.
- Fixture-mode health checks cannot report `GO` unless the gate allows action;
  blocked fixture runs report `NARROW_CLAIM`.
- Multi-event `decisiontrace.v2` verifies from disk.
- Mutating the selector command causes trace verification failure.
- JSON-mode Qwen helper rejects blank prompts, non-positive/bool token limits,
  empty content, and malformed DashScope JSON before downstream use.
- Health-check `no_motion_executed` is derived from the replayed trace, not a
  hard-coded assertion.
- Trial records reject malformed enum fields before evaluation data can enter
  later paper/eval tables.
- The SO-101 operator command script shell-quotes unsafe task text, pins the
  LeRobot source ref and OpenCV version, and passes `bash -n`.
- Operator ACT training pack generates without secret material.

Still not checked:

- SO-101 camera frame capture.
- ACT policy training or rollout.
- Physical motion.
- Physical success rate.
- Live Qwen selector/evaluator on SO-101 frames.
- Alibaba ECS proof.
- DimOS runtime consumption.

## Non-claims

- No physical motion.
- No SO-101 connectivity proof.
- No ACT policy success.
- No safety, latency, or reliability claim.
- No Qwen motor-control claim.
- No Qwen onboard claim.
- No validated 3D grasping claim.
- No DimOS runtime execution.
- No Alibaba ECS deployment proof.

## Next step

Once hardware is connected:

1. Run the existing SO-101 camera probe.
2. Capture one SO-101 frame.
3. Run the QwenGuard selector/gate/evaluator path over that frame in no-motion
   mode.
4. Record 50-100 ACT demonstrations.
5. Train/evaluate ACT.
6. Wire policy rollout summary into the existing trace path.
