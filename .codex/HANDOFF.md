# Accountable Swarm Handoff

Last updated: 2026-06-28 JST

## Active Thesis

Accountable Swarm is a hackathon robotics lab for Qwen Cloud EdgeAgent. The
demo spine keeps real-time action local and deterministic while using Qwen Cloud
for low-rate keyframe perception or mission reasoning. Any demo decision that
matters must be reproducible as a hash-chained `DecisionTrace`.

## Current Evidence State

Status: `GO` for live Qwen API/model availability and single-keyframe
DecisionTrace; `NARROW_CLAIM` for the broader robotics demo.

QwenGuard update: `GO` for the no-hardware SO-101 software spine on branch
`codex/qwenguard-so101-spine-2026-06-28`. Issue #95 is the current physical
QwenGuard umbrella. The branch is based on `origin/main`, not the dashboard PR
stack. It adds Set-of-Mark selector validation, before/after evaluator
validation, a deterministic local outcome gate, a no-motion health-check CLI,
a non-secret SO-101 ACT training pack, and trial/eval schema. This is not
SO-101 operation or physical motion evidence.

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
- sensor-frame proof pack now turns the camera/webcam path into a reproducible
  manifest artifact with source-frame SHA, trace/report binding, and
  delete-after-hash default for captured webcam frames. This is still not
  SO-101 operation or physical motion evidence.
- SO-101 trace-only camera probe surface now exists and emits a controlled
  `NO_GO` report when optional `lerobot` / `opencv` dependencies are absent.
  This is an adapter/probe boundary only, not SO-101 camera success.
- SO-101 operator probe pack now exists to generate a non-secret runbook and
  command script for the actual hardware machine using the official LeRobot
  install and OpenCV camera flow. This is setup guidance, not hardware success.
- QwenGuard no-motion health check now validates a relational cube selector,
  local outcome gate, evaluator, and multi-event `decisiontrace.v2` without
  moving hardware. Fixture mode produced summary
  `5161920e949b369b73aae52557cccede17a05dda80e90c1d9da0fc52d282a38c` with
  `gate_decision=ALLOW` intent and `motion_executed=false`. Degraded mode
  produced summary
  `6d7be5d5246f10aafd1af79ee0c7df398fe8aa57bb6e9832073e31621e791042` with
  `gate_decision=HOLD`.
- QwenGuard post-review hardening keeps local candidate labels canonical,
  requires exactly two distinct references for `between`, validates JSON-mode
  `max_tokens`, derives no-motion status from replayed trace events, prevents
  blocked fixture-mode gates from reporting `GO`, shell-quotes operator-pack
  task text, pins the generated LeRobot/OpenCV install commands, and adds
  malformed-input regressions for Qwen JSON responses, evaluator payloads,
  trial enums, blocked fixture gates, and shell-unsafe task values.
- QwenGuard selector/evaluator/gate/trial targeted tests pass locally. The
  checked command was:
  `python3 -m unittest tests.test_qwenguard_selector tests.test_qwenguard_evaluator tests.test_qwenguard_outcome_gate tests.test_qwenguard_traces tests.test_qwenguard_health_check_cli tests.test_so101_training_pack_cli tests.test_qwenguard_trial tests.test_qwen_client tests.test_trace`.
- Full local gate passed on the post-review branch with:
  `./scripts/local_gate.sh` -> `Ran 294 tests in 196.221s`, `local gate passed`.
- QwenGuard SO-101 training pack generator now emits a no-secret runbook,
  operator command script, and trial CSV template. This is preparation for
  tomorrow's hardware session, not SO-101 connectivity or ACT success.
- QwenGuard physical GO pack generator now consolidates the SO-101 camera
  probe, fixture/degraded no-motion traces, ACT training-pack generation, trial
  template, evidence template, and demo shotlist into one non-secret
  phase-driven operator bundle. Its generated `all-safe` phase runs without
  hardware and verifies fixture/degraded `decisiontrace.v2` traces. This is
  still preparation, not SO-101 connectivity, camera success, ACT success, or
  physical motion evidence.
- minimal stdlib HTTP server and Dockerfile exist for manual Alibaba ECS proof;
  operator still needs to provision ECS and run the smoke checks.
- ECS operator proof pack generator prepares a non-secret runbook, command
  script, `.env.template` with blank secret fields/defaults, and manifest for
  the operator-run Alibaba ECS proof session; this is not itself deployment
  proof. The #91 proof collector now distinguishes localhost diagnostics from
  `ecs-public` proof: `GO` requires public endpoint mode, ECS region, instance
  ID, global public IP, and matching public endpoint evidence. Localhost smoke
  is intentionally `NARROW_CLAIM`.
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
  fixture hazard-to-X formation gate, renders the hazard formation replay,
  builds the verified world-model dashboard, and emits a judge-facing manifest
  plus shotlist with fixture/live-Qwen boundaries separated.
