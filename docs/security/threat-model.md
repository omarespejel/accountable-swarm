# Threat Model

This threat model covers the early Accountable Swarm hackathon repo as of
2026-06-14.

The current system is a trace and evidence spine. It is not a safety-certified
robotics stack.

## Security Objectives

The repository aims to:

- keep secrets out of code, docs, traces, and logs;
- validate external model output before using it;
- preserve deterministic `DecisionTrace` replay;
- detect trace tampering through hash-chain checks;
- prevent initial physical-device paths from silently moving hardware;
- keep public claims aligned with checked evidence.

## Claim Classes

`Fixture evidence`

Local deterministic tests over committed fixtures. Useful for parser, trace, and
replay correctness. Not evidence of live model behavior.

`Live model evidence`

Qwen/DashScope calls over real images with recorded model ID, prompt, validated
response shape, and redacted artifacts. Not evidence of real-time control.

`Physical trace evidence`

Observed sensor frame or hardware state converted into a trace, with no
autonomous motion unless a later safety gate explicitly allows it.

`Public demo claim`

README, Devpost, deck, video, or social wording. Requires evidence paths,
commands, and non-claims.

## In-Scope Adversaries

- malformed model-output producer;
- prompt-response drift or model-version drift;
- trace tamperer;
- path traversal or unsafe file writer;
- accidental secret committer;
- stale-evidence reuser;
- physical-motion footgun introduced during integration;
- claim-drift author who upgrades fixture evidence into public demo claims.

## Trusted Assumptions

- Local development machines are not maliciously compromised.
- Python standard-library JSON and hashing behave correctly.
- API keys are supplied only through environment variables or approved secret
  stores.
- Operators keep physical hardware powered off or unarmed unless a PR adds an
  explicit safety gate.

## Intended Rejections

The system should reject or fail closed on:

- non-JSON Qwen responses where JSON is required;
- missing `bbox_2d` or `label`;
- non-integer bbox coordinates;
- normalized coordinates outside `0..1000`;
- boxes with non-positive area;
- image-dimension mismatches;
- trace hash mismatch;
- missing or incorrect `prev_sha`;
- physical actions other than `hold` in trace-only mode;
- missing API key in live mode.

## Explicit Non-Goals

This repository does not currently prove:

- physical robot safety;
- policy optimality;
- perception correctness;
- Qwen truthfulness;
- Qwen onboard execution;
- physical or physics-backed swarm collision avoidance;
- real-time latency;
- reliability;
- Alibaba deployment;
- DimOS integration completeness.

## Operational Policy

Public text must state the evidence boundary. If a claim depends on live Qwen,
physical hardware, cloud deployment, or swarm behavior, it needs a dedicated
issue and checked artifacts before promotion.
