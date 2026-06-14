# Research Lab Setup 2026-06-14

This note records the repo-lab setup decisions for Accountable Swarm.

## Sources Checked

- CodeRabbit YAML docs: repo-root `.coderabbit.yaml` is the version-controlled
  configuration file, and the feature-branch config is used for review.
- CodeRabbit tools reference: the tools reference was generated on 2026-06-02
  and lists static-analysis integrations configurable through `.coderabbit.yaml`.
- Qodo docs: Qodo Code Review v2 is the current pull-request review experience,
  and repo configuration is read from `.pr_agent.toml`.
- GitHub issue forms docs: issue forms live in `.github/ISSUE_TEMPLATE` and
  require `name`, `description`, and `body`.
- GitHub repository-instructions docs: `.github/copilot-instructions.md` and
  `.github/instructions/*.instructions.md` provide repo and path-specific
  instructions for GitHub Copilot cloud agent and code review.
- GitHub rulesets and branch-protection docs: rulesets can layer across branch
  targets; branch protection can require PRs and status checks. We keep the
  repo-side docs ready, but do not hard-require CodeRabbit as a branch check
  until it is stable in this repo.

## Decision

Use the `provable-transformer-vm` research-lab pattern, adapted to robotics:

- `AGENTS.md` remains the repo constitution.
- `.codex/START_HERE.md` is the fresh-agent entrypoint.
- `.codex/HANDOFF.md` records active evidence and blockers.
- `.codex/research/north_star.yml` defines the thesis and forbidden claims.
- `.codex/research/operating_model.yml` defines issue-as-hypothesis workflow,
  review-bot policy, and merge discipline.
- `docs/engineering/reproducibility.md` defines the local evidence loop.
- `docs/engineering/hardening-policy.md` defines trusted-core hardening.
- `docs/security/threat-model.md` defines adversaries and non-goals.
- `.github/copilot-instructions.md` and `.github/instructions/*.instructions.md`
  steer GitHub-native agents back to the same constitution.

## Repo-Settings Recommendation

These settings require owner/admin action in GitHub and are not encoded by this
PR:

- protect `main`;
- require pull requests before merge;
- require linear history;
- block force pushes and deletions;
- require `local-gate` status check once the workflow is stable;
- require conversation resolution;
- keep CodeRabbit/Qodo operationally required through review policy before
  making either a hard branch-protection check.

## Non-Claims

This setup does not prove:

- live Qwen works;
- Qodo or CodeRabbit are installed on every fork;
- branch protection is enabled;
- physical-device safety;
- swarm behavior;
- Alibaba deployment;
- hackathon acceptance.

It only makes the research operating system explicit, reviewable, and enforced
by the local gate.
