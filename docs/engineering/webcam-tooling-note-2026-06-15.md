# Webcam Tooling Note 2026-06-15

The camera GO-gate supports:

```bash
python3 scripts/run_camera_go_gate.py \
  --capture-webcam runs/go_gate/webcam_frame.png \
  --mode dashscope \
  --trace-out runs/go_gate/webcam_qwen_trace.json \
  --report-out runs/go_gate/webcam_qwen_report.json
```

On this machine, true webcam capture is not yet runnable:

```text
imagesnap: not found
opencv-python: not installed
```

This is a tooling/permission blocker, not a trace-schema blocker. The same gate
already works with a static image and live Qwen. To clear this issue, install
one capture path and grant camera permission:

- macOS option: install `imagesnap`;
- Python option: install `opencv-python` in a local environment;
- fallback: provide a phone/laptop camera image file and run `--image`.

Do not add autonomous robot motion while clearing this blocker.
