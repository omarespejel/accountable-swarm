# Live DashScope Hazard Formation Gate 2026-06-16

Issue: #59

## Thesis

Live Qwen vision can be load-bearing in the recorded swarm demo without putting
Qwen in the real-time motion loop. A single image keyframe is sent to DashScope,
the returned 2D bbox is validated and quantized into a local integer hazard
cell, and the deterministic local planner assigns a four-agent formation around
that cell.

## Why It Matters

This closes the weakest part of the sim-only story: the swarm replay is now
connected to a live Qwen visual perception event, while preserving the
accountability boundary.

The boundary is still:

```text
Qwen perceives a keyframe hazard.
Local deterministic code validates and quantizes the bbox.
Local deterministic code compiles the formation and owns every move.
DecisionTrace artifacts make the result replay-verifiable.
```

## Commands

The API key was loaded from the local untracked `.env` file. The key was not
printed, logged, committed, or written into any artifact.

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
python3 -m scripts.verify_trace runs/hazard_formation/live_dashscope_x/hazard.json
python3 -m scripts.verify_trace runs/hazard_formation/live_dashscope_x/agents/sim-agent-0.json
python3 -m scripts.verify_trace runs/hazard_formation/live_dashscope_x/agents/sim-agent-1.json
python3 -m scripts.verify_trace runs/hazard_formation/live_dashscope_x/agents/sim-agent-2.json
python3 -m scripts.verify_trace runs/hazard_formation/live_dashscope_x/agents/sim-agent-3.json
```

## Observed Output

```text
qwen-plus: OK
wrote runs/go_gate/hazard_marker.png
outcome GO
mode dashscope
formation x
trace_dir runs/hazard_formation/live_dashscope_x
wrote runs/hazard_formation/live_dashscope_x_report.json
verified runs/hazard_formation/live_dashscope_x/hazard.json
summary_sha b4f6b341aeb470afebcf79f245c8521e8bf06e42f58c3fa071af245f8aefd53d
```

Agent trace verification:

```text
sim-agent-0 cff7a9164c1ede4cba8f168338b6280393685990d5dcd7f58e8d4537dea757c3
sim-agent-1 98eb01a518b1ba53302a1f9cfe7a0d25922482c7a6d5bf646f7de1fd541d132b
sim-agent-2 9717f9f5e377ce12bd8d913c3795f12eafdd4ae6a0b064d5fd65ff590b8d421d
sim-agent-3 bb67df480a4648d0ee752803546f037b4ff52b2c2876cd8a2902109793938ad6
```

## Result

```json
{
  "outcome": "GO",
  "mode": "dashscope",
  "model": "qwen3-vl-flash",
  "image": {"name": "hazard_marker.png", "width": 64, "height": 64},
  "hazard": {
    "bbox_2d_norm_1000": [241, 238, 756, 759],
    "bbox_2d_px": [15, 15, 48, 49],
    "cell": {"x": 3, "y": 2},
    "source_label": "hazard"
  },
  "formation": "x",
  "assigned_goals": {
    "sim-agent-0": {"x": 2, "y": 1},
    "sim-agent-1": {"x": 4, "y": 3},
    "sim-agent-2": {"x": 4, "y": 1},
    "sim-agent-3": {"x": 2, "y": 3}
  },
  "sim_report": {
    "outcome": "GO",
    "agent_count": 4,
    "same_cell_collision_count": 0,
    "swap_collision_count": 0,
    "obstacle_occupancy_violation_count": 0,
    "hold_count": 22,
    "reroute_count": 2
  }
}
```

Pass conditions were all true:

```text
hazard_perception_available
hazard_cell_quantized
formation_compiled
hazard_trace_replay_deterministic
agent_traces_replay_deterministic
formation_run_go
trace_replay_clean
```

## GO Gate

GO for a live DashScope keyframe perception to deterministic formation-planner
bridge.

The claim is bounded to this specific generated PNG fixture, model
`qwen3-vl-flash`, local integer grid, four agents, `x` formation, and the
recorded trace hashes above.

## Non-Claims

- No physical robot behavior.
- No SO-101 operation.
- No physical swarm claim.
- No 3D physics simulation.
- No DimOS integration.
- No arbitrary-map planner claim.
- No safety claim.
- No latency or reliability claim.
- No Qwen real-time control.
- No Alibaba ECS deployment proof.

