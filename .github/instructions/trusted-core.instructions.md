---
applyTo: "accountable_swarm/**,scripts/**,tests/**,.codex/**,docs/engineering/**,docs/security/**"
---

# Trusted-Core Instructions

Treat these paths as trusted-core robotics evidence code.

Review for:

- deterministic replay and stable hashes;
- strict parser validation;
- negative tests for malformed Qwen output and trace tampering;
- no secret leakage;
- bounded file and path handling;
- physical-device hold-by-default behavior;
- exact commands for evidence-producing scripts;
- documentation that does not overstate the evidence.

Any behavior that can move hardware must include operator arming, workspace
bounds, low-speed defaults, and an emergency-stop path before it leaves
experimental status.
