# Camera GO Gate 2026-06-15

Issue: https://github.com/omarespejel/accountable-swarm/issues/2

Started: 2026-06-15 01:00 JST

## Gate

Convert one edge frame into:

```text
frame source -> Qwen/fixture/degraded mode -> normalized bbox validation
-> pixel bbox -> local hold/veto -> DecisionTrace -> replay -> gate report
```

The CLI is:

```bash
python3 scripts/run_camera_go_gate.py \
  --image runs/go_gate/hazard_marker.png \
  --mode dashscope \
  --trace-out runs/go_gate/camera_qwen_trace.json \
  --report-out runs/go_gate/camera_qwen_report.json
python3 -m scripts.verify_trace runs/go_gate/camera_qwen_trace.json
```

The generated `runs/**` outputs are intentionally ignored. This doc records the
small evidence summary without committing model response payloads or local run
artifacts.

## Current Result

`GO` for generated static-frame live Qwen mode.

The five binary pass conditions were all true:

```text
model_responded: true
json_validated: true
bbox_rescaled: true
trace_replay_deterministic: true
frame_emits_decisiontrace_schema: true
```

Result:

```text
outcome GO
trace_summary_sha 214d4edb89537ecf6c8060b2e4fcd6053497aa20439b65cca8641ef8d0e011c8
verified runs/go_gate/camera_qwen_trace.json
summary_sha 214d4edb89537ecf6c8060b2e4fcd6053497aa20439b65cca8641ef8d0e011c8
```

## Local Validation

```bash
./scripts/local_gate.sh
```

Result:

```text
Ran 26 tests
OK
local gate passed
```

## Degraded Mode

The same CLI supports explicit degraded mode:

```bash
python3 scripts/run_camera_go_gate.py \
  --image fixtures/hazard_marker.ppm \
  --mode degraded \
  --trace-out runs/go_gate/camera_degraded_trace.json \
  --report-out runs/go_gate/camera_degraded_report.json
```

Degraded mode emits a `HOLD` decision and a replayable trace without calling
Qwen. It is a weak-network/offline behavior, not a perception success claim.

## Non-Claims

This result does not prove:

- physical robot motion;
- SO-101 connectivity;
- safety;
- latency or reliability;
- swarm behavior;
- Alibaba ECS deployment.

## Next Gate

Use `--capture-webcam runs/go_gate/webcam_frame.png` on a machine with
`imagesnap` or `opencv-python` camera access, then rerun the same gate and
record whether a real sensor frame preserves the same schema and pass
conditions. Webcam images and traces may be kept untracked if they include
private environment details.
