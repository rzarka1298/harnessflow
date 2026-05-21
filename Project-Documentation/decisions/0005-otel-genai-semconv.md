# ADR-0005: Adopt OpenTelemetry GenAI semantic conventions

Date: 2026-05-14
Status: Accepted — implemented & verified Week 5 (2026-05-21)

> Implemented in `apps/worker/harnessflow_worker/llm/client.py` (GenAI span
> attributes) and `apps/worker/harnessflow_worker/metrics.py` (the
> `harnessflow_*` metric families). Verified end-to-end through the collector
> into Prometheus and the provisioned Grafana dashboard.

## Context

We need a consistent way to annotate spans and metrics for LLM calls. There are three options: ad-hoc attribute names ("model", "tokens_in", etc.), a vendor-specific convention (LangSmith, Helicone, Braintrust), or the [OpenTelemetry GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions/tree/main/docs/gen-ai), which were stabilized in 2024–2025 and are the emerging industry standard.

## Decision

**Adopt OpenTelemetry GenAI semantic conventions across both Go and Python LLM instrumentation.** Every LLM call span uses:

| Attribute | Value |
| --- | --- |
| `gen_ai.system` | `openai` / `anthropic` |
| `gen_ai.request.model` | full model ID (e.g., `gpt-4o-2024-08-06`) |
| `gen_ai.request.max_tokens` | int |
| `gen_ai.request.temperature` | float |
| `gen_ai.usage.input_tokens` | int |
| `gen_ai.usage.output_tokens` | int |
| `gen_ai.response.finish_reasons` | array |
| `gen_ai.operation.name` | `chat` / `embed` / `completion` |

Plus one custom attribute: `harnessflow.cost_usd_cents` (int) — until OTel GenAI standardizes cost.

## Consequences

- **Enables:** any OTel-compatible backend (Jaeger, Tempo, Datadog APM, Honeycomb, ClickHouse OTel exporter) can natively analyze HarnessFlow traces. Users can swap backends without changing instrumentation.
- **Forecloses:** lock-in to any specific AI-observability vendor. Acceptable — we explicitly want vendor-neutral.
- **Operational:** when the semconv spec evolves (it will), we update the attribute names in two places (`apps/api/internal/otel/genai.go`, `apps/worker/harnessflow_worker/otel/genai.py`). Both pinned to the same spec version in a comment.
- **Recruiter signal:** this is a brand-new spec; most projects use ad-hoc attributes. Using GenAI semconv correctly is an instant senior-observability signal at Datadog, Honeycomb, and Anthropic.

## Alternatives considered

- **Ad-hoc attribute names.** Rejected: works but signals 2022-era instrumentation thinking.
- **LangSmith-style attributes.** Rejected: vendor lock-in.
- **Braintrust SDK.** Rejected: same reason; we're building the observability layer, not consuming it.
