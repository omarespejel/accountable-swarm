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

Do not commit API keys, raw secrets, or cloud credentials.

## Claim Scope Reminder

Passing fixture mode means only that the local trace spine is deterministic for
the fixture. Passing the deterministic swarm gate means only that the integer
grid scenario emits replayable traces with zero reported same-cell or swap
collisions. These gates do not prove live Qwen behavior, SO-101 operation,
physical safety, physics-backed swarm behavior, Alibaba deployment, latency, or
reliability.

Any public-facing claim needs a `Public claim` issue and the promotion gate in
`.codex/research/north_star.yml`.
