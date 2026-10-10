# HarnessFlow Architecture

> Current product: local PRD-to-verified-branch runs (ADR-0009). The legacy YAML
> platform remains available; its original architecture is documented below.

## Project-run architecture

```text
Project dashboard → loopback Connect API → Postgres projects / project_runs
                              ↓                   ↑ state + versioned controls
                     Temporal project workflow → Python project_tick
                                                       ↓ repository lock
                                                 isolated Git worktree
                                                       ↓
                  plan → independent plan review → implement → checks → review
                                                      ↑         │        │
                                                      └─ repair ┘────────┘
                                                                    ↓
                                                   verified branch + evidence
```

Temporal schedules recoverable units, not one indefinitely running agent. A project
snapshot stores phases, task progress, attempts, limits, checks, reviews and artifacts.
Postgres controls are authoritative; Temporal signals wake waiting workflows.
Database uniqueness plus a host file lock prevent concurrent writers to a repository.
The subprocess watchdog retains that lock while stopping children after worker death.

Each Codex invocation gets fresh context assembled from durable state. Planning and
review use a read-only sandbox; coding uses workspace-write with network disabled by
default. Frozen acceptance argv execute directly through Codex's native sandbox.
Completion requires every task, passing evidence for the current commit, a clean
worktree, and independent review. Optional PR publication is explicit; no auto-merge.

The default deployment is one trusted local host, not a security boundary for
untrusted users/repositories. See [project runtime details](Project-Documentation/projects/overview.md).

## Legacy YAML platform summary

A user (or a CI job) submits a workflow YAML to the **Go orchestrator** (`apps/api`). The orchestrator validates the YAML against the JSON Schema in `packages/sdk/schema/`, persists workflow metadata to Postgres via sqlc, and (when a run is requested) compiles the workflow into a deterministic Temporal Workflow function that executes against a Temporal cluster. **Python workers** (`apps/worker`) register against the same Temporal cluster and implement the activity types (`llm_call`, `retrieve`, `tool_call`, `verify`). Activities call OpenAI/Anthropic via a thin in-house `LLMClient` and ChromaDB for retrieval. All Go and Python code is instrumented with **OpenTelemetry** — a single trace ID flows from the inbound Connect RPC through Temporal and into the LLM API call, viewable in Jaeger. Metrics flow to Prometheus + Grafana. The **Next.js dashboard** (`apps/dashboard`) calls the same Connect services the Go server exposes, using the same `.proto`-generated types via Connect-ES. Workers also emit run/step **lifecycle events** to a Redpanda topic, which `apps/event-consumer` drains to date-partitioned Parquet on S3 for analytics — a best-effort path off the workflow's critical line (Postgres remains the source of truth).

## Components

| Component | Tech | Responsibility |
| --- | --- | --- |
| API / Orchestrator | Go + Connect-Go + Chi + Temporal Go SDK + sqlc + pgx/v5 | Public API, YAML parsing/compilation, Temporal client, Postgres persistence |
| Workers | Python + Temporal Python SDK + Pydantic v2 | Execute activities — LLM, retrieve, tool, verify |
| Dashboard | Next.js 16 + TanStack Query + Connect-ES + React Flow | Workflow mgmt UI, run inspection, animated DAG, run-replay, analytics |
| Eval Runner | Python | Runs eval datasets against workflows, scores, persists results; powers the CI eval-gate |
| Event Consumer | Python (aiokafka + pyarrow + boto3) | Drains the workflow-events topic to Parquet on S3 |
| Policy Learner (week 13) | Python | Contextual-bandit retry policy learning |
| Workflow Optimizer (week 14) | Python | LLM-driven YAML mutation, opens PRs |
| Temporal | self-hosted, Postgres-backed | Durable execution, retries, signals, scheduling |
| Postgres 16 | docker / RDS | App state + Temporal persistence (separate DB) |
| Redis | docker / ElastiCache | Pub/sub for live dashboard updates, rate limits |
| Redpanda | docker / managed | Kafka-API event-firehose substrate (one topic: `harnessflow.workflow.events`) |
| OTel Collector | docker | Receive OTLP, fan out to Jaeger/Prom |
| Jaeger | docker | Trace storage + UI |
| Prometheus + Grafana | docker | Metrics + dashboards |
| ChromaDB | embedded in worker | Vector retrieval for demo workflow |
| MinIO / S3 | docker / AWS | Artifact storage + event-firehose Parquet sink |

## Data flow (request lifecycle)

1. Client → `POST /workflows/:id/run` (Connect RPC).
2. Go orchestrator validates schema, writes a `workflow_runs` row, generates a trace, and starts a Temporal workflow with the workflow YAML as input.
3. Temporal schedules activities onto the worker task queue.
4. Python worker picks up an activity, runs LLM/retrieval/tool code, emits OTel spans with `gen_ai.*` attributes.
5. Activity result returns to Temporal → workflow advances → next activity scheduled.
6. On completion, the workflow writes a final `workflow_runs` status update. The dashboard, polling via TanStack Query, reflects the change.

## Data flow (event firehose, ADR-0004)

Parallel to the request lifecycle, best-effort and off the critical path:

1. As activities run, the worker emits `run.*` / `step.*` events (keyed by run_id) to the Redpanda topic `harnessflow.workflow.events`. A producer error is logged and dropped — it never fails the workflow.
2. `apps/event-consumer` polls the topic, batches events, and writes one Parquet object per batch to `s3://<bucket>/workflow-events/dt=YYYY-MM-DD/…` (MinIO locally, Terraform-managed bucket + IRSA on EKS). At-least-once: it writes the object, *then* commits offsets.

## What this doc is NOT

- A tutorial — see the Quickstart in the repo-root [`README.md`](./README.md).
- A decisions log — see `Project-Documentation/decisions/`.
- A roadmap — see `Project-Documentation/ROADMAP.md`.
