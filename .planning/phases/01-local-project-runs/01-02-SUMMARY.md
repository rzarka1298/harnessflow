---
phase: 01-local-project-runs
plan: "02"
subsystem: api
tags: [postgres, temporal, connect, protobuf]
provides: [durable project intake, versioned controls, reconciliation]
requirements-completed: [PRD-01, RUN-01, RUN-03]
coverage:
  - id: durable-run
    description: Project/run persistence and lifecycle controls
    requirement: RUN-01
    verification:
      - kind: integration
        ref: apps/api/internal/store/project_store_integration_test.go
        status: pass
      - kind: unit
        ref: go test ./apps/api/...
        status: pass
    human_judgment: false
status: complete
completed: 2026-10-10
---

# Durable project API

ProjectService accepts local Git paths and PRDs, stores run snapshots and
commands, and advances a Temporal workflow. Reconciliation repairs interrupted
scheduling; versioned controls avoid losing newer pause/resume/cancel intent.
Commits: `c05c4e7`, `5c9ce13`. Verification: Go lifecycle tests, isolated live
Postgres persistence test, generated-contract check, and real Codex fixtures.