- dashboard data-pack generator verifies a hazard formation report, hazard
  trace, per-agent traces, and the persisted world-model timeline into a single
  renderer-ready `world-model-dashboard-data.v1` JSON artifact, and rejects
  rehashed world-model drift against source DecisionTrace commands.
- interactive world-model dashboard renderer consumes the verified
  `world-model-dashboard-data.v1` artifact and emits a self-contained HTML
  replay plus `world-model-dashboard-html-report.v1`. The renderer validates
  non-empty timelines, world-model hashes, event-hash binding, relative paths,
  no raw floats, no secret-looking payloads, and explicit non-claims before
  writing the page.
- the dashboard pack can now optionally copy a reviewed source frame into the
  output, carry a validated `dimos-bridge-pack-report.v1` summary, and expose
  both through the rendered dashboard without claiming DimOS execution.
- the world-model dashboard now shows a Qwen source-frame pane with bbox
  overlay, a per-agent `DecisionTrace Inspector`, and a DimOS-ready export
  status panel in the same verified HTML artifact.
- the world-model dashboard can now call a local-only `/replan` endpoint that
  re-enters the reviewed reservation planner from current agent cells plus a
  bounded formation enum. The interactive HTML surface supports click-to-toggle
  obstacle placement, formation switches, deterministic planner rejection, and
  redraws from returned world-model timeline rows. This is local interactive
  replay only, not public deployment proof, physics, hardware, or live-Qwen
  motion control.
- the hazard-formation gate can now emit a separate bounded mission-choice
  `DecisionTrace` using a strict local allow-list:
  `{"mission":"surround_hazard|hold_position","risk":"cautious|balanced"}`.
  The validator is local, not API-enforced. The persisted `mission.json` trace
  is threaded into the hazard report, dashboard data pack, and rendered
  dashboard when `--mission-source fixture|dashscope|auto` is enabled.
- the recording pack now prefers live DashScope for both the hazard bbox and
  bounded mission path when `ALIBABA_API_KEY` is present, and otherwise falls
  back to fixture mode without changing the local deterministic replay surface.
- read-only stdlib server endpoints serve existing swarm bundle artifacts at
  `/swarm-demo` and `/swarm-demo/summary.json` with path traversal rejection.
- read-only stdlib server endpoints serve the generated hazard formation replay
  at `/hazard-formation` and `/hazard-formation/summary.json` with path
  traversal rejection.
- read-only stdlib server endpoints serve the generated world-model dashboard at
  `/world-model-dashboard` and `/world-model-dashboard/summary.json` with path
  traversal rejection.
- exploratory deterministic N=4 integer-grid probe passes locally, but is not a
  physical, physics, latency, reliability, or larger-swarm claim.
- local-guard-only deterministic N=4 center-block obstacle probe remains useful
  as the prior `NARROW_CLAIM`: it avoids collisions and obstacle occupancy but
  does not reach all goals without the bounded planner.

What is not checked yet:

- Alibaba Cloud deployment proof from an actual ECS instance;
- SO-101 physical frame source;
- ACT policy training or physical rollout;
- live Qwen selector/evaluator on SO-101 frames;
- DimOS runtime execution or Rerun visualization; current work exports and
  consumes a deterministic replay stream contract only;
- physics-backed multi-agent swarm behavior;
- latency, reliability, or safety claims.
- live Qwen mission assignment beyond the scoped `qwen-plus` five-scenario
  suite evidence.
- public recording based on the interactive world-model dashboard renderer.

## Active GitHub Work

- Issue #95: QwenGuard SO-101 physical edge-cloud manipulation demo. This is
  the current umbrella for selector, evaluator, outcome gate, ACT training,
  physical GO gates, trace evidence, and claim boundaries.
- PR #92: bounded Qwen mission-choice dashboard flow and Node 24 workflow-pin
  update on `codex/bounded-qwen-demo-2026-06-17`. It must keep Qwen as a
  bounded mission proposer only, derive dashboard mission state from verified
  traces, and validate mission/risk enums locally before rendering.
- Issue #93 / PR #94: interactive dashboard, stacked on PR #92. Useful for
  visualization, but not on the QwenGuard critical path.
- Issue #91: operator-run Alibaba ECS proof from a public endpoint. This remains
  the submission blocker to move in parallel with SO-101 work.
- Issues #87 and #90 are resolved by the bounded mission-choice/dashboard pack
  once PR #92 lands.
- Issues #3, #75, and #88 are closed; #3 remains historical context only.
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
