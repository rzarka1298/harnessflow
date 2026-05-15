# Orchestration — Overview

**Location:** `apps/api/` (Go).

**Responsibility:** Accept workflow YAML, validate against JSON Schema, persist to Postgres, and compile YAML into deterministic Temporal Workflow functions. Expose the Connect-Go API the dashboard and external clients consume.

## Current state (2026-05-15)

Week 1 skeleton only. `apps/api` is a Go module (`github.com/rzarka1298/harnessflow/apps/api`) with:
- `cmd/api/main.go` — entrypoint with graceful shutdown
- `internal/config/` — env-based config loader
- `internal/server/` — Chi router, slog request logging, `/healthz` + `/readyz`
- `internal/{workflow,temporal,store,otel}/` — empty dirs, populated Week 2
- `Dockerfile` — multi-stage distroless build

No Temporal, Postgres, or Connect services yet — those land Week 2.

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
