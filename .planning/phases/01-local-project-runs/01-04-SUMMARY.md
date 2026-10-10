---
phase: 01-local-project-runs
plan: "04"
subsystem: dashboard
tags: [nextjs, browser, projects]
provides: [project intake, progress and evidence UI]
requirements-completed: [UI-01]
coverage:
  - id: project-ui
    description: Intake, state, deferred controls, evidence and legacy replay
    requirement: UI-01
    verification:
      - kind: automated_ui
        ref: apps/dashboard/tests/browser_project_smoke.py
        status: pass
      - kind: other
        ref: make build
        status: pass
    human_judgment: false
status: complete
completed: 2026-10-10
---

# Project dashboard

The dashboard supports text/file PRD intake, project/run status, plan and attempt
details, versioned controls, blockers, artifact downloads and delivery links.
Legacy workflow navigation and replay remain available. Commit: `26888f5`.
Verified by production build, TypeScript, ESLint and a Playwright browser journey
covering completion, blocked/exhausted recovery, mobile layout and replay. The
browser journey mocks RPC; backend acceptance is recorded separately.
