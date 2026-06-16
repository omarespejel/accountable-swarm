# Demo Video Shot List

Issue: #59

Target length: under 3 minutes.

## Setup

Run the recording pack:

```bash
python3 scripts/prepare_demo_recording_pack.py
```

Optional local server:

```bash
python3 scripts/serve_demo.py --host 127.0.0.1 --port 8000
```

Record from local files or from:

```text
http://127.0.0.1:8000/swarm-demo
http://127.0.0.1:8000/swarm-demo/summary.json
```

## Shot Sequence

1. Show the repository root, `LICENSE`, `README.md`, and
   `docs/submission/README.md`.
2. Show `runs/demo/recording-pack/manifest.json` and its `outcome`.
3. Open `runs/demo/swarm/index.html`.
4. Open one scenario replay page and show the animated agents moving.
5. Show the same page has static per-tick frames and trace hashes.
6. Open `runs/hazard_formation/recording_x_replay/index.html`.
7. Show the hazard cell obstacle and the four agents moving into the `x`
   formation.
8. Open `runs/hazard_formation/recording_x_report.json`.
9. Show the hazard bbox, hazard cell, `x` formation, assigned goals, and
   trace summary hashes.
10. Say the default fixture-recording boundary on camera:

    ```text
    This recording shows the local audited execution path using a fixture
    Qwen-style bbox. Live Qwen evidence is recorded separately. Local
    deterministic code owns motion, and every promoted action is replayable
    from hash-chained traces.
    ```

11. Show the non-claims in `runs/demo/recording-pack/shotlist.md`.

## Optional DimOS Bridge Insert

Only include this if `prepare-dimos-bridge-pack` has already produced a local
manifest:

```bash
python3 scripts/build_swarm_demo_bundle.py --out-dir runs/demo/dimos-bridge-source
python3 scripts/prepare_dimos_bridge_pack.py \
  --source-bundle runs/demo/dimos-bridge-source \
  --out-dir runs/dimos/bridge-pack \
  --dimos-checkout /path/to/local/dimos
```

The `--dimos-checkout` value is optional and must be adjusted to a local DimOS
source checkout when available.

Show `runs/dimos/bridge-pack/manifest.json` and
`runs/dimos/bridge-pack/timeline.ndjson`, then say:

```text
This is a DimOS-ready replay export from verified DecisionTrace files. It does
not prove DimOS executed the swarm yet.
```

## Server Replay Routes

After `python3 scripts/serve_demo.py --host 127.0.0.1 --port 8000`, use these
for the local recording:

```text
http://127.0.0.1:8000/swarm-demo
http://127.0.0.1:8000/hazard-formation
```

## Optional Live Qwen Insert

Only include this if the operator has already run the live command and checked
the report:

```bash
set -a; . ./.env; set +a
python3 scripts/qwen_model_ping.py --models qwen-plus
python3 scripts/make_hazard_fixture.py runs/go_gate/hazard_marker.png
python3 -m scripts.run_hazard_formation_gate \
  --image runs/go_gate/hazard_marker.png \
  --mode dashscope \
  --model qwen3-vl-flash \
  --formation x \
  --trace-dir runs/hazard_formation/live_dashscope_x \
  --report-out runs/hazard_formation/live_dashscope_x_report.json
```

Do not show `.env`, API keys, shell history containing keys, or provider
credentials on camera.

## Lines To Avoid

- "DimOS-backed swarm"
- "physical swarm"
- "SO-101 is operating"
- "3D physics"
- "Qwen controls the robots"
- "deployed on Alibaba ECS"
- "safe" or "reliable" without a separately checked evidence artifact

## Honest One-Line Captions

Fixture-only recording:

```text
A Qwen-style keyframe bbox becomes a local hazard cell; deterministic agents
form an X around it, and every decision is replayable from hash-chained traces.
```

Live-Qwen insert recording:

```text
Qwen flags a hazard from a keyframe; local deterministic agents form an X
around it, and every decision is replayable from hash-chained traces.
```
