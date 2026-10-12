# Roadmap

## Phase 1: Local project runs

Goal: A developer submits a PRD, sees durable progress, and receives a verified branch.

Plans:
- 01-01: Reliable local runtime and genuine checks.
- 01-02: Project API, durable scheduler and versioned controls.
- 01-03: Isolated Codex execution, independent verification and recovery.
- 01-04: Project dashboard and browser acceptance.
- 01-05: Integrated real-Codex demonstrations and release evidence.

## Phase 2: Judge, CLI and agent entry points

Goal: Launch durable PRD runs from a local file, expose explicit requirement-level
judge evidence, and retain the YAML platform as a maintained foundation.

Plans:
- 02-01: Evidence-bound judge after read-only review; Anthropic when configured,
  read-only Codex fallback, deterministic completion gate unchanged.
- 02-02: Installable CLI and thin repo-local Codex/Claude Code skills.
- 02-03: Multi-task acceptance fixture, browser evidence, and real Codex trial.

The independent Anthropic path needs a live credentialed validation before it can
be called release-proven. This phase uses GSD evaluation guidance, but the generic
agent runner does not implement GSD's typed AI-phase role-dispatch workflow.

## Progress

| Phase | Plans Complete | Status | Completed |
| --- | --- | --- | --- |
| 1. Local project runs | 5/5 | Complete | 2026-10-11 |
| 2. Judge, CLI and agent entry points | 3/3 | Complete | 2026-10-11 |

Phase 2 was implemented and tested before its GSD directory was reconciled.
The three plan labels above describe shipped work retrospectively; they are not
being presented as pre-execution GSD plans. See the Phase 2 verification report
and [release acceptance](../Project-Documentation/projects/acceptance.md).

## Deferred

Hosted tenancy/authentication, additional coding engines, automatic deployment,
AWS rollout, contextual bandits and autonomous YAML optimization. Cloud deployment
will be considered only after the remaining local tasks are complete. The
protected opt-in real-model CI job is the next local follow-up; live Anthropic
validation remains deferred by user choice.
