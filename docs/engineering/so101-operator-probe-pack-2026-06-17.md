# SO-101 Operator Probe Pack 2026-06-17

Issue: https://github.com/omarespejel/accountable-swarm/issues/81

## Thesis

Once the repo has a controlled SO-101 camera probe, the next useful artifact is
an operator-run setup pack that points at the current official LeRobot install
and camera flow instead of making the next session rediscover those commands.

## What changed

Added `scripts/prepare_so101_operator_probe_pack.py`.

The command:

```bash
python3 -m scripts.prepare_so101_operator_probe_pack \
  --out-dir runs/physical/so101-operator-pack \
  --camera-name so101_overhead \
  --camera-id 0
```

emits:

- `README.md`
- `operator_commands.sh`
- `manifest.json`

## Scope

This pack is not a hardware-success artifact. It prepares a reproducible,
non-secret path for the operator to:

1. install LeRobot,
2. install Feetech support,
3. install OpenCV,
4. discover the camera id with `lerobot-find-cameras opencv`,
5. run the trace-only SO-101 probe.

## Local validation

```bash
python3 -m unittest tests.test_so101_operator_probe_pack_cli
python3 -m scripts.prepare_so101_operator_probe_pack --out-dir runs/physical/so101-operator-pack-smoke
git diff --check
```

## Non-Claims

This does not prove:

- SO-101 connectivity;
- SO-101 camera success;
- autonomous motion;
- ACT policy success;
- safety, latency, or reliability;
- physical swarm behavior.
