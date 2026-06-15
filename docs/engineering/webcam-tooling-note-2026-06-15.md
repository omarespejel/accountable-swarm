# Webcam Sensor-Frame Note 2026-06-15

The camera GO-gate supports:

```bash
python3 -m scripts.run_camera_go_gate \
  --capture-webcam runs/go_gate/webcam_frame.png \
  --mode dashscope \
  --trace-out runs/go_gate/webcam_qwen_trace.json \
  --report-out runs/go_gate/webcam_qwen_report.json
```

Local sensor-frame status:

```text
outcome GO
mode dashscope
model qwen3-vl-flash
source_kind webcam_capture
trace_summary_sha b643935f5ea0d326ac468c60cbac4ca46e61bab67584fd8840766a6a2601be9f
pass_conditions.model_responded true
pass_conditions.json_validated true
pass_conditions.bbox_rescaled true
pass_conditions.trace_replay_deterministic true
pass_conditions.frame_emits_decisiontrace_schema true
```

The captured frame and trace are intentionally not committed because they may
include private environment details. This narrows the physical-device blocker
to a safe sensor-frame proof, not SO-101 operation.

To reproduce on another machine, install one capture path and grant camera
permission:

- macOS option: install `imagesnap`;
- Python option: install `opencv-python` in a local environment;
- fallback: provide a phone/laptop camera image file and run `--image`.

Do not add autonomous robot motion while clearing this blocker.
