# QwenGuard Motion Interlock Decision 2026-06-29

## Thesis

Issue #122 identified a real safety and claim boundary: the repository has
verified QwenGuard no-motion traces, and it can generate LeRobot SO-101
operator commands, but it does not yet bind a fresh `ALLOW` gate decision to the
immediate command that moves the robot.

## Decision

A code interlock is required before any public or internal claim that SO-101
motion was programmatically gated by QwenGuard.

Until that interlock exists, the supported paths are:

- SO-101 camera capture through the trace-only camera probe;
- fixture and degraded no-motion `decisiontrace.v2` evidence;
- generation of LeRobot training/evaluation runbooks;
- manually operated LeRobot data collection or rollout, labeled as manual
  operator execution and not as programmatically gated QwenGuard motion.

## Required Interlock For A Future Gated-Motion Claim

A future implementation must bind all of the following immediately before the
actuating command:

- a fresh local `evaluate_outcome_gate(...)` result with `gate_decision=ALLOW`;
- `PhysicalNodeSafety.assert_safe_for_motion()` with operator arming, motion
  enablement, emergency stop, low-speed mode, and workspace bounds enabled;
- an actuation wrapper or sink that is the only route to the LeRobot motion
  command;
- a `decisiontrace.v2` event or linked artifact that records the gate decision,
  safety state, control label, and exact policy command boundary.

## Current Hardening

The generated physical GO pack now states this non-claim before any motion
phase. The generated SO-101 training pack now requires explicit manual operator
acknowledgements for:

- emergency stop readiness;
- low-speed mode;
- workspace bounds;
- leader detached or non-authoritative before autonomous policy rollout.

Those acknowledgements reduce accidental execution risk, but they are not a
QwenGuard ALLOW-to-LeRobot software interlock.

## GO / NO-GO

GO:

- connect SO-101 for camera/no-motion checks;
- capture a camera frame through `capture-so101-camera-frame`;
- generate training packs and review commands;
- run fixture/degraded no-motion traces.

NO-GO:

- call any autonomous SO-101 motion "QwenGuard gated";
- claim physical success, safety, reliability, or measured `N/10` from manually
  edited or unbound evidence;
- run autonomous policy rollout without a human operator's safety checklist and
  honest `AUTONOMOUS` / `TELEOP` / `SCRIPTED` labeling.

## Non-Claims

- This does not implement physical actuation.
- This does not prove SO-101 connectivity.
- This does not prove ACT policy success.
- This does not certify safety.
- This does not prove a latency or reliability number.
