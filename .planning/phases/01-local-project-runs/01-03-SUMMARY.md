---
phase: 01-local-project-runs
plan: "03"
subsystem: worker
tags: [codex, git, sandbox, recovery]
provides: [isolated execution, commit-bound verification, safe optional publication]
requirements-completed: [RUN-02, RUN-03, VERIFY-01, VERIFY-02, DELIVER-01, DELIVER-02]
coverage:
  - id: bounded-execution
    description: Resumable planning, coding, review, verification and repair
    requirement: RUN-02
    verification:
      - kind: integration
        ref: apps/worker/tests/test_project_execution.py
        status: pass
    human_judgment: false
  - id: verified-branch
    description: Clean branch with frozen checks tied to the final commit
    requirement: VERIFY-01
    verification:
      - kind: e2e
        ref: Project-Documentation/projects/acceptance.md
        status: pass
    human_judgment: false
  - id: publication-target
    description: Explicit validated origin/default-branch PR target
    requirement: DELIVER-02
    verification:
      - kind: unit
        ref: apps/worker/tests/test_project_publication.py
        status: pass
    human_judgment: false
status: complete
completed: 2026-10-10
---

# Recoverable Codex execution

The worker owns an isolated worktree and branch, durable phase state, bounded
attempt/time limits, frozen checks and independent review. A clean HEAD with
passing real commands is required for delivery. Native sandbox tests exercise
write/network restrictions. Optional PR publication fails closed unless GitHub
origin and base are unambiguous. Core commit: `e11cb3e`; final sandbox and
publication hardening are included on this branch. Verified by worker tests,
five opt-in native CLI sandbox tests and two real-Codex fixtures.
