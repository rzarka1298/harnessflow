---
phase: 01-local-project-runs
plan: "05"
subsystem: acceptance
tags: [codex, end-to-end, git]
provides: [real-model release evidence]
requirements-completed: [PRD-01, RUN-02, RUN-03, VERIFY-01, DELIVER-01, OPS-01]
coverage:
  - id: new-repository
    description: Empty Git repository receives a verified branch
    requirement: PRD-01
    verification:
      - kind: e2e
        ref: Project-Documentation/projects/acceptance.md
        status: pass
    human_judgment: false
  - id: existing-repository
    description: Dirty checkout remains unchanged while a branch is delivered
    requirement: DELIVER-01
    verification:
      - kind: e2e
        ref: Project-Documentation/projects/acceptance.md
        status: pass
    human_judgment: false
status: complete
completed: 2026-10-10
---

# Real-model acceptance

`scripts/project-smoke.py` ran through the public API with real Codex. The new
repository passed five frozen checks plus ten independently run unittests. The
existing dirty checkout passed three frozen checks plus five independently run
unittests, and retained its
original commit and personal note. Both used durable resume after integration
issues. These small fixtures do not prove arbitrary PRD completeness. Full run
IDs and boundaries: Project-Documentation/projects/acceptance.md.
Smoke-script commit: `9671d87`.
