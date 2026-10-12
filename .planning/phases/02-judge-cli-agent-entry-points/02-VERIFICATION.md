---
phase: 02-judge-cli-agent-entry-points
verified: 2026-10-11
status: passed
score: 5/5 local-release must-haves verified
behavior_unverified: 1
---

# Phase 2: Judge, CLI and agent entry points verification

This is a retrospective verification of the shipped local release, not a claim
that GSD planned or dispatched Phase 2 before implementation. The three roadmap
plan labels summarize delivered work; no pre-execution PLAN/SUMMARY files are
being synthesized.

**Phase goal:** Launch durable PRD runs from a local file, expose explicit
requirement-level judge evidence, and retain the YAML platform as a maintained
foundation.

| Local-release truth | Status | Evidence |
| --- | --- | --- |
| File-based CLI starts a durable PRD run and reports its URL and status | Verified | Real three-task inventory, expense-report and WorkQueue runs in [acceptance](../../../Project-Documentation/projects/acceptance.md); CLI source and tests under `apps/cli`. |
| Codex and Claude Code skills hand off to the CLI from another workspace | Verified | Separate-workspace invocations in the acceptance record; installer tests in `scripts/tests/test_install_agent_skills.py`. |
| Read-only judge records per-requirement results after frozen checks and review | Verified | Real Codex verdicts for four, six, five and seven requirements across recorded runs; worker judge tests in `apps/worker/tests/test_project_judge.py`. |
| Completion still requires passing commands at the delivered commit | Verified | Four frozen commands at HEAD in the real fixtures, fail-closed worker tests, and independent fixture verifiers. |
| Existing YAML workflow remains operational alongside project runs | Verified | The merged local stack and post-merge CI include the legacy workflow checks and browser workflow; the platform is explicitly retained in [ADR-0010](../../../Project-Documentation/decisions/0010-project-judge-and-cli.md). |

**Score:** 5/5 local-release must-haves verified. JUDGE-01, CLI-01, SKILLS-02,
and the Codex fallback of JUDGE-02 have direct end-to-end evidence.

## Boundary and unverified behavior

The Anthropic judge path is implemented and unit-tested with a mocked provider
response, but no live Anthropic call was made because the user deferred it.
It is **not** release-proven against that provider. A configured key would send
the PRD, plan, diff, checks and review findings externally. This is one known
unverified behavior, not a claim that the local Codex-fallback release failed.

## Release evidence

- [PR #3](https://github.com/rzarka1298/harnessflow/pull/3) merged after its
  checks passed, on top of the merged [PR #2](https://github.com/rzarka1298/harnessflow/pull/2).
- The [post-merge main CI run](https://github.com/rzarka1298/harnessflow/actions/runs/38191066102)
  passed, including browser workflow coverage.
- The merged local stack served API readiness and dashboard pages; a live browser
  visit showed a completed WorkQueue run with delivery and judge evidence.
- Detailed fixtures, delivered commit hashes, frozen command results and
  independent acceptance checks are recorded in
  [projects/acceptance.md](../../../Project-Documentation/projects/acceptance.md).
