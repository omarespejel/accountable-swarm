# Research Operating Notes

This directory is the research control plane for agents.

The repo is run as a lab, not a normal feature backlog. Issues are hypotheses,
not task buckets. A good issue names the thesis, the smallest falsifying
experiment, exact GO/NO-GO gates, required artifacts, and non-claims.

## Lanes

`default`

Stable repo behavior, schemas, tests, judge quickstart, and conservative docs.

`experimental`

Qwen prompts, SO-101 adapters, simulated swarm behavior, DimOS integration,
visualization, and Alibaba deployment wiring. Experimental results cannot
silently become public claims.

`claim`

README, Devpost, demo script, deck, blog, social post, or any external wording.
Claims need checked artifacts, exact commands, and non-claims.

`hardening`

DecisionTrace determinism, hash-chain replay, coordinate normalization, key
handling, physical safety, path safety, and generated artifact integrity.

## Unit Of Work

Use the GitHub issue templates:

- `GO-gate hypothesis` for experiments;
- `Hardening follow-up` for risks;
- `Public claim` for external wording.

Allowed outcomes:

- `GO`: continue or promote within the stated boundary;
- `NO_GO`: stop the path;
- `NARROW_CLAIM`: keep only the part the evidence supports;
- `FOLLOWUP_ISSUE`: park scoped work without widening the PR;
- `KILL`: remove or abandon the path.

## Evidence Standard

Evidence is not real unless another agent can rerun it.

Prefer:

- checked-in docs under `docs/engineering/`;
- machine-readable JSON traces under `runs/` only when small and intentional;
- exact commands;
- deterministic regeneration;
- explicit non-claims.

Avoid:

- screenshots as the only evidence;
- undocumented local service state;
- unbounded "it works" claims;
- generated assets without provenance.
