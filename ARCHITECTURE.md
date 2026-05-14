# HarnessFlow Architecture

> **Status:** stub. Will be expanded with a committed Excalidraw diagram in week 12. This file is updated alongside any architectural change.

## One-paragraph summary

A user (or a CI job) submits a workflow YAML to the **Go orchestrator** (`apps/api`). The orchestrator validates the YAML against the JSON Schema in `packages/sdk/schema/`, persists workflow metadata to Postgres via sqlc, and (when a run is requested) compiles the workflow into a deterministic Temporal Workflow function that executes against a Temporal cluster. **Python workers** (`apps/worker`) register against the same Temporal cluster and implement the activity types (`llm_call`, `retrieve`, `tool_call`, `verify`). Activities call OpenAI/Anthropic via a thin in-house `LLMClient` and ChromaDB for retrieval. All Go and Python code is instrumented with **OpenTelemetry** — a single trace ID flows from the inbound Connect RPC through Temporal and into the LLM API call, viewable in Jaeger. Metrics flow to Prometheus + Grafana. The **Next.js dashboard** (`apps/dashboard`) calls the same Connect services the Go server exposes, using the same `.proto`-generated types via Connect-ES.

## Components

| Component | Tech | Responsibility |
| --- | --- | --- |
| API / Orchestrator | Go + Connect-Go + Chi + Temporal Go SDK + sqlc + pgx/v5 | Public API, YAML parsing/compilation, Temporal client, Postgres persistence |
| Workers | Python + Temporal Python SDK + Pydantic v2 | Execute activities — LLM, retrieve, tool, verify |
| Dashboard | Next.js 15 + TanStack Query + Connect-ES + React Flow | Workflow management UI, run inspection, eval comparison |
| Eval Runner | Python | Runs eval datasets against workflows, scores, persists results |
| Policy Learner (week 13) | Python | Contextual-bandit retry policy learning |
| Workflow Optimizer (week 14) | Python | LLM-driven YAML mutation, opens PRs |
| Temporal | self-hosted, Postgres-backed | Durable execution, retries, signals, scheduling |
| Postgres 16 | docker / RDS | App state + Temporal persistence (separate DB) |
| Redis | docker / ElastiCache | Pub/sub for live dashboard updates, rate limits |
| OTel Collector | docker | Receive OTLP, fan out to Jaeger/Prom |
| Jaeger | docker | Trace storage + UI |
| Prometheus + Grafana | docker | Metrics + dashboards |
| ChromaDB | embedded in worker | Vector retrieval for demo workflow |
| MinIO / S3 | docker / AWS | Workflow artifact storage |

## Data flow (request lifecycle)

1. Client → `POST /workflows/:id/run` (Connect RPC).
2. Go orchestrator validates schema, writes a `workflow_runs` row, generates a trace, and starts a Temporal workflow with the workflow YAML as input.
3. Temporal schedules activities onto the worker task queue.
4. Python worker picks up an activity, runs LLM/retrieval/tool code, emits OTel spans with `gen_ai.*` attributes.
5. Activity result returns to Temporal → workflow advances → next activity scheduled.
6. On completion, the workflow writes a final `workflow_runs` status update. The dashboard, polling via TanStack Query, reflects the change.

## What this doc is NOT

- A tutorial — see `docs/quickstart.md`.
- A decisions log — see `Project-Documentation/decisions/`.
- A roadmap — see `Project-Documentation/ROADMAP.md`.
