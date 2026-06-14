# Disclosure Ledger

Track dependencies, copied or adapted code, generated-AI assistance, model usage,
data sources, and external assets from day one.

## Repo Setup

| Date | Item | Source / Tool | License / Terms | Use | Notes |
|---|---|---|---|---|---|
| 2026-06-14 | Repository scaffold | Authored for `accountable-swarm` | Apache-2.0 | Hackathon submission repo | Initial review-bot and process setup. |
| 2026-06-14 | CodeRabbit configuration format | CodeRabbit docs | Documentation terms | PR review configuration | `.coderabbit.yaml` follows June 2026 config schema. |
| 2026-06-14 | Qodo configuration format | Qodo docs | Documentation terms | PR review configuration | `.pr_agent.toml` follows Qodo v2 repository config docs. |
| 2026-06-14 | Qwen-style grounding response shape | Qwen3-VL docs / Model Studio docs | Documentation terms | GO-gate parser and tests | Parser expects `bbox_2d` plus `label` and validates normalized 0-1000 coordinates. |
| 2026-06-14 | Deterministic hazard marker fixture | Authored for `accountable-swarm` | Apache-2.0 | Fixture-mode GO gate | Text PPM fixture for local-only tests; not used as a DashScope image. |

## Pending Before Demo

- Qwen / DashScope model IDs and API use.
- Alibaba Cloud ECS proof backend.
- SO-101 / LeRobot integration, if used.
- DimOS code or patterns, if copied or adapted.
- Any generated media, fixture images, traces, or demo assets.
