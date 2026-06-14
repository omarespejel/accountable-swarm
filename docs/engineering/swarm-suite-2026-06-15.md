# Swarm Suite 2026-06-15

## Thesis

A deterministic swarm scenario suite can make the current simulated-swarm
evidence easier to rerun and harder to overclaim. The suite is a local
integer-grid replay gate, not a physics or hardware gate.

## Scope

The suite runs five fixed cases:

```text
n2-corridor-go
n2-center-block-go
n4-center-block-go
n4-vertical-slalom-go
n4-center-block-short-narrow
```

The final case is an expected `NARROW_CLAIM` canary. The suite outcome is `GO`
only when the expected-GO cases remain `GO`, the expected-NARROW case remains
`NARROW_CLAIM`, and all persisted traces replay deterministically.

## Commands

```bash
python3 -m unittest tests.test_swarm_suite_cli
python3 scripts/run_swarm_suite.py \
  --trace-root runs/swarm/suite \
  --report-out runs/swarm/suite_report.json
./scripts/local_gate.sh
```

## Result

```text
outcome GO
case_count 5
case n2-corridor-go expected GO actual GO
case n2-center-block-go expected GO actual GO
case n4-center-block-go expected GO actual GO
case n4-vertical-slalom-go expected GO actual GO
case n4-center-block-short-narrow expected NARROW_CLAIM actual NARROW_CLAIM
```

Pass conditions:

```text
all_agent_traces_replay_deterministic true
all_case_expectations_matched true
all_replay_matches_sim_reports true
all_replay_violation_counts_zero true
narrow_canary_present true
```

## Case Evidence

`n2-corridor-go`

```text
expected GO
actual GO
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
sim-agent-0 ee36e801aa67a48514faca572670f79a36a37f7259ed521c5b2e40e3f4625d3e
sim-agent-1 ef799eda1093892069a5d9e46a6a5875e325617406364406e6a855f3e1c3be63
```

`n2-center-block-go`

```text
expected GO
actual GO
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
sim-agent-0 f766d127847cd7a78bbddd6e825aa7b7a88b5b06a7cc4a25b0f42f5ce80ac881
sim-agent-1 9150893eb741b2c59163c20e88b844f659e2ee1a7b98d973aa207422a5e9ea63
```

`n4-center-block-go`

```text
expected GO
actual GO
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
sim-agent-0 5bbe753c32636a8e43942bcc95a6acd1bb7fe317dc7b04fe524ad0a16e231f92
sim-agent-1 5a4fbcf615a020aa6b92b614f84c9b98d329e5dad58337d93d849f24b1b0ec18
sim-agent-2 0b2fdbf3f178734b22802581b80f9282d87b9c1e535045c81bcf47fe894fa348
sim-agent-3 2c09beda24110a43c25fcb3f764ee5903e9baf4047eb1a26f6c535b6dd205a31
```

`n4-vertical-slalom-go`

```text
expected GO
actual GO
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
sim-agent-0 1167514b0a9701f51e98cfd9803e7ef076127209c40e32c90dd437ab5472e4ef
sim-agent-1 ebf15386eae44d9d026aaf96cfec1ff98c0a54c300035679b5fbbfa4d00e898d
sim-agent-2 eae8cbbbadace55a4e99cca4f71ec982fcd34545758f42f4ce23ad861cd98f6c
sim-agent-3 1ab461c6c6673c47541280dc895bff4a3a8d541e61fce5acc74d27c5f119e66d
```

`n4-center-block-short-narrow`

```text
expected NARROW_CLAIM
actual NARROW_CLAIM
same_cell_collision_count 0
swap_collision_count 0
obstacle_occupancy_violation_count 0
sim-agent-0 6c69c4d5225927cea46c0c4031e74cd7021c4032cd35ce3ce10cba98688814c9
sim-agent-1 17cc00b0010acc83ec60fcd767358a0004d4b54f098c185434b0daf9e1960e31
sim-agent-2 070b8673bbed091f5d972edf93ba7e034ac3a94c546df38354561a1cd39bd9c2
sim-agent-3 204d70d11a35f63336a0cfcfee6bfce220ee357cf3c40eaae25e76037d61cb5d
```

## GO Gate

- Suite report is canonical JSON and raw-float-free.
- All expected-GO cases report `GO`.
- The expected-NARROW canary reports `NARROW_CLAIM`.
- Every written agent trace is reloaded and verified from disk.
- Trace-derived replay counts match simulator report counts.
- Trace-derived replay reports zero same-cell, swap, and obstacle occupancy
  violations for all listed cases.

## Non-Claims

- No physical robot behavior.
- No SO-101 operation.
- No 3D physics simulation.
- No live Qwen mission assignment.
- No latency or reliability claim.
- No DimOS integration.
- No arbitrary-map planner claim.
- No larger-swarm claim beyond the listed deterministic integer-grid cases.
