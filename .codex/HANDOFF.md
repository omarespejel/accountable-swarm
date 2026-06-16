# Accountable Swarm Handoff

Last updated: 2026-06-15 JST

## Active Thesis

Accountable Swarm is a hackathon robotics lab for Qwen Cloud EdgeAgent. The
demo spine keeps real-time action local and deterministic while using Qwen Cloud
for low-rate keyframe perception or mission reasoning. Any demo decision that
matters must be reproducible as a hash-chained `DecisionTrace`.

## Current Evidence State

Status: `GO` for live Qwen API/model availability and single-keyframe
DecisionTrace; `NARROW_CLAIM` for the broader robotics demo.

What is checked locally:

- fixture-mode image-to-decision GO gate;
- fixture-mode GO-gate now runs hazard and clear frames end-to-end inside
  `scripts/local_gate.sh`; hazard emits `VETO`, clear emits `MOVE`, and both
  traces verify through `scripts/verify_trace.py`.
- Qwen-style `bbox_2d` parsing and normalized coordinate validation;
- deterministic `DecisionTrace` serialization and replay;
- physical-node trace-only safety contract;
- no-key DashScope failure path.
- DashScope bbox calls pin `temperature: 0`, and malformed bbox text is retried
  once before failing with a controlled validation error.
- the GO-gate optional-grounding wrapper maps extracted empty arrays, including
  `[ ]` and prose-wrapped `[]`, to clear frames; the strict bbox parser still
  rejects empty arrays.
- live `qwen3-vl-flash` DashScope trace from generated PNG fixture;
- minimal `qwen-plus` and `qwen3.5-plus` Commander/text pings.
- trace canonical JSON rejects raw floats; future measurements must use integer
  units or decimal strings.
- package metadata now exposes installable `run-go-gate`,
  `run-camera-go-gate`, and `verify-trace` commands with zero runtime
  third-party dependencies. The local gate validates those installed entry
  points in a temporary virtual environment, and the GO-gate command paths no
  longer depend on script-local `sys.path.insert(...)` mutation or
  `PYTHONPATH` injection.
- `DecisionEvent.command` explicitly rejects raw floats before command hashing;
  command measurements must use declared integer units or decimal strings.
- Qwen bbox confidence-like fields are quantized into integer `score_milli`
  before entering `PerceptionEvent`, and `PerceptionEvent` rejects raw float,
  boolean, or out-of-range scores before hashing.
- `DecisionTrace` schema is now `decisiontrace.v2`; v1 traces are rejected
  instead of being rehashed with an injected confidence field.
- tiny positive-area normalized bboxes now clamp to a positive-area pixel bbox
  inside the image instead of collapsing into zero-area detections on small
  frames.
- camera/static-frame GO gate passes live `qwen3-vl-flash` with all five binary
  pass conditions and summary
  `214d4edb89537ecf6c8060b2e4fcd6053497aa20439b65cca8641ef8d0e011c8`.
- true webcam sensor-frame gate passed locally with live `qwen3-vl-flash` and
  summary `b643935f5ea0d326ac468c60cbac4ca46e61bab67584fd8840766a6a2601be9f`;
  the captured frame and trace are intentionally untracked. This is not
  SO-101 operation or physical motion evidence.
- minimal stdlib HTTP server and Dockerfile exist for manual Alibaba ECS proof;
  operator still needs to provision ECS and run the smoke checks.
- ECS operator proof pack generator prepares a non-secret runbook, command
  script, `.env.template` with blank secret fields/defaults, and manifest for
  the operator-run Alibaba ECS proof session; this is not itself deployment
  proof.
- DimOS bridge pack generator consumes a verified swarm demo bundle, verifies
  every referenced agent `DecisionTrace`, exports an integer-only timeline
  NDJSON with event hashes, and records DimOS source/runtime availability as a
  separate probe. This is a DimOS-ready replay artifact, not DimOS execution or
  integration proof.
