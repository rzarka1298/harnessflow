# HarnessFlow

**GitHub Actions + Temporal + Datadog for AI agents.**

HarnessFlow is an open-source AI workflow orchestration, observability, CI/CD, and evaluation platform for AI-native applications and autonomous agent systems.

> **Status:** under active development (Phase 4 complete, through week 11 of 14).
> Tags: [`v0.1.0-thin-slice`](https://github.com/rzarka1298/harnessflow/releases)
> (end-to-end runtime, week 4) and
> [`v0.5.0-cicd`](https://github.com/rzarka1298/harnessflow/releases) (eval
> framework + CI eval-gate, week 8). Since then: dashboard run-replay +
> cost/score analytics (week 9), a Helm chart verified on a local kind cluster
> (week 10), and Terraform for AWS EKS/RDS/ElastiCache/S3 (`plan`-validated)
> plus a Redpanda event firehose to Parquet-on-S3 (week 11). The 14-week plan
> is in [`Project-Documentation/ROADMAP.md`](./Project-Documentation/ROADMAP.md);
> resume any session by reading
> [`Project-Documentation/STATUS.md`](./Project-Documentation/STATUS.md) first.

## What it does

HarnessFlow lets you author AI workflows in declarative YAML, run them on a durable, observable, polyglot runtime, and gate releases on automated evals — the same engineering rigor that web services have, brought to LLM-driven workflows.

- **Orchestration:** YAML → Temporal-compiled deterministic workflows. Branching, retries, fallback, approval gates, scheduled execution.
- **Workers:** Polyglot — Go orchestrator drives Python workers via Temporal. LLM, retrieval, tool-call, and verifier activities.
- **Observability:** OpenTelemetry-native, with first-class support for the OTel GenAI semantic conventions. Single trace ID spans `api → workflow → activity → llm call`.
- **Self-healing:** Declarative model-fallback graphs (e.g., OpenAI → Anthropic on rate-limit). Approval gates via Temporal signals.
- **Evaluation:** Custom eval framework — exact-match, LLM-as-judge, embedding-similarity, latency, cost. Eval-gated PRs that block regressions in CI (GitHub Actions posts a Δ-vs-baseline comment and fails on per-scorer regression).
- **Dashboard:** Next.js + React Flow DAG (animated per-step status on in-progress runs), run-replay timeline scrubber, and cost/score analytics.
- **Event firehose:** workflow lifecycle events → Redpanda topic → consumer → date-partitioned Parquet on S3 for analytics (best-effort, never on the workflow's critical path).
- **Production-ready infra:** Helm chart (first-party Postgres/Redis, post-install DB-migration hook, worker HPA on Temporal task-queue depth) verified on kind; Terraform for AWS EKS/RDS/ElastiCache/S3 with IRSA.

## Quickstart

```bash
git clone https://github.com/rzarka1298/harnessflow
cd harnessflow
cp .env.example .env  # optional: set OPENAI_API_KEY / ANTHROPIC_API_KEY
                      # (omit to run on the deterministic Mock provider)
make up               # docker-compose: postgres, temporal(+ui), redis,
                      # otel-collector, jaeger, prometheus, grafana, minio, redpanda
make migrate-up       # apply Postgres migrations
make demo             # ChromaDB seed + Go API + Python worker +
                      # research-assistant workflow end-to-end, with deep-links
                      # to the dashboard run page and the Jaeger trace
```

UIs once `make up`: Temporal `:8233`, Jaeger `:16686`, Prometheus `:9090`,
Grafana `:3000`, MinIO `:9001`, Redpanda console `:8085`. The dashboard runs
separately with `pnpm --dir apps/dashboard dev` — Next picks `:3001` when
Grafana already holds `:3000`. Run the eval suite with
`uv run --directory apps/eval-runner harnessflow-eval --workflow-id <id>`, and
drain the event firehose to Parquet with `make events-consume`.

## Architecture

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the diagram and component map. High level:

```
Next.js dashboard ──┐
                    ├─► Connect-Go API (apps/api) ──► Temporal cluster
Public Connect API ─┘                                    │
                                                         ▼
                                            Python workers (apps/worker)
                                                         │
                                          OpenAI / Anthropic / ChromaDB
                            (all instrumented with OTel → Jaeger + Prometheus + Grafana)

  workers also emit lifecycle events ─► Redpanda topic ─► apps/event-consumer ─► Parquet on S3
```

## Repo layout

| Path | What |
| --- | --- |
| `apps/api` | Go orchestrator (Connect-Go + Temporal Go SDK + sqlc) |
| `apps/worker` | Python Temporal worker (activities, LLMClient, event emitter) |
| `apps/dashboard` | Next.js 16 dashboard |
| `apps/eval-runner` | Python eval framework + CI eval-gate |
| `apps/event-consumer` | Python firehose consumer (Redpanda → Parquet on S3) |
| `apps/policy-learner` | (Week 13, planned) Contextual-bandit retry policy learner |
| `apps/workflow-optimizer` | (Week 14, planned) Autonomous YAML mutation agent |
| `packages/sdk` | `.proto` files (source of truth) + JSON Schema for workflow YAML |
| `packages/examples/workflows` | Example workflow YAMLs |
| `infrastructure/{otel,prometheus,grafana,postgres}` | Observability + DB configs |
| `infrastructure/helm/harnessflow` | Helm chart (kind-verified) |
| `infrastructure/kind` | Local kind cluster config |
| `infrastructure/terraform/envs/demo` | AWS EKS/RDS/ElastiCache/S3 (`plan`-validated) |
| `.github/workflows` | CI, incl. the eval-gate |
| `Project-Documentation` | Internal dev journal — STATUS, ROADMAP, ADRs |

## Decisions

Every non-trivial decision is captured as an ADR. See [`Project-Documentation/decisions/INDEX.md`](./Project-Documentation/decisions/INDEX.md).

## License

Apache 2.0 — see [`LICENSE`](./LICENSE).
