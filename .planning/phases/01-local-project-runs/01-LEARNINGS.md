---
phase: 01
phase_name: "local-project-runs"
project: "HarnessFlow"
generated: "2026-10-12"
counts:
  decisions: 4
  lessons: 4
  patterns: 4
  surprises: 3
missing_artifacts:
  - "01-UAT.md"
---

# Phase 01 Learnings: Local project runs

## Decisions

### Durable commands and snapshots
ProjectService stores run snapshots and versioned pause, resume, and cancel commands; Temporal advances a run through recoverable ticks.

**Rationale:** Reconciliation can repair interrupted scheduling without silently losing newer user intent.
**Source:** 01-02-PLAN.md; 01-02-SUMMARY.md

### Isolated Git worktrees
Coding runs use a separate worktree and branch, with a repository lock held through supervised subprocesses.

**Rationale:** The original checkout, including uncommitted work, must remain unchanged and concurrent writers must not race.
**Source:** 01-03-PLAN.md; 01-03-SUMMARY.md

### Completion requires exact-revision checks
Frozen executable checks and a clean final HEAD gate delivery; model claims and read-only review do not replace command results.

**Rationale:** The delivered commit must be the one that actually passed verification.
**Source:** 01-03-PLAN.md; 01-03-SUMMARY.md; 01-VERIFICATION.md

### Explicit publication target
Optional PR publication fails closed unless GitHub origin and the default-branch base are unambiguous.

**Rationale:** A local coding run must not infer a remote target or publish to an unintended repository.
**Source:** 01-03-SUMMARY.md; 01-VERIFICATION.md

## Lessons

### Durable resume matters in real runs
Both real-Codex fixtures needed resume after integration issues and still reached verified branches.

**Context:** The resume path was exercised by actual API-backed runs, beyond unit-only lifecycle coverage.
**Source:** 01-05-SUMMARY.md

### Browser and backend evidence are complementary
The browser journey mocks RPC and verifies the user interaction contract; backend acceptance is recorded separately.

**Context:** A passing browser test alone would not establish the durable API and worker behavior.
**Source:** 01-04-SUMMARY.md; 01-VERIFICATION.md

### Small live fixtures have a narrow claim
The greeting fixtures prove the local new/existing-repository path, not completeness for arbitrary PRDs.

**Context:** They independently ran behavioral tests and preserved the original checkout, but their task scope was intentionally small.
**Source:** 01-05-SUMMARY.md

### Installed skill assets still need path checks
The GSD installer reported unresolved `.claude` references in some installed assets.

**Context:** Installed tooling provenance was verified, but affected flows should be inspected before invocation.
**Source:** 01-01-SUMMARY.md

## Patterns

### Versioned control reconciliation
Persist a control request with a version, then reconcile asynchronous work against the latest version.

**When to use:** Long-running workflows where signals can arrive during retries or restarts.
**Source:** 01-02-PLAN.md; 01-02-SUMMARY.md

### Owned-process lifecycle
Launch local services with bounded health checks and owned process groups; stop only processes started by the launcher.

**When to use:** Developer tooling that supervises several local services without disrupting unrelated processes.
**Source:** 01-01-PLAN.md; 01-01-SUMMARY.md

### Commit-bound delivery gate
Freeze requirement-linked argv, run checks directly, then recheck status and evidence at the final commit before delivery.

**When to use:** Autonomous coding systems where implementation and repair can change code after an earlier successful check.
**Source:** 01-03-PLAN.md; 01-03-SUMMARY.md; 01-VERIFICATION.md

### Independent fixture assertions
Run real-model fixtures through the public API, then execute behavioral assertions outside the harness and compare the original repository state.

**When to use:** End-to-end acceptance that must detect self-reported success or unintended source-checkout changes.
**Source:** 01-05-PLAN.md; 01-05-SUMMARY.md

## Surprises

### Resume was necessary even for tiny fixtures
Both new and existing greeting runs encountered integration issues requiring durable resume.

**Impact:** The release evidence exercised recovery behavior, not just a happy-path implementation.
**Source:** 01-05-SUMMARY.md

### Installed GSD references were not uniformly resolved
Some installed assets retained unresolved `.claude` references.

**Impact:** Skill installation alone was insufficient to guarantee every referenced path was usable.
**Source:** 01-01-SUMMARY.md

### Shared Phase 1 worker files changed during Phase 2
Phase 2 modified shared worker files after the initial Phase 1 implementation.

**Impact:** The Phase 1 verification fingerprint had to be refreshed against the stacked branch; the behavior remained verified.
**Source:** 01-VERIFICATION.md
