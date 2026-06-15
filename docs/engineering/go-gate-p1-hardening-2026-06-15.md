# GO-Gate P1 Hardening 2026-06-15

Issue: #54

## Thesis

The single-frame GO-gate should prove the actual local loop, not only unit tests:
fixture frame -> bbox parsing -> local decision -> `DecisionTrace` ->
`verify_trace.py`. The decision should be a function of parsed perception, and
the live DashScope path should retry once when Qwen returns malformed bbox text.

## Scope

This PR closes the P1 surface of issue #54:

- `scripts/local_gate.sh` now runs the fixture GO-gate and trace verifier for a
  hazard frame and a clear frame;
- fixture hazard frame emits `VETO`;
- fixture clear frame emits `MOVE`;
- DashScope bbox calls send `temperature: 0`;
- DashScope bbox parsing retries once after malformed model text before failing;
- optional GO-gate grounding treats extracted empty arrays, including `[ ]` and
  prose-wrapped `[]`, as a clear frame while keeping the strict parser strict;
- trace hashing still rejects raw floats rather than quantizing arbitrary floats.

The P2/P3 items from issue #54 remain out of scope: package metadata,
entrypoints, score fields, and tiny-bbox policy.

## Commands

```bash
git diff --check
python3 -m unittest tests.test_go_gate_cli tests.test_qwen_client tests.test_qwen_bbox tests.test_trace
python3 -m scripts.run_go_gate \
  --image fixtures/hazard_marker.ppm \
  --mode fixture \
  --out runs/go_gate/p1_hazard_trace.json
python3 -m scripts.verify_trace runs/go_gate/p1_hazard_trace.json
python3 -m scripts.run_go_gate \
  --image fixtures/clear_frame.ppm \
  --mode fixture \
  --out runs/go_gate/p1_clear_trace.json
python3 -m scripts.verify_trace runs/go_gate/p1_clear_trace.json
```

## Observed Output

```text
Ran 25 tests in 0.462s
OK

wrote runs/go_gate/p1_hazard_trace.json
decision VETO
summary_sha 711e2e403d4f4d4be0b0a5ad57a9bce6c8d1c8d7cbde30ec731cbc359b3dacd9
verified runs/go_gate/p1_hazard_trace.json
summary_sha 711e2e403d4f4d4be0b0a5ad57a9bce6c8d1c8d7cbde30ec731cbc359b3dacd9

wrote runs/go_gate/p1_clear_trace.json
decision MOVE
summary_sha 73cf106f7d52e864f2de6f2db4e49cbb093dcd5d15daf12737613446aa1e9269
verified runs/go_gate/p1_clear_trace.json
summary_sha 73cf106f7d52e864f2de6f2db4e49cbb093dcd5d15daf12737613446aa1e9269
```

## Pass Conditions

- hazard fixture produces a verified `DecisionTrace` with decision `VETO`;
- clear fixture produces a verified `DecisionTrace` with decision `MOVE`;
- `scripts/local_gate.sh` runs both fixture traces and `verify_trace.py`;
- DashScope request payload pins `temperature` to `0`;
- malformed DashScope bbox text is retried exactly once in tests;
- empty optional Qwen detection arrays with whitespace or surrounding prose are
  interpreted as clear frames;
- repeated malformed DashScope bbox text fails with a controlled `ValueError`;
- no raw floats are introduced into hashed trace payloads.

## GO Gate

This gate is `GO` for issue #54 P1 fixture-mode hardening. The single-frame
local GO-gate now demonstrates a perception-dependent decision and deterministic
trace replay for both hazard and clear fixtures.

## Non-Claims

- No physical robot behavior.
- No SO-101 operation.
- No true webcam frame.
- No Alibaba ECS deployment proof.
- No latency or reliability claim.
- No DimOS integration.
- No Qwen onboard execution.
- No Qwen real-time control.
- No arbitrary scene understanding beyond the two fixture frames.
- No P2/P3 issue #54 closure.
