# Disclosure Ledger

Track dependencies, copied or adapted code, generated-AI assistance, model usage,
data sources, and external assets from day one.

## Repo Setup

| Date | Item | Source / Tool | License / Terms | Use | Notes |
|---|---|---|---|---|---|
| 2026-06-14 | Repository scaffold | Authored for `accountable-swarm` | Apache-2.0 | Hackathon submission repo | Initial review-bot and process setup. |
| 2026-06-14 | CodeRabbit configuration format | CodeRabbit docs | Documentation terms | PR review configuration | `.coderabbit.yaml` follows June 2026 config schema. |
| 2026-06-14 | Qodo configuration format | Qodo docs | Documentation terms | PR review configuration | `.pr_agent.toml` follows Qodo v2 repository config docs. |
| 2026-06-14 | GitHub issue forms and repo instructions | GitHub docs | Documentation terms | Issue templates, Copilot instructions, branch-protection note | Used to keep GitHub-native agents aligned with repo operating rules. |
| 2026-06-14 | Qwen-style grounding response shape | Qwen3-VL docs / Model Studio docs | Documentation terms | GO-gate parser and tests | Parser expects `bbox_2d` plus `label` and validates normalized 0-1000 coordinates. |
| 2026-06-14 | Deterministic hazard marker fixture | Authored for `accountable-swarm` | Apache-2.0 | Fixture-mode GO gate | Text PPM fixture for local-only tests; not used as a DashScope image. |
| 2026-06-14 | DashScope compatible-mode API path | Alibaba Cloud Model Studio docs | Service terms apply | Optional live Qwen GO-gate mode | Uses `ALIBABA_API_KEY` from environment and `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`; no key committed. |
| 2026-06-15 | Deterministic integer-grid swarm simulator | Authored for `accountable-swarm` | Apache-2.0 | Simulated N=2 DecisionTrace GO gate and exploratory N=4 probe | No external swarm code copied; no physics, DimOS, or physical-device claim. |
| 2026-06-15 | Low-rate swarm mission gate | Authored for `accountable-swarm` | Apache-2.0 | Fixture/Qwen-style mission JSON validation before deterministic local swarm planning | Fixture mode is checked; live DashScope mission assignment is not claimed unless separately recorded. |
| 2026-06-15 | Deterministic swarm scenario suite | Authored for `accountable-swarm` | Apache-2.0 | Multi-case integer-grid swarm regression and overclaim canary | Includes expected `NARROW_CLAIM` case; no physics, hardware, DimOS, or larger-swarm claim. |
| 2026-06-15 | Vertical-slalom swarm scenario | Authored for `accountable-swarm` | Apache-2.0 | Second fixed two-obstacle N=4 integer-grid swarm gate | No external planner code copied; no arbitrary-map, physics, hardware, or larger-swarm claim. |
| 2026-06-15 | Fixed swarm scenario registry | Authored for `accountable-swarm` | Apache-2.0 | Central source of truth for current deterministic scenario metadata | No user-supplied layouts, arbitrary-map planning, physics, hardware, or larger-swarm claim. |
| 2026-06-15 | Horizontal-slalom swarm scenario | Authored for `accountable-swarm` | Apache-2.0 | Third fixed two-obstacle N=4 integer-grid swarm gate | No external planner code copied; no arbitrary-map, physics, hardware, or larger-swarm claim. |
| 2026-06-15 | Registry-bound swarm mission scenario selection | Authored for `accountable-swarm` | Apache-2.0 | Fixture/DashScope mission prompt selection from reviewed scenario names | No live Qwen mission claim without separate DashScope evidence; no arbitrary-map or hardware claim. |
| 2026-06-15 | Fixture swarm mission suite | Authored for `accountable-swarm` | Apache-2.0 | Multi-scenario fixture mission regression through the reviewed scenario registry | Runs local fixture mission gates only; no live Qwen, hardware, physics, latency, reliability, or arbitrary-map claim. |
| 2026-06-15 | Swarm mission-suite tamper verifier | Authored for `accountable-swarm` | Apache-2.0 | Local verification of persisted mission-suite trace artifacts and negative tamper gate | No cryptographic authenticity claim beyond local hash-chain verification; no hardware, cloud, latency, or reliability claim. |
| 2026-06-15 | Live DashScope swarm mission assignment | Alibaba Cloud Model Studio / DashScope `qwen-plus` | Service terms apply | Low-rate live mission-intent evidence for reviewed `center-block` deterministic swarm scenario | API key loaded from local environment only; no key committed; no Qwen real-time control, hardware, physics, latency, reliability, arbitrary-map, or ECS deployment claim. |
| 2026-06-15 | Live DashScope swarm mission suite | Alibaba Cloud Model Studio / DashScope `qwen-plus` | Service terms apply | Low-rate live mission-intent evidence across reviewed deterministic swarm scenarios | API key loaded from local environment only; no key committed; no Qwen real-time control, hardware, physics, latency, reliability, arbitrary-map, larger-swarm, or ECS deployment claim. |
| 2026-06-15 | Swarm trace HTML renderer | Authored for `accountable-swarm` | Apache-2.0 | Deterministic static HTML/SVG replay and canonical summary from verified persisted swarm traces | No external renderer code copied; no physical, physics, live-Qwen, latency, reliability, arbitrary-map, or larger-swarm claim. |
| 2026-06-15 | Swarm demo bundle builder | Authored for `accountable-swarm` | Apache-2.0 | One-command deterministic local demo bundle over reviewed swarm scenarios | Orchestrates repo-authored simulator and renderer only; no physical, cloud, live-Qwen, DimOS, Docker, latency, reliability, arbitrary-map, or larger-swarm claim. |

## Pending Before Demo

- Qwen / DashScope model IDs and API use.
- Alibaba Cloud ECS proof backend.
- SO-101 / LeRobot integration, if used.
- DimOS code or patterns, if copied or adapted.
- Any generated media, fixture images, traces, or demo assets.
