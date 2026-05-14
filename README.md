# HarnessFlow

**GitHub Actions + Temporal + Datadog for AI agents.**

HarnessFlow is an open-source AI workflow orchestration, observability, CI/CD, and evaluation platform for AI-native applications and autonomous agent systems.

> **Status:** under active development. The 14-week plan is in [`Project-Documentation/ROADMAP.md`](./Project-Documentation/ROADMAP.md). Resume any session by reading [`Project-Documentation/STATUS.md`](./Project-Documentation/STATUS.md) first.

## What it does

HarnessFlow lets you author AI workflows in declarative YAML, run them on a durable, observable, polyglot runtime, and gate releases on automated evals — the same engineering rigor that web services have, brought to LLM-driven workflows.

- **Orchestration:** YAML → Temporal-compiled deterministic workflows. Branching, retries, fallback, approval gates, scheduled execution.
- **Workers:** Polyglot — Go orchestrator drives Python workers via Temporal. LLM, retrieval, tool-call, and verifier activities.
- **Observability:** OpenTelemetry-native, with first-class support for the OTel GenAI semantic conventions. Single trace ID spans `api → workflow → activity → llm call`.
- **Self-healing:** Declarative model-fallback graphs (e.g., OpenAI → Anthropic on rate-limit). Approval gates via Temporal signals.
- **Evaluation:** Custom eval framework — exact-match, LLM-as-judge, embedding-similarity, latency, cost. Eval-gated PRs that block regressions in CI.
- **Dashboard:** Next.js + React Flow DAG viewer, live run status, run replay, cost analytics.
- **Production-ready infra:** Helm chart with HPA keyed on Temporal task-queue depth; Terraform for AWS EKS.

## Quickstart (TODO — will be a `make demo` one-liner by week 4)

```bash
git clone https://github.com/rzarka1298/harnessflow
cd harnessflow
cp .env.example .env  # add your OPENAI_API_KEY and ANTHROPIC_API_KEY
make up               # docker-compose: postgres, temporal, redis, jaeger, prom, grafana, workers
make demo             # runs the research-assistant workflow end-to-end
```

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
| `apps/dashboard` | Next.js 15 dashboard |
| `apps/eval-runner` | Python eval framework |
| `apps/policy-learner` | (Week 13) Contextual-bandit retry policy learner |
| `apps/workflow-optimizer` | (Week 14) Autonomous YAML mutation agent |
| `packages/sdk` | `.proto` files (source of truth) + JSON Schema for workflow YAML |
| `packages/examples/workflows` | Example workflow YAMLs |
| `infrastructure/{terraform,helm,kubernetes}` | Deploy artifacts |
| `infrastructure/{otel,prometheus,grafana}` | Observability configs |
| `docs` | Public docs |
| `Project-Documentation` | Internal dev journal — STATUS, ROADMAP, ADRs |

## Decisions

Every non-trivial decision is captured as an ADR. See [`Project-Documentation/decisions/INDEX.md`](./Project-Documentation/decisions/INDEX.md).

## License

Apache 2.0 — see [`LICENSE`](./LICENSE).
