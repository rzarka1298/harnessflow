# Orchestration — Overview

**Location:** `apps/api/` (Go).

**Responsibility:** Accept workflow YAML, validate against JSON Schema, persist to Postgres, and compile YAML into deterministic Temporal Workflow functions. Expose the Connect-Go API the dashboard and external clients consume.

## Current state (2026-05-19) — end of Week 2

`apps/api` is wired end-to-end: HTTP → Connect handlers → Postgres + Temporal client → Workflow + stub activities → OTel-traced through the whole path.

Layout:
- `cmd/api/main.go` — OTel → Postgres → Temporal+worker → Connect HTTP, with cross-channel graceful shutdown.
- `internal/config/` — env loader (API_PORT, DATABASE_URL, TEMPORAL_*, OTEL_EXPORTER_OTLP_ENDPOINT_GRPC).
- `internal/server/` — `http.ServeMux` (Chi was swapped out — Connect's owned URL prefixes don't survive Chi `Mount`'s path rewrite), slog request log, `/healthz`+`/readyz`, WorkflowService + RunService Connect handlers.
- `internal/store/` — sqlc-generated bindings + a hand-written `pool.go` pgx-pool helper.
- `internal/workflow/` — DSL parser (Kahn topo sort + cross-field validation), `HarnessFlowWorkflow` Temporal function (interprets the parsed IR), Week-2 stub activities, `NewWorker` registration.
- `internal/temporal/` — `client.Dial` wrapper with the OTel tracing interceptor.
- `internal/otel/` — OTLP/gRPC tracer + W3C propagator, shutdown hook.
- `migrations/` — 0001_init (workflows, workflow_runs, workflow_steps).

**Compiler model.** One generic Temporal workflow function interprets the IR at runtime; we do not generate Go code per user workflow. Determinism is preserved by passing a pre-computed topological order from the parser; the workflow never iterates the `Steps` map directly.

**OTel correlation works end-to-end.** A single inbound Connect RPC's trace ID covers the Temporal client `StartWorkflow`, the `RunWorkflow:HarnessFlowWorkflow` execution span, and each activity's `StartActivity`/`RunActivity` pair — verified in Jaeger (16 spans / trace). This is the work Week 5 had budgeted to "verify"; it lands here because the Temporal Go SDK's `contrib/opentelemetry` interceptor + Connect's `otelconnect` `WithTrustRemote` interoperate cleanly.

**SDK contracts (Week 1 Day 4–5):** proto files in `packages/sdk/proto/harnessflow/{workflow,run,eval}/v1/` define `WorkflowService`, `RunService`, `EvalService`. The workflow YAML DSL is defined by `packages/sdk/schema/workflow.schema.json` + `packages/workflow-dsl/SPEC.md`. `make proto` generates committed Go (Connect-Go), Python, and TypeScript clients into `packages/sdk/gen/`. The generated Go is its own module, joined to `apps/api` via the repo-root `go.work`.

**Approval gates (Week 6).** A step with `requires_approval: true` pauses the workflow: `runSteps` records run status `waiting_approval`, then blocks on `workflow.GetSignalChannel(ctx, "approve").Receive(...)`. The API releases it via `RunService.ApproveRun(run_id)`, which looks up the run's `temporal_workflow_id` and calls `SignalWorkflow(..., "approve", ApprovalSignal{...})`. On signal the run flips back to `running` and proceeds. Demoed by `packages/examples/workflows/approval-demo.yaml` and the dashboard's Approve button on a paused run.

**Self-healing.** Model fallback is handled in the worker's `LLMClient` (declared `fallback_on_rate_limit` / `fallback_on_5xx` graph, Week 3). Per-step retries map to a Temporal `RetryPolicy` in `activityOptionsFor` (`retry_policy.max_attempts`).

## Key files (planned)

| File | What |
| --- | --- |
| `apps/api/cmd/api/main.go` | Entrypoint — wires config, db, temporal client, server |
| `apps/api/internal/server/` | Connect handlers (one file per service) |
| `apps/api/internal/workflow/parser.go` | YAML → IR |
| `apps/api/internal/workflow/compiler.go` | IR → Temporal `Workflow` function |
| `apps/api/internal/temporal/client.go` | Temporal client + worker registration |
| `apps/api/internal/store/` | sqlc-generated queries |
| `apps/api/internal/otel/` | Tracer + meter providers, slog OTel bridge |
| `apps/api/internal/config/` | koanf config loader |
| `apps/api/migrations/` | SQL migrations via golang-migrate |
| `apps/api/sqlc.yaml` | sqlc config |

## YAML DSL (current surface)

> The full spec lives in `packages/workflow-dsl/SPEC.md`. Pinned shape as of v0.1:

```yaml
name: research-assistant
version: 1
description: Plans, retrieves, executes, verifies.

steps:
  planner:
    type: llm_call
    model: gpt-4o
    fallback_on_rate_limit: claude-sonnet-4-6
    prompt: |
      ...
  retriever:
    type: retrieve
    source: vector-db
    after: [planner]
  executor:
    type: tool_call
    tools: [github, terminal]
    after: [retriever]
  verifier:
    type: verify
    retries: 3
    after: [executor]

deployment:
  requires_eval_pass:
    min_score: 0.85
```

## Compiler invariants

- The YAML is parsed to an IR before becoming a Temporal Workflow. The IR is what gets persisted to the `workflows` table — never the raw YAML alone (we need to detect schema drift).
- Temporal workflow code MUST be deterministic. `time.Now()`, random sources, and direct I/O are forbidden inside the compiled workflow function. `temporalio/workflowcheck` runs in CI.
- Branching, retries, and approval gates are expressed via Temporal primitives:
  - Branches: conditional `workflow.ExecuteActivity` calls based on prior activity results.
  - Retries: Temporal `RetryPolicy` on the activity, parameterized from YAML.
  - Approval gates: `workflow.GetSignalChannel("approve").Receive(ctx, &v)`.

## Related ADRs

- [ADR-0001](../decisions/0001-use-temporal-not-custom-orchestrator.md) — why Temporal not custom
- [ADR-0002](../decisions/0002-connect-go-not-grpc.md) — why Connect-Go not raw gRPC

## TODO as we go

- [ ] Document the YAML→IR mapping table once parser exists
- [ ] Capture the determinism gotchas we hit during week 2
- [ ] Decide ID scheme for `workflow_runs.id` (ULID? UUID v7?)
