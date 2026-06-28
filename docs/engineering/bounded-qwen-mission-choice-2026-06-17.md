# Bounded Qwen Mission Choice 2026-06-17

Issue: #90

## Why

The world-model dashboard already made Qwen keyframe evidence visible, but the
only cloud-visible artifact in frame was the bbox. For the judge-facing demo we
needed a second bounded cloud surface that stays outside motion control:

- Qwen hazard bbox evidence
- Qwen mission-choice JSON
- local deterministic planning and motion
- hash-verifiable traces and replay

## What changed

- Added `accountable_swarm.swarm.mission_choice` with a strict
  `formation-mission.v1` schema.
- Added a bounded JSON prompt for `qwen3-vl-flash`:
  `{"mission":"surround_hazard|hold_position","risk":"cautious|balanced"}`.
- Added local validation and a persisted `mission.json` `DecisionTrace`.
- Threaded the validated mission choice into:
  - `hazard-formation-gate-report.v1`
  - `world-model-dashboard-data.v1`
  - the rendered HTML dashboard
- Updated the recording pack so it prefers live DashScope when
  `ALIBABA_API_KEY` is present, while preserving fixture fallback.

## Validation

```bash
python3 -m unittest \
  tests.test_formation_mission_choice \
  tests.test_hazard_formation_gate_cli \
  tests.test_world_model_dashboard_pack_cli \
  tests.test_world_model_dashboard_renderer_cli \
  tests.test_demo_recording_pack_cli
./scripts/local_gate.sh
```

## Claim boundary

The Qwen mission choice is not API-enforced beyond `json_object`. The allow-list
is enforced locally by our validator before any local plan executes.

## CI Pinning Note

`.github/workflows/local-gate.yml` pins `actions/checkout` and
`actions/setup-python` by full commit SHA. This is intentional supply-chain
hardening for the research gate. Update those pins only in a focused maintenance
PR that records the replacement SHAs and reruns `./scripts/local_gate.sh`.

## Non-claims

- no Qwen real-time control
- no API-enforced enum guarantee
- no 3D or hardware claim
- no DimOS execution claim
