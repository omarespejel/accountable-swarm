# Engineering Reproducibility

This repo should be reproducible by a judge, a teammate, or a fresh agent from a
clean checkout.

## Baseline Command

Run from the repository root:

```bash
./scripts/local_gate.sh
```

The local gate checks:

- whitespace hygiene via `git diff --check`;
- required repo-governance files;
- `.pr_agent.toml` syntax when `tomllib` is available;
- `.coderabbit.yaml` syntax when `PyYAML` is available;
- the Python unit test suite.

## Evidence Rules

Every experimental result needs enough evidence for another agent to rerun it.

Use:

- `docs/engineering/*.md` for human-readable notes;
- `runs/**` only for small, intentional trace fixtures;
- exact commands in the doc or PR body;
- deterministic JSON serialization for traces;
- integer or string scalar encoding for measurements that enter trace hashes;
- explicit non-claims.

Avoid:

- timestamps in generated machine-readable artifacts unless time is the measured
  object;
- host-specific absolute paths in committed evidence;
- screenshots as the only evidence;
- undocumented cloud console state;
- hidden local secrets.

See `docs/engineering/trace-scalar-policy.md` before adding depth, confidence,
pose, latency, or other measured values to traces.

## Reproducing The Current GO Gate

Fixture mode:

```bash
python3 scripts/run_go_gate.py \
  --image fixtures/hazard_marker.ppm \
  --mode fixture \
  --out runs/go_gate/trace.json
python3 scripts/verify_trace.py runs/go_gate/trace.json
```

DashScope mode requires an environment variable:

```bash
ALIBABA_API_KEY=... python3 scripts/run_go_gate.py \
  --image runs/go_gate/hazard_marker.png \
  --mode dashscope \
  --out runs/go_gate/qwen_trace.json
python3 scripts/verify_trace.py runs/go_gate/qwen_trace.json
```

Camera/static-frame gate:

```bash
python3 scripts/run_camera_go_gate.py \
  --image fixtures/hazard_marker.ppm \
  --mode fixture \
  --trace-out runs/go_gate/camera_trace.json \
  --report-out runs/go_gate/camera_report.json
python3 scripts/verify_trace.py runs/go_gate/camera_trace.json
```

Deterministic N=2 swarm gate:

```bash
python3 scripts/run_swarm_sim.py \
  --agents 2 \
  --ticks 8 \
  --trace-dir runs/swarm/n2 \
  --report-out runs/swarm/n2_report.json
python3 scripts/verify_trace.py runs/swarm/n2/sim-agent-0.json
python3 scripts/verify_trace.py runs/swarm/n2/sim-agent-1.json
```

The swarm report includes trace-derived replay fields so another agent can
recompute final positions and collision counts from the emitted traces.

Deterministic N=2 obstacle gate:

```bash
python3 scripts/run_swarm_sim.py \
  --agents 2 \
  --ticks 9 \
  --scenario center-block \
  --trace-dir runs/swarm/center-block-n2 \
  --report-out runs/swarm/center_block_n2_report.json
```

The obstacle report also includes trace-derived obstacle-occupancy violation
counts.

Deterministic N=4 obstacle gate with bounded reservation planner:

```bash
python3 scripts/run_swarm_sim.py \
  --agents 4 \
  --ticks 16 \
  --scenario center-block \
  --trace-dir runs/swarm/reservation-center-block-n4 \
  --report-out runs/swarm/reservation_center_block_n4_report.json
```

This report must show `outcome GO`, `all_goals_reached true`, zero same-cell
collisions, zero swap collisions, zero obstacle occupancy violations, and the
same zero counts in the trace-derived replay section.

Deterministic N=4 vertical-slalom obstacle gate:

```bash
python3 scripts/run_swarm_sim.py \
  --agents 4 \
  --ticks 16 \
  --scenario vertical-slalom \
  --trace-dir runs/swarm/vertical-slalom-n4 \
  --report-out runs/swarm/vertical_slalom_n4_report.json
```

This report must show `outcome GO`, obstacles at `(3, 1)` and `(3, 3)`, all
four agents reaching goals, zero same-cell collisions, zero swap collisions,
zero obstacle occupancy violations, and matching zero counts in the
trace-derived replay section.

Deterministic N=4 horizontal-slalom obstacle gate:

```bash
python3 scripts/run_swarm_sim.py \
  --agents 4 \
  --ticks 16 \
  --scenario horizontal-slalom \
  --trace-dir runs/swarm/horizontal-slalom-n4 \
  --report-out runs/swarm/horizontal_slalom_n4_report.json
```

This report must show `outcome GO`, obstacles at `(2, 2)` and `(4, 2)`, all
four agents reaching goals, zero same-cell collisions, zero swap collisions,
zero obstacle occupancy violations, and matching zero counts in the
trace-derived replay section.

Low-rate fixture mission gate:

```bash
python3 scripts/run_swarm_mission_gate.py \
  --mode fixture \
  --trace-dir runs/swarm/mission-fixture-n4 \
  --report-out runs/swarm/mission_fixture_n4_report.json
```

This report must show validated mission JSON, a deterministic mission trace
replay, simulator `GO`, and zero same-cell, swap, and obstacle-occupancy counts
in the agent trace-derived replay section.

Do not commit API keys, raw secrets, or cloud credentials.

Deterministic swarm suite:

```bash
python3 scripts/run_swarm_suite.py \
  --trace-root runs/swarm/suite \
  --report-out runs/swarm/suite_report.json
```

This report must show suite `outcome GO`, expected-GO cases still `GO`, the
vertical-slalom and horizontal-slalom cases still `GO`, the short N=4 canary
still `NARROW_CLAIM`, deterministic agent trace replay from disk, replay
counts matching simulator counts, and zero same-cell, swap, and
obstacle-occupancy replay violations.

## Claim Scope Reminder

Passing fixture mode means only that the local trace spine is deterministic for
the fixture. Passing deterministic swarm gates means only that the scoped
integer-grid scenarios emit replayable traces with zero reported same-cell,
swap, and, where applicable, obstacle-occupancy violations. These gates do not
prove live Qwen behavior, SO-101 operation, physical safety, physics-backed
swarm behavior, Alibaba deployment, latency, reliability, live Qwen mission
assignment, or a general-purpose multi-agent planner.

Any public-facing claim needs a `Public claim` issue and the promotion gate in
`.codex/research/north_star.yml`.
