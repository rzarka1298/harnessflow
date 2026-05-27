# HarnessFlow

**GitHub Actions + Temporal + Datadog for AI agents.**

HarnessFlow is an open-source AI workflow orchestration, observability, CI/CD, and evaluation platform for AI-native applications and autonomous agent systems.

> **Status:** under active development. Tag [`v0.1.0-thin-slice`](https://github.com/rzarka1298/harnessflow/releases) ships the end-to-end runtime (week 4). Through week 7: approval gates, model fallback, failure analysis, OTel-native metrics + provisioned Grafana, and an in-house eval framework with persisted results. The 14-week plan is in [`Project-Documentation/ROADMAP.md`](./Project-Documentation/ROADMAP.md); resume any session by reading [`Project-Documentation/STATUS.md`](./Project-Documentation/STATUS.md) first.

## What it does

HarnessFlow lets you author AI workflows in declarative YAML, run them on a durable, observable, polyglot runtime, and gate releases on automated evals — the same engineering rigor that web services have, brought to LLM-driven workflows.

- **Orchestration:** YAML → Temporal-compiled deterministic workflows. Branching, retries, fallback, approval gates, scheduled execution.
- **Workers:** Polyglot — Go orchestrator drives Python workers via Temporal. LLM, retrieval, tool-call, and verifier activities.
- **Observability:** OpenTelemetry-native, with first-class support for the OTel GenAI semantic conventions. Single trace ID spans `api → workflow → activity → llm call`.
- **Self-healing:** Declarative model-fallback graphs (e.g., OpenAI → Anthropic on rate-limit). Approval gates via Temporal signals.
- **Evaluation:** Custom eval framework — exact-match, LLM-as-judge, embedding-similarity, latency, cost. Eval-gated PRs that block regressions in CI.
- **Dashboard:** Next.js + React Flow DAG viewer, live run status, run replay, cost analytics.
- **Production-ready infra:** Helm chart with HPA keyed on Temporal task-queue depth; Terraform for AWS EKS.

## Quickstart

```bash
git clone https://github.com/rzarka1298/harnessflow
cd harnessflow
cp .env.example .env  # optional: set OPENAI_API_KEY / ANTHROPIC_API_KEY
                      # (omit to run on the deterministic Mock provider)
make up               # docker-compose: postgres, temporal(+ui), redis,
                      # otel-collector, jaeger, prometheus, grafana, minio
make migrate-up       # apply Postgres migrations
make demo             # ChromaDB seed + Go API + Python worker +
                      # research-assistant workflow end-to-end, with deep-links
                      # to the dashboard run page and the Jaeger trace
```

UIs once `make up`: dashboard `:3000` (run `pnpm --dir apps/dashboard dev`),
Temporal `:8233`, Jaeger `:16686`, Prometheus `:9090`, Grafana `:3000` (when
running standalone). Run the eval suite with
`uv run --directory apps/eval-runner harnessflow-eval --workflow-id <id>`.

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
```

## Repo layout

| Path | What |
| --- | --- |
| `apps/api` | Go orchestrator (Connect-Go + Temporal Go SDK + sqlc) |
| `apps/worker` | Python Temporal worker (activities, LLMClient) |
| `apps/dashboard` | Next.js 16 dashboard |
| `apps/eval-runner` | Python eval framework |
| `apps/policy-learner` | (Week 13, planned) Contextual-bandit retry policy learner |
| `apps/workflow-optimizer` | (Week 14, planned) Autonomous YAML mutation agent |
| `packages/sdk` | `.proto` files (source of truth) + JSON Schema for workflow YAML |
| `packages/examples/workflows` | Example workflow YAMLs |
| `infrastructure/{otel,prometheus,grafana,postgres}` | Observability + DB configs (live) |
| `infrastructure/{terraform,helm,kubernetes}` | (Weeks 10–12, planned) Deploy artifacts |
| `docs` | Public docs |
| `Project-Documentation` | Internal dev journal — STATUS, ROADMAP, ADRs |

## Decisions

Every non-trivial decision is captured as an ADR. See [`Project-Documentation/decisions/INDEX.md`](./Project-Documentation/decisions/INDEX.md).

## License

Apache 2.0 — see [`LICENSE`](./LICENSE).