- DimOS replay consumer validates the bridge-pack manifest and timeline, rejects
  non-canonical, float-containing, path-escaped, or out-of-order replay input,
  groups verified events into DimOS-shaped stream summaries, and records DimOS
  source/runtime availability separately. This is a replay stream-contract
  proof, not DimOS execution, Rerun recording, or swarm-control proof.
- `WorldModelState` now exists as the explicit accountable world-model data
  contract for issue #75. It records observations, hazards, agents,
  reservations, predicted conflicts, and a deterministic `world_model_sha` while
  rejecting raw floats and booleans in hashed payloads. This is a data-contract
  proof only; it is not yet wired into the hazard-formation gate or dashboard.
- The hazard-formation gate now emits `world_model_timeline.jsonl` and a
  `world_model` report section with first/last `world_model_sha`, state count,
  replay determinism, and predicted conflict count. Fixture and degraded modes
  both emit world-model evidence; dashboard rendering and conflict heatmaps
  remain follow-up work under #75.
- deterministic N=2 integer-grid simulated swarm emits one DecisionTrace per
  agent, reaches goals, and reports zero same-cell or swap collisions.
- deterministic N=2 center-block obstacle scenario reaches goals, reports zero
  obstacle occupancy, and replay recomputes obstacle occupancy from traces.
- deterministic N=4 center-block obstacle scenario reaches goals with the
  bounded reservation planner, reports zero same-cell collisions, zero swap
  collisions, zero obstacle occupancy, and replay recomputes those counts from
  traces.
- deterministic N=4 vertical-slalom obstacle scenario reaches goals with the
  bounded reservation planner, reports zero same-cell collisions, zero swap
  collisions, zero obstacle occupancy, and replay recomputes those counts from
  traces.
- deterministic N=4 horizontal-slalom obstacle scenario reaches goals with the
  bounded reservation planner, reports zero same-cell collisions, zero swap
  collisions, zero obstacle occupancy, and replay recomputes those counts from
  traces.
- deterministic N=4 double-chicane obstacle scenario reaches goals at its
  reviewed 17-tick budget with the bounded reservation planner, reports zero
  same-cell collisions, zero swap collisions, zero obstacle occupancy, and
  replay recomputes those counts from traces. The same scenario at 16 ticks
  remains `NARROW_CLAIM`.
- larger simulated swarm counts are intentionally outside the current reviewed
  surface; N=5/N=6 are not success claims, and `--agents 5` is rejected before
  trace or report artifacts are written.
- low-rate fixture mission assignment validates strict mission JSON, emits a
  mission `DecisionTrace`, then runs deterministic N=4 center-block and
  horizontal-slalom swarm gates with trace-replayed zero same-cell, swap, and
  obstacle occupancy counts.
- mission objective text hardening rejects hidden counts, selected scenario
  names, coordinates, arrays, and control terms inside the otherwise
  single-key `objective` string.
- live `qwen-plus` DashScope mission assignment validates an intent-only
  objective for the reviewed `center-block` scenario, emits a mission
  `DecisionTrace`, then runs the deterministic N=4 center-block swarm gate with
  trace-replayed zero same-cell, swap, and obstacle occupancy counts.
- prior live `qwen-plus` DashScope mission suite validates intent-only
  objectives for the then-reviewed four scenario-registry names, emits mission
  `DecisionTrace` artifacts, then verifies persisted mission and agent traces
  from disk with trace-replayed zero same-cell, swap, and obstacle occupancy
  counts.
- post-hardening live `qwen-plus` DashScope mission suite validates intent-only
  objectives for all five current reviewed scenario-registry names, including
  `double-chicane`, emits mission `DecisionTrace` artifacts, then verifies
  persisted mission and agent traces from disk with trace-replayed zero
  same-cell, swap, and obstacle occupancy counts.
- mission scenario selection is bounded to reviewed simulator scenario-registry
  names; this is not an arbitrary-map interface.
- fixture swarm mission suite runs the mission binding path for every reviewed
  scenario-registry name, verifies persisted mission and agent traces from disk,
  and keeps same-cell, swap, and obstacle occupancy counts at zero in each
  trace-derived replay.
- swarm mission-suite trace verifier reports `GO` for clean persisted mission
  and agent traces, and reports `NARROW_CLAIM` when a copied agent trace is
  mutated without recomputing hashes.
