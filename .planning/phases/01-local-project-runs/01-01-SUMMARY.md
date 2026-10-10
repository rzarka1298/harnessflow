---
phase: 01-local-project-runs
plan: "01"
subsystem: operations
tags: [local-dev, ci, skills]
provides: [managed local startup, genuine quality gates, installed development skills]
requirements-completed: [OPS-01, SKILLS-01]
coverage:
  - id: local-start
    description: Managed local startup and shutdown
    requirement: OPS-01
    verification:
      - kind: integration
        ref: scripts/tests/test_local_dev.py
        status: pass
    human_judgment: false
  - id: skill-provenance
    description: Pinned GSD and supplementary skill guidance
    requirement: SKILLS-01
    verification:
      - kind: other
        ref: Project-Documentation/skills.md
        status: pass
    human_judgment: false
status: complete
completed: 2026-10-10
---

# Managed local runtime and skills

`make dev` starts the local applications with bounded health checks and owned
process groups. `make check` is a genuine test/lint/type/build gate. GSD Core
1.16.0, webapp-testing and Vercel React guidance were installed and their limits
recorded. Commits: `8742433`, `dd170fb`, `85894a3`. Verification: eight launcher
tests, full `make check`, and live startup. The GSD installer reported unresolved
`.claude` references in some assets; inspect paths before invoking those flows.
