# Swarm Mission Suite Tamper Gate 2026-06-15

## Thesis

The mission-suite evidence is only useful if persisted traces fail closed after
mutation. This gate verifies that a clean suite report and trace root produce
`GO`, while a copied trace root with one mutated agent trace produces
`NARROW_CLAIM`.

## Scope

This is a local artifact-integrity gate. It verifies hash-chain and summary-SHA
consistency for mission and agent `DecisionTrace` files referenced by a swarm
mission-suite report.

## Clean Verification

```bash
python3 scripts/run_swarm_mission_suite.py \
  --trace-root runs/swarm/tamper-clean \
  --report-out runs/swarm/tamper_clean_report.json
python3 scripts/verify_swarm_mission_suite.py \
  --trace-root runs/swarm/tamper-clean \
  --report runs/swarm/tamper_clean_report.json \
  --report-out runs/swarm/tamper_clean_verify_report.json
```

Result:

```text
outcome GO
case_count 5
case mission-corridor-fixture-n4-go actual GO verified True
case mission-center-block-fixture-n4-go actual GO verified True
case mission-vertical-slalom-fixture-n4-go actual GO verified True
case mission-horizontal-slalom-fixture-n4-go actual GO verified True
case mission-double-chicane-fixture-n4-go actual GO verified True
```

## Tamper Verification

Mutation used for the evidence run:

```python
trace["events"][0]["command"]["accepted_x"] += 1
```

The mutation was applied to:

```text
mission-corridor-fixture-n4-go/trace/agents/sim-agent-0.json
```

Verifier command:

```bash
python3 scripts/verify_swarm_mission_suite.py \
  --trace-root runs/swarm/tamper-agent \
  --report runs/swarm/tamper_clean_report.json \
  --report-out runs/swarm/tamper_agent_verify_report.json
```

Result:

```text
outcome NARROW_CLAIM
case_count 5
case mission-corridor-fixture-n4-go actual GO verified False
case mission-center-block-fixture-n4-go actual GO verified True
case mission-vertical-slalom-fixture-n4-go actual GO verified True
case mission-horizontal-slalom-fixture-n4-go actual GO verified True
case mission-double-chicane-fixture-n4-go actual GO verified True
```

The failed case reports:

```text
error_type trace_artifact_invalid
error_classes ValueError
failed_trace_kinds agent:sim-agent-0
mission_trace_sha_matches_report true
agent_trace_shas_match_report false
trace_paths_relative true
```

## Pass Conditions

- clean suite verification exits 0 with `outcome GO`;
- copied-and-mutated trace root exits non-zero with `outcome NARROW_CLAIM`;
- verifier identifies the failed trace kind without storing raw trace contents;
- verifier reports only relative suite trace paths and sanitized error classes;
- local tests cover clean verification, agent-trace tamper, unsafe absolute
  path rejection, symlink escape rejection, malformed suite reports,
  incompatible suite schema versions, and pure summary-SHA mismatches.

## Non-Claims

- no live Qwen mission assignment;
- no physical robot behavior;
- no SO-101 operation;
- no 3D physics simulation;
- no latency or reliability claim;
- no DimOS integration;
- no cryptographic authenticity beyond local hash-chain verification;
- no adversarial file-system compromise model beyond persisted artifact
  mutation.
