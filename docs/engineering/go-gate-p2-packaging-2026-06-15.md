# GO-Gate P2 Packaging And Scalar Hardening

Date: 2026-06-15 JST

## Thesis

The first GO-gate should be installable as a small Python package, and the
hashed trace payload should reject raw motion floats before they enter command
hashing.

## Change

- Added `pyproject.toml` with zero runtime third-party dependencies.
- Added console entry points:
  - `run-go-gate`
  - `verify-trace`
- Made `scripts.run_go_gate` and `scripts.verify_trace` importable module
  entry points without local `sys.path.insert(...)` mutation.
- Updated `scripts/local_gate.sh` to install the package in a temporary virtual
  environment and run the installed console entry points.
- Added an explicit `DecisionEvent.command` raw-float rejection before command
  hashing.

## Validation

Focused local checks:

```text
python3 -m unittest tests.test_trace tests.test_go_gate_cli tests.test_packaging
git diff --check
python3 -m scripts.run_go_gate --image fixtures/hazard_marker.ppm --mode fixture --out runs/go_gate/p2_module_trace.json
python3 -m scripts.verify_trace runs/go_gate/p2_module_trace.json
```

Editable-install check from outside the repository with Python 3.11:

```text
PY311=${PY311:-python3.11}
REPO_ROOT=$(pwd)
tmpdir=$(mktemp -d /tmp/accountable-swarm-p2-venv.XXXXXX)
"$PY311" -m venv "$tmpdir/venv"
"$tmpdir/venv/bin/python" -m pip install -e .
cd /tmp
"$tmpdir/venv/bin/run-go-gate" --image "$REPO_ROOT/fixtures/hazard_marker.ppm" --mode fixture --out "$tmpdir/trace.json"
"$tmpdir/venv/bin/verify-trace" "$tmpdir/trace.json"
rm -rf "$tmpdir"
```

Python 3.9 note:

```text
The system Python 3.9 bundled pip was too old for editable pyproject installs.
The README quickstart now upgrades pip before `pip install -e .`.
```

## GO / NO-GO

GO for the scoped packaging gate if:

- editable install succeeds after pip is current;
- `run-go-gate` and `verify-trace` run from outside the repo;
- the local gate proves installed console entry points in a temporary virtual
  environment without `PYTHONPATH` injection;
- raw floats in `command` are rejected before trace hashing.

NO-GO if:

- installing the package adds runtime third-party dependencies;
- the local GO-gate requires cloud credentials;
- direct command floats can enter a persisted hash body.

## Non-Claims

- No new Qwen model capability claim.
- No physical robot, SO-101, webcam, ECS deployment, latency, reliability,
  safety, DimOS integration, or larger-swarm claim.
- The package metadata makes the local gate easier to run; it is not a
  production robotics runtime claim.
