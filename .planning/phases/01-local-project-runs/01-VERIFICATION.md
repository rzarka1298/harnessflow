---
phase: 01-local-project-runs
verified: 2026-10-11T22:25:00Z
status: passed
score: 8/8 must-haves verified
covered_files:
  - .planning/phases/01-local-project-runs/01-01-PLAN.md
  - .planning/phases/01-local-project-runs/01-01-SUMMARY.md
  - .planning/phases/01-local-project-runs/01-02-PLAN.md
  - .planning/phases/01-local-project-runs/01-02-SUMMARY.md
  - .planning/phases/01-local-project-runs/01-03-PLAN.md
  - .planning/phases/01-local-project-runs/01-03-SUMMARY.md
  - .planning/phases/01-local-project-runs/01-04-PLAN.md
  - .planning/phases/01-local-project-runs/01-04-SUMMARY.md
  - .planning/phases/01-local-project-runs/01-05-PLAN.md
  - .planning/phases/01-local-project-runs/01-05-SUMMARY.md
  - apps/api/internal/server/projectservice.go
  - apps/api/internal/server/projectservice_integration_test.go
  - apps/dashboard/tests/browser_project_smoke.py
  - apps/worker/harnessflow_worker/projects/engine.py
  - apps/worker/tests/test_project_execution.py
  - apps/worker/tests/test_project_publication.py
  - scripts/project-smoke.py
covered_digest: "v3:sha256:89ff99d341a6b98272224631e5eb0fa3cfcd4a57c931e90508b2d19f92eac22c"
behavior_unverified: 0
---

# Phase 1: Local project runs verification

**Phase goal:** A developer submits a PRD, sees durable progress, and receives a verified branch.

## Goal achievement

| Observable truth | Status | Evidence |
| --- | --- | --- |
| Accept new and existing local Git repositories | ✓ VERIFIED | Two real Codex fixtures completed through ProjectService; `scripts/project-smoke.py` and `Project-Documentation/projects/acceptance.md`. |
| Persist plan, tasks, attempts, evidence and controls | ✓ VERIFIED | Postgres lifecycle integration test and worker execution tests; restart/resume exercised in the real fixtures. |
| Enforce one repository writer | ✓ VERIFIED | Workspace locking and process tests cover contention and cleanup. |
| Pause, cancel, clarify and resume durably | ✓ VERIFIED | API integration and browser workflow tests; duplicate or ineligible resume requests cannot extend limits twice. |
| Repair within configured limits | ✓ VERIFIED | Worker execution tests and the real fixtures exercised repair and blocker/resume paths. |
| Require passing checks tied to delivered commit | ✓ VERIFIED | Fail-closed completion tests and real fixture check counts at delivered HEAD. |
| Preserve original checkout; provide branch, full diff and report | ✓ VERIFIED | Both real fixtures preserved original checkout; publication tests confirm full diff artifact and branch/report state. |
| Start locally and inspect progress/evidence in browser | ✓ VERIFIED | `make check`, CI browser workflow, and local browser smoke; dashboard and API launcher documented. |

**Score:** 8/8 must-haves verified.

## Requirements coverage

PRD-01, RUN-01 through RUN-03, VERIFY-01 and VERIFY-02, DELIVER-01 and
DELIVER-02, UI-01, OPS-01, and SKILLS-01 are satisfied by the evidence above
and the five plan summaries. Optional PR publication is tested, not performed
by the release fixtures.

## Verification record

- PR #2 head `a79711e`: `checks`, `eval-gate`, and GitGuardian passed on 2026-10-11.
- `make check` passed on the stacked branch containing this Phase 1 tree, with
  four non-failing generated-code ESLint warnings.
- Focused Go server, Postgres lifecycle, and worker publication tests passed
  after the review fixes.
- The recorded real-Codex runs are local and their transcripts are intentionally
  not committed because they may contain PRD and model output. The repeatable
  smoke script and commit-bound result summary are in the repository.

No blocking gap or remaining human verification item was identified. The
Anthropic judge path is a Phase 2 follow-up and is not part of this phase goal.
