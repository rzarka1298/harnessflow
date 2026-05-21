# Observability — Overview

**Location:** `infrastructure/otel/`, `infrastructure/prometheus/`, `infrastructure/grafana/` (configs); instrumentation lives inside `apps/api` and `apps/worker`.

**Responsibility:** One trace ID spans every layer of a workflow run. Metrics roll up to Grafana dashboards. Logs are structured (slog in Go, `structlog`-style in Python) and flow through OTel.

## Current state (2026-05-21) — Week 5

**Traces:** a single trace spans Go API → Temporal → Python worker → LLM call (verified weeks 2–4). LLM spans carry OTel GenAI semconv attributes (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.{input,output}_tokens`, `gen_ai.response.finish_reasons`) plus `harnessflow.cost_usd_cents`.

**Metrics (Week 5):** the Python worker exports four metric families via OTel → collector → Prometheus:

| Prometheus name | Type | Labels | Emitted from |
| --- | --- | --- | --- |
| `harnessflow_workflow_runs_total` | counter | `workflow`, `status` | `record_run_status` activity (terminal only) |
| `harnessflow_workflow_duration_seconds` | histogram | `workflow` | `record_run_status` activity |
| `harnessflow_llm_tokens_total` | counter | `workflow`, `provider`, `model`, `type` | `llm_call` + `verify` activities |
| `harnessflow_llm_cost_usd_total` | counter | `workflow`, `provider`, `model` | `llm_call` + `verify` activities |

Naming note: OTel instruments omit the `_total` suffix and any `unit=` — the collector's Prometheus exporter appends `_total` to counters and would otherwise splice the unit into the name (the original `harnessflow_llm_cost_usd_USD_total` bug). Worker metric instruments are bound from the provider's own meter inside `setup_metrics`, not from the import-time global proxy.

Run-level metrics live in the worker because completion is only observable there (the Go API starts runs asynchronously). Go-side HTTP metrics are a later addition.

**Grafana:** `infrastructure/grafana/dashboards/harnessflow.json` is auto-provisioned (6 panels: total runs, total cost, runs-by-status, p50/p95 duration, tokens by model, cost by model). The Prometheus datasource has a fixed UID (`harnessflow-prometheus`) so the committed dashboard references it reproducibly.

## Topology

```
apps/api (Go, OTel SDK) ─┐
apps/worker (Python OTel)─┼─► OTel Collector (docker-compose) ─┬─► Jaeger     (traces)
apps/dashboard (Next.js) ─┘                                    ├─► Prometheus (metrics)
                                                               └─► (optional Loki for logs, post-MVP)
```

## The hardest part: trace propagation across Temporal

Temporal does NOT propagate W3C trace context across workflow/activity boundaries automatically. We use the official interceptors:

- Go: `go.temporal.io/sdk/contrib/opentelemetry`
- Python: `temporalio.contrib.opentelemetry`

**Verification (week 5, day 1–2 spike):** start a workflow → in Jaeger find the span → it must have child spans for each activity → each activity span must have a child span for the LLM call → all under the same trace ID. If any boundary breaks, file a known issue and propagate `traceparent` manually via activity inputs.

## OTel GenAI semantic conventions

Every LLM call span uses these attributes:

| Attribute | Value example |
| --- | --- |
| `gen_ai.system` | `openai` / `anthropic` |
| `gen_ai.request.model` | `gpt-4o-2024-08-06` |
| `gen_ai.request.max_tokens` | `1024` |
| `gen_ai.request.temperature` | `0.0` |
| `gen_ai.usage.input_tokens` | `1234` |
| `gen_ai.usage.output_tokens` | `567` |
| `gen_ai.response.finish_reasons` | `["stop"]` |
| `harnessflow.cost_usd_cents` | `42` (custom, not yet in semconv) |

## Prometheus metrics (planned)

| Metric | Labels |
| --- | --- |
| `harnessflow_workflow_runs_total` | `workflow`, `version`, `status` |
| `harnessflow_workflow_duration_seconds` (histogram) | `workflow`, `version` |
| `harnessflow_llm_tokens_total` | `workflow`, `step`, `provider`, `model`, `type` (input/output) |
| `harnessflow_llm_cost_usd_total` | `workflow`, `step`, `provider`, `model` |
| `harnessflow_activity_retries_total` | `workflow`, `step`, `reason` |
| `harnessflow_eval_score` (gauge) | `workflow`, `scorer` |

## Grafana dashboard

Single JSON file at `infrastructure/grafana/dashboards/harnessflow.json`, provisioned via docker-compose volume mount. Panels:

- Workflow runs by status (last 24h)
- p50/p95 workflow duration
- LLM tokens + cost by model (stacked)
- Eval scores trend per workflow
- Activity retry rate

## Related ADRs

- [ADR-0005](../decisions/0005-otel-genai-semconv.md) — committing to GenAI semconv

## TODO as we go

- [ ] Confirm OTel collector config supports both gRPC and HTTP receivers
- [ ] Decide whether to use exemplars to link metrics → traces (probably yes)
- [ ] Document the trace correlation work after the week-5 spike
