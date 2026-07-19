# Accountable Swarm Submission Manifest

## Track 5 Position

QwenGuard is an EdgeAgent evidence loop for ambiguous physical-world changes:

> **Memory with receipts: teleoperated capture, post-run replay, and fail-closed cloud checks.**

```text
edge evidence -> Qwen Cloud semantic result -> strict local validation ->
local HOLD / REVERIFY policy -> hash-chained DecisionTrace -> replay
```

Qwen is deliberately outside the motor loop. The physical capture was
teleoperated, and the checked public replay is a post-run policy simulation.
The deterministic swarm remains a secondary, no-hardware illustration of the
same trace architecture.

## Submission Checklist

The official [rules](https://qwencloud-hackathon.devpost.com/rules),
[deployment-proof update](https://qwencloud-hackathon.devpost.com/updates/45055-proof-of-deployment-101-what-judges-need-to-see),
and [final checklist](https://qwencloud-hackathon.devpost.com/updates/45369-this-is-it-your-last-weekend-to-build)
require a public licensed repository, visible Qwen Cloud API code, an
architecture diagram, Alibaba Cloud visual proof, a public demo under three
minutes, a project description, and a track selection.

The current submission deadline is July 20, 2026 at 2:00 PM Pacific.

| Requirement | Repository state |
| --- | --- |
| Public source and Apache-2.0 license | Present |
| Qwen Cloud base URL and API call | Present; links below |
| Architecture diagram | Present in `docs/submission/architecture.md` |
| Reproducible local judge path | Present; commands below |
| Alibaba Cloud deployment proof | Final sanitized report, Workbench screenshot, and human review not yet claimed complete |
| Public demo video | Must be under 3:00 on YouTube, Vimeo, or Youku; publication and final privacy/claim review remain pending |
| Judge access | Public links must remain free and playable without login through judging; logged-out test remains pending |
| Devpost metadata | Name Qwen Cloud in the description and Built With section before submission |
| Track | Track 5: EdgeAgent |

## Qwen Cloud Code Proof

The exact reviewed source at commit
`a62c78ff8c1c82e73686afb18fcb52cf64c77a1b` is:

- [Qwen client, public DashScope base URL, and Qwen3-VL payload](https://github.com/omarespejel/accountable-swarm/blob/a62c78ff8c1c82e73686afb18fcb52cf64c77a1b/accountable_swarm/qwen/client.py#L15-L68)
- [authenticated OpenAI-compatible API request](https://github.com/omarespejel/accountable-swarm/blob/a62c78ff8c1c82e73686afb18fcb52cf64c77a1b/accountable_swarm/qwen/client.py#L103-L124)
- [same file in this checkout](../../accountable_swarm/qwen/client.py)

The default is
`https://dashscope-intl.aliyuncs.com/compatible-mode/v1`. A regional
`DASHSCOPE_BASE_URL` override must still be HTTPS and cannot contain embedded
credentials, a query, or a fragment. `ALIBABA_API_KEY` is read from the
environment and must never be committed.

## Judge Reproduction

From a clean clone, run the privacy-safe replay without provider credentials:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e .
run-qwenguard-memory-replay
verify-qwenguard-memory-replay
```

The verifier independently rebuilds the public fixture and enforces this exact
post-run sequence:

```text
VERIFIED -> PROVISIONAL -> HOLD -> REVERIFY
```

It also rejects skipped phases, added motor authority, changed receipts, and a
trace whose hash chain or report no longer matches.

To inspect the same replay through the local backend, start the server in one
terminal:

```bash
python3 scripts/serve_demo.py --host 127.0.0.1 --port 8000
```

Then query it from a second terminal:

```bash
curl -fsS http://127.0.0.1:8000/healthz
curl -fsS http://127.0.0.1:8000/qwenguard-memory-fixture
```

To make a live Qwen Cloud call, use a private key in the environment and the
same checked-in, non-private PNG fixture used by the ECS proof endpoint:

```bash
# Load ALIBABA_API_KEY from a secret manager; do not paste it into this file.
run-camera-go-gate \
  --image fixtures/hazard_marker.png \
  --mode dashscope \
  --trace-out runs/go_gate/qwen_trace.json \
  --report-out runs/go_gate/qwen_report.json
verify-trace runs/go_gate/qwen_trace.json
```

The live result proves only the bounded API/parser/trace path for the named
model and fixture. It does not prove perception accuracy, robot autonomy,
latency, or reliability.

## Physical Evidence Boundary

- The Go2 Air was driven by a human operator. Qwen did not steer it.
- The replay phases are post-run policy states, not robot-runtime transitions.
- Public receipts contain hashes and redacted metadata, not hotel imagery or
  raw capture databases.
- The semantic frames came from a fixed independent Gemini 2 RGB-D camera. Its
  displayed depth preview is qualitative and independently normalized, not a
  metric depth comparison. It was not mounted on the Go2, and the devices were
  not frame-synchronized.
- Go2 receipts cover the recorded onboard-SLAM point cloud and odometry
  context; they are not a claim of raw L1 LiDAR capture.
- Memory2 values `500` and `750` are internal belief confidence, not Qwen
  detection confidence.
- Stored model box integers are model-coordinate receipts, not calibrated
  pixels, metric displacement, or validated 3D grounding.
- `HOLD` has no motor authority. `REVERIFY` asks for another observation; it
  does not certify that the object moved.

## Significant Updates Since May 26, 2026

The repository history begins on June 14, so all substantive implementation is
post-May 26:

- **June 14-17:** added the Qwen Cloud client, strict bbox/mission validation,
  hash-chained `DecisionTrace`, deterministic replay, degraded HOLD paths,
  bounded local swarm scenarios, a world-model dashboard, and Alibaba ECS proof
  tooling.
- **June 28-29:** added the QwenGuard selector/evaluator/gate contracts,
  fail-closed evidence manifests, trial attestation, and final readiness audits.
- **July 18-19:** added the privacy-safe Go2 memory replay, semantic replay
  verification, network-path leak rejection, a deterministic PNG live-Qwen
  fixture, and hardened ECS smoke endpoints.

## Secondary Local Demo

The deterministic four-agent integer-grid bundle is useful for inspecting the
same replay discipline without hardware or a provider key:

```bash
python3 scripts/build_swarm_demo_bundle.py
```

Expected high-level output:

```text
outcome GO
scenario_count 5
wrote runs/demo/swarm/index.html
wrote runs/demo/swarm/summary.json
```

Open `runs/demo/swarm/index.html`, or run the local server above and inspect
`/swarm-demo` and `/swarm-demo/summary.json`. This is a deterministic
integer-grid simulation, not physics-backed swarm or physical-robot evidence.

## Checked Local Evidence

Primary deterministic swarm evidence:

- `docs/engineering/swarm-demo-bundle-2026-06-15.md`
- `docs/engineering/swarm-suite-2026-06-15.md`
- `docs/engineering/swarm-scenario-registry-2026-06-15.md`
- `docs/engineering/swarm-trace-visualization-2026-06-15.md`
- `docs/engineering/dimos-bridge-probe-2026-06-16.md` (optional bridge
  export only; no DimOS execution claim)
- `docs/engineering/current-status-2026-06-15.md`

The reviewed scenario registry is:

- `corridor`
- `center-block`
- `vertical-slalom`
- `horizontal-slalom`
- `double-chicane`

The current bundle claim is limited to four agents on deterministic integer
grids, with zero same-cell, swap, and obstacle-occupancy violations in the
trace-derived replay for the listed scenarios. Each scenario replay page now
contains a recordable animated panel plus static per-tick SVG frames generated
from the same verified persisted traces.

Primary hazard-to-formation evidence:

- `docs/engineering/hazard-formation-gate-2026-06-16.md`
- `docs/engineering/hazard-formation-replay-pack-2026-06-16.md`
- `docs/engineering/world-model-state-2026-06-16.md`
- `docs/engineering/world-model-hazard-binding-2026-06-16.md`
- `docs/engineering/world-model-dashboard-pack-2026-06-16.md`
- `docs/engineering/world-model-dashboard-renderer-2026-06-16.md`
- `docs/engineering/live-dashscope-hazard-formation-2026-06-16.md`

Replay the fixture hazard-to-X gate:

```bash
python3 -m scripts.run_hazard_formation_gate \
  --image fixtures/hazard_marker.ppm \
  --mode fixture \
  --formation x \
  --trace-dir runs/hazard_formation/smoke_x \
  --report-out runs/hazard_formation/smoke_x_report.json
```

This checked path maps a Qwen-style 2D bbox to an integer-grid hazard cell,
assigns four agents to formation slots, and verifies persisted hazard and agent
traces from disk. It is not 3D grounding, physical behavior, or Qwen real-time
control.

The recording pack also renders the generated agent traces into
`runs/hazard_formation/recording_x_replay/index.html`, with the hazard cell
shown as the obstacle. This makes the perception-to-formation path visible
without changing the claim boundary.

When `ALIBABA_API_KEY` is available, the live hazard-to-formation proof uses
`qwen3-vl-flash` on a generated PNG keyframe and the same model for the bounded
mission JSON. The checked 2026-06-16 run returned `outcome GO`, bbox
`[241,238,756,759]`, hazard cell `{"x":3,"y":2}`, and replay-verified hazard
plus four agent traces. The mission JSON is locally validated against the
allow-list before planning. This remains keyframe perception and low-rate
mission reasoning feeding deterministic local planning, not live Qwen control.

## Checked Live-Qwen Evidence

Primary live Qwen mission evidence:

- `docs/engineering/live-dashscope-swarm-mission-suite-post-hardening-2026-06-15.md`
- `docs/engineering/live-dashscope-hazard-formation-2026-06-16.md`
- `docs/engineering/swarm-mission-objective-hardening-2026-06-15.md`
- `docs/engineering/swarm-mission-suite-tamper-2026-06-15.md`

Replay the fixture mission suite without API credentials:

```bash
python3 scripts/run_swarm_mission_suite.py \
  --trace-root runs/swarm/mission-suite \
  --report-out runs/swarm/mission_suite_report.json
python3 scripts/verify_swarm_mission_suite.py \
  --trace-root runs/swarm/mission-suite \
  --report runs/swarm/mission_suite_report.json \
  --report-out runs/swarm/mission_suite_verify_report.json
```

Replay live DashScope evidence only when `ALIBABA_API_KEY` is available. Obtain
the key from the operator's Alibaba Cloud DashScope console, then either export
it in the shell or place it in a local untracked `.env` file as
`ALIBABA_API_KEY=...`.

If using `.env`, load it before running the live commands:

```bash
set -a; . ./.env; set +a
```

Then run:

```bash
python3 scripts/qwen_model_ping.py --models qwen-plus
python3 scripts/run_swarm_mission_suite.py \
  --mode dashscope \
  --model qwen-plus \
  --trace-root runs/swarm/live-mission-suite-after-objective-hardening \
  --report-out runs/swarm/live_mission_suite_after_objective_hardening_report.json
python3 scripts/verify_swarm_mission_suite.py \
  --trace-root runs/swarm/live-mission-suite-after-objective-hardening \
  --report runs/swarm/live_mission_suite_after_objective_hardening_report.json \
  --report-out runs/swarm/live_mission_suite_after_objective_hardening_verify_report.json
```

Do not print or commit API keys. Keep live-provider results bounded to the
model, date, command, and scenario registry recorded in the evidence docs.

## Architecture Diagram

See `docs/submission/architecture.md`.

Short architecture statement:

```text
Qwen Cloud supplies bounded, low-rate semantic evidence. Local code validates
it, owns the HOLD / REVERIFY policy, emits a hash-chained DecisionTrace, and
verifies replay. The teleoperated Go2 capture and the deterministic swarm demo
are evidence sources, not Qwen-controlled robots.
```

## Alibaba ECS Proof Status

Status: public proof is not yet claimed complete.

Manual deployment checklist:

- `docs/engineering/alibaba-ecs-manual-deploy-2026-06-15.md`
- `docs/engineering/ecs-operator-proof-pack-2026-06-16.md`

Prepare the non-secret operator pack from the exact commit deployed to ECS.
Do not replace this value with the documentation branch HEAD:

```bash
DEPLOYED_COMMIT=a62c78ff8c1c82e73686afb18fcb52cf64c77a1b
python3 scripts/prepare_ecs_operator_pack.py --commit "$DEPLOYED_COMMIT"
```

The repo contains the minimal backend, Dockerfile, live
`/qwen-vl-fixture?model=qwen3-vl-flash` endpoint, and a collector that binds the
public endpoint to the deployed commit and ECS metadata. Promotion still
requires a sanitized collector report with `outcome: GO`, a Workbench screenshot
of the running resource, and a separate human proof review. Do not infer those
artifacts from the existence of deployment code.

## Demo Video Shot List

The final planned cut is 88 seconds and follows the QwenGuard hero path:

1. **0-5s — claim-safe title:** QwenGuard Sentry, human-teleoperated Go2, and
   post-run Qwen analysis.
2. **5-21s — two physical passes:** clock-aligned operator and Go2 views before
   and after the suitcase change. Label both passes `HUMAN TELEOP`.
3. **21-29s — Qwen Cloud evidence:** show the fixed-reference before/after
   comparison and the model-coordinate change receipt. Report `271` only as
   model-coordinate units, never pixels or metric distance.
4. **29-34s — Gemini 2 context:** show qualitative, independently normalized
   depth as supporting evidence, not a frame-paired or metric comparison.
5. **34-42s — spatial replay:** show the recorded Go2 onboard-SLAM point cloud
   and odometry in post-run DimOS replay. Do not label it raw L1 LiDAR.
6. **42-51s — trust boundary:** Qwen Cloud proposes semantics; strict local code
   validates output and retains all motor authority.
7. **51-64s — memory policy:** show `VERIFIED -> PROVISIONAL -> HOLD ->
   REVERIFY`, explicitly labeled post-run policy simulation with no robot
   actuation.
8. **64-74s — receipts:** show the DecisionTrace hash chain and replay
   verification.
9. **74-81s — Alibaba proof:** show only a redacted Workbench screenshot and
   sanitized `GO / ecs-public` evidence after human review.
10. **81-88s — close:** show the public repository, judge quickstart, Track 5,
    and the Qwen Cloud code link.

The upload must remain under three minutes, contain no unlicensed music or
third-party marks, and be public on YouTube, Vimeo, or Youku. Before submission,
inspect the complete encode for privacy and claim accuracy, then test playback
in a logged-out browser. The swarm replay is optional supporting material, not
the hero video.

## Submission Text Draft

QwenGuard demonstrates accountable edge-cloud robotics with Qwen in a bounded,
auditable role. Qwen Cloud provides low-rate semantic evidence; strict local
code validates the response and turns an ambiguous change into PROVISIONAL,
HOLD, and REVERIFY instead of granting motion authority. A privacy-safe replay
binds each decision to recorded receipts in a hash-chained DecisionTrace. The
physical Go2 capture was teleoperated, and the same repository also includes a
deterministic four-agent simulator as a secondary replay example.

## Final Non-Claims

- Physical Go2 capture was teleoperated; there was no Qwen-directed or
  autonomous robot motion.
- The post-run policy phases were not robot-runtime transitions.
- The Gemini 2 was a fixed independent reference, not a Go2-mounted or
  frame-synchronized sensor.
- The Go2 visualization is recorded onboard-SLAM point cloud plus odometry,
  not a raw L1 LiDAR claim.
- No SO-101 operation or ACT success claim.
- No 3D physics simulation.
- No latency claim.
- No reliability claim.
- DimOS was used to record and replay the Go2 streams. It was not in the motor
  loop, and this repository does not claim a runtime DecisionTrace integration.
- No Alibaba ECS deployment-proof claim until the final public collector,
  Workbench screenshot, and human review gates are complete.
- No Qwen real-time control.
- No Qwen onboard execution.
- No arbitrary-map planner claim.
- No larger-swarm claim beyond the listed deterministic four-agent integer-grid
  cases.
