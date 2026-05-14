# ADR-0001: Use Temporal Go SDK, don't roll a custom orchestrator

Date: 2026-05-14
Status: Accepted

## Context

HarnessFlow needs a durable workflow execution engine: state persistence, retries, signals (for approval gates), child workflows, scheduling. The PRD positions the platform as "Temporal for AI agents," so the question is: do we build the orchestrator from scratch, or use Temporal under the hood?

Building a custom orchestrator would mean implementing: durable state machine, retry policies with exponential backoff, history-based replay, signal/query primitives, scheduling, worker registration protocol — all things Temporal does well. On a 12-week solo project, this is months of work with no novel value above Temporal.

## Decision

Use **Temporal Go SDK** as the underlying execution engine. HarnessFlow's value sits *on top of* Temporal as an AI-native YAML DSL, eval framework, observability layer, and CI/CD integration. The compiler at `apps/api/internal/workflow/compiler.go` translates the workflow YAML to a deterministic Temporal `Workflow` function at runtime.

Workers (`apps/worker`) register as Temporal workers using the Python SDK. The Go orchestrator never talks to workers directly — both sides talk to the Temporal cluster.

## Consequences

- **Enables:** polyglot workers (Go workflows + Python activities) with zero custom wire protocol; battle-tested durability and retries; an upstream-supported way to do approval gates (signals) and scheduling (cron workflows).
- **Forecloses:** a fully self-contained "one-binary HarnessFlow" — users always need Temporal running. We provide it via docker-compose (`temporalio/auto-setup`) and Helm (upstream Temporal chart) so this is a documentation problem, not a UX problem.
- **Operational:** workflows must be deterministic. `time.Now()`, RNG, direct I/O, and Go map iteration are forbidden inside workflow code. CI lints with `temporalio/workflowcheck`. The compiler enforces this by-construction.
- **Recruiter signal:** Temporal is on the target-recruiter list; using it correctly with a YAML-compiler abstraction is a strong signal of senior-level workflow-engine fluency.

## Alternatives considered

- **Custom orchestrator in Go (e.g., goquery-style state machine over Postgres).** Rejected: massive scope, no upside.
- **Cadence (Temporal's predecessor).** Rejected: Temporal is the active project.
- **Apache Airflow.** Rejected: batch-oriented, not designed for sub-second LLM activities.
- **Prefect.** Rejected: Python-only worker side; we want the Go signal.
- **Bare Kubernetes Jobs.** Rejected: no durability, no retry semantics, no signals.
