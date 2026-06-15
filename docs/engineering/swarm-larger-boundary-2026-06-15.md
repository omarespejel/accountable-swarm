# Swarm Larger-Agent Boundary 2026-06-15

## Thesis

The deterministic integer-grid swarm simulator should make its current
agent-count boundary executable before physical hardware work resumes. The
reviewed surface is N=2 and N=4 only.

## Why It Matters

The project is continuing swarm-first before SO-101 or other physical hardware.
That makes overclaim prevention part of the demo. A future agent or judge should
see that N=5/N=6 is intentionally outside the current reviewed evidence, not an
untested success path.

## Change

The simulator exposes `supported_agent_counts()` and the CLI uses that same
contract for `--agents`. Unsupported larger counts are rejected before any trace
or report artifact is written.

## Commands

```text
python3 -m unittest tests.test_swarm_sim tests.test_swarm_suite_cli
python3 scripts/run_swarm_suite.py --trace-root runs/swarm/suite --report-out runs/swarm/suite_report.json
python3 scripts/run_swarm_sim.py --agents 5 --ticks 20 --scenario center-block --trace-dir runs/swarm/n5-probe --report-out runs/swarm/n5_probe_report.json
git diff --check
```

Expected boundary probe:

```text
error: argument --agents: invalid choice: 5 (choose from 2, 4)
exit code 2
```

## GO Gate

- Supported simulator agent counts are exposed from one code-owned source.
- `run_swarm_sim(agent_count=5, ...)` rejects the request with a deterministic
  `ValueError`.
- `scripts/run_swarm_sim.py --agents 5 ...` rejects the request at CLI argument
  validation.
- Unsupported larger-count CLI probes do not create trace or report artifacts.
- Existing N=2/N=4 deterministic swarm suite remains `GO`.

## Non-Claims

- No N=5/N=6 swarm success claim.
- No physical robot behavior.
- No SO-101 operation.
- No 3D physics simulation.
- No live Qwen mission assignment.
- No latency or reliability claim.
- No DimOS integration.
