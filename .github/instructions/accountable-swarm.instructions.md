# Repository Review Instructions

Review this repository as safety-sensitive robotics evidence code.

Prioritize:

- deterministic DecisionTrace serialization and replay;
- Qwen response validation and bbox normalization;
- physical-device safety guards;
- secret handling;
- clear separation of cloud reasoning from local control;
- public claim boundaries;
- reproducible commands and judge-friendly setup.

Avoid:

- style-only churn;
- broad refactors;
- claims that are not backed by checked artifacts;
- adding Qwen or any LLM/VLM to real-time motion control.