- deterministic swarm scenario suite reruns seven N=2/N=4 scoped cases,
  includes an expected `NARROW_CLAIM` canary, and verifies persisted agent
  traces from disk.
- fixed swarm scenario registry centralizes current scenario names, obstacle
  policies, fixed-grid requirements, and reservation-planner use.
- deterministic swarm trace visualization emits a static HTML/SVG replay and
  canonical summary from verified persisted traces; the checked N=4
  center-block artifact has HTML SHA
  `686a328376478bc1bf76b9c59b7ed283f6889d5d48003fdc8928f9f80a231f60`.
- one-command deterministic swarm demo bundle generates reports, verified
  traces, static replays, and a deterministic index for every reviewed scenario
  registry name; checked index SHA is
  `b929f77827e69b9100e9883f78e7b882e7b161d67350a31a129d452f99c63368`.
- demo recording pack generator builds the deterministic swarm bundle, runs the
  fixture hazard-to-X formation gate, renders the hazard formation replay, and
  emits a judge-facing manifest plus shotlist with fixture/live-Qwen boundaries
  separated.
- dashboard data-pack generator verifies a hazard formation report, hazard
  trace, per-agent traces, and the persisted world-model timeline into a single
  renderer-ready `world-model-dashboard-data.v1` JSON artifact, and rejects
  rehashed world-model drift against source DecisionTrace commands.
- read-only stdlib server endpoints serve existing swarm bundle artifacts at
  `/swarm-demo` and `/swarm-demo/summary.json` with path traversal rejection.
- read-only stdlib server endpoints serve the generated hazard formation replay
  at `/hazard-formation` and `/hazard-formation/summary.json` with path
  traversal rejection.
- exploratory deterministic N=4 integer-grid probe passes locally, but is not a
  physical, physics, latency, reliability, or larger-swarm claim.
- local-guard-only deterministic N=4 center-block obstacle probe remains useful
  as the prior `NARROW_CLAIM`: it avoids collisions and obstacle occupancy but
  does not reach all goals without the bounded planner.

What is not checked yet:

- Alibaba Cloud deployment proof from an actual ECS instance;
- SO-101 physical frame source;
- DimOS runtime execution or Rerun visualization; current work exports and
  consumes a deterministic replay stream contract only;
- physics-backed multi-agent swarm behavior;
- latency, reliability, or safety claims.
- live Qwen mission assignment beyond the scoped `qwen-plus` five-scenario
  suite evidence.
- interactive world-model dashboard renderer; current work prepares the
  verified data substrate only.

## Active GitHub Work

- Issue #75: Qwen-grounded world-model dashboard for accountable swarm.
- Issue #3: physical-node safety contract and true sensor-frame proof. This is
  parked during the dashboard sprint, not closed.
- Issue #1 and #73 are closed or superseded by the current dashboard plan.
- Issue #2, #6, #11, #13, #15, #17, #19, #21, #23, #25, #27, #29, #33,
  #35, #37, #39, #41, #43, #45, #48, #50, #52, #54, #59, and #68 are closed
  as GO or scoped NARROW_CLAIM where documented.
- PR #5, #7, #8, #9, #10, #12, #14, #16, #18, #20, #22, #24, #34, #36, and
  #38, #40, #42, #44, #46, #47, #49, #51, #66, #70, and #72 are merged.

Before creating new work, inspect the current PR and issues:

```bash
gh pr list --state open
gh issue list --state open
```

## Next Agent Rules

- Start from the read order in `.codex/START_HERE.md`.
- Keep work issue-scoped and outcome-scoped: `GO`, `NO_GO`,
  `NARROW_CLAIM`, `FOLLOWUP_ISSUE`, or `KILL`.
- Add exact commands to PR bodies and evidence docs.
- Record any copied code, generated assets, model usage, or external services in
  `DISCLOSURE_LEDGER.md`.
- Do not merge while Qodo, CodeRabbit, or human review feedback is actionable.
- Wait five minutes after the latest relevant reviewer activity before merge.
