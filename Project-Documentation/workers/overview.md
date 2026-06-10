# Workers — Overview

**Location:** `apps/worker/` (Python 3.12, managed by `uv`).

**Responsibility:** Long-running Python processes that register against the Temporal cluster and execute activities — the actual LLM calls, retrieval, tool execution, and verification. Workers are stateless; all durability is in Temporal.

## Current state (2026-05-22) — through Week 6

`apps/worker` is a uv-managed package. `python -m harnessflow_worker` connects to Temporal (with `pydantic_data_converter` + OTel `TracingInterceptor`), opens an asyncpg pool, builds the `LLMClient`, installs the OTel tracer + meter providers, and registers five activities.

Modules:
- `__main__.py` — bootstrap + signal-driven graceful shutdown (force_flush traces & metrics before exit).
- `config.py` — `WorkerConfig` (Temporal, DATABASE_URL, OTLP endpoint).
- `otel.py` / `metrics.py` — OTLP tracer + the four `harnessflow_*` metric families.
- `llm/` — the in-house `LLMClient` (OpenAI/Anthropic/Mock, declared fallback graph, GenAI semconv spans, pinned price table). See `llm-client.md`.
- `retrieval/` — embedded ChromaDB read path + the seeded corpus.
- `activities/` — `llm_call`, `retrieve`, `tool_call`, `verify`, `record_run_status`. `_common.with_persistence` wraps each with timing + workflow_steps persistence.
- `persistence.py` — step + run row writes.
- `types.py` — Pydantic activity I/O wire-compatible with the Go side.

`ruff` + `mypy --strict` + `pytest` (10 tests) all pass.

### Self-healing demo (Week 6)

Model fallback is in the `LLMClient`: a step's `fallback_on_rate_limit` / `fallback_on_5xx` declare backup models, and the client walks them on the matching provider error. With real keys, a 429/401 on the primary triggers it naturally. Without keys, set `HARNESSFLOW_MOCK_FAIL_MODELS=gpt-4o` on the worker — `MockProvider` then raises a simulated rate limit for `gpt-4o`, so the research-assistant workflow's `planner`/`executor` visibly fall over to `claude-sonnet-4-6` and the run still completes. This is the reproducible form of the "kill the OpenAI key mid-run" demo.

## Architecture

```
Temporal cluster ──► Python worker (apps/worker)
                          │
                          ├── activities/llm_call.py     ──► LLMClient ──► OpenAI / Anthropic
                          ├── activities/retrieve.py     ──► ChromaDB
                          ├── activities/tool_call.py    ──► whitelisted tools
                          └── activities/verify.py       ──► LLM-as-judge style
```

## Key files (planned)

| File | What |
| --- | --- |
| `harnessflow_worker/__main__.py` | Entrypoint — register activities, start worker |
| `harnessflow_worker/activities/llm_call.py` | LLM activity |
| `harnessflow_worker/activities/retrieve.py` | Vector retrieval |
| `harnessflow_worker/activities/tool_call.py` | Tool execution sandbox |
| `harnessflow_worker/activities/verify.py` | Verifier with retry loop |
| `harnessflow_worker/llm/client.py` | **The 200-line LLMClient — heart of the worker** |
| `harnessflow_worker/llm/openai_provider.py` | OpenAI shim |
| `harnessflow_worker/llm/anthropic_provider.py` | Anthropic shim |
| `harnessflow_worker/retrieval/chroma.py` | ChromaDB wrapper |
| `harnessflow_worker/otel/` | OTel setup (tracer, meter, slog-equivalent for python) |
| `harnessflow_worker/schema/` | Pydantic models codegen'd from `packages/sdk/schema/` |

## LLMClient design (the core IP)

The `LLMClient` is the project's most important worker-side piece. It is deliberately small (~200 lines) and explicit. Behaviors:

1. **Provider routing.** Map model name → provider. `gpt-4o*` → OpenAI; `claude-*` → Anthropic. No abstractions over message formats — provider-specific code stays provider-specific.
2. **Declared fallback graph.** Not a try/except. The YAML declares:
   ```yaml
   model: gpt-4o
   fallback_on_rate_limit: claude-sonnet-4-6
   fallback_on_5xx: gpt-4o-mini
   ```
   The client walks this graph in order, recording each attempt in OTel attributes.
3. **OTel GenAI semconv compliance.** Every call emits a span with `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.response.finish_reasons`.
4. **Cost accounting.** Per-call $ cost computed from a small price table; aggregated into the parent `workflow_steps.token_usage` and `workflow_steps.cost_usd_cents` columns.
5. **Budget guard.** Per-workflow-run cap from YAML (`budget_usd: 1.00`). If exceeded mid-run, raises a non-retryable activity error.

## Event firehose (producer side)

Week 11 (ADR-0004). The worker emits workflow lifecycle events to a Redpanda
(Kafka-API) topic, `harnessflow.workflow.events`, drained downstream to
Parquet on S3 by `apps/event-consumer`. The producer lives in
`harnessflow_worker/events.py`:

- **Event types:** `run.started` / `run.completed` / `run.failed` (emitted
  from `record_run_status`), and `step.completed` / `step.failed` (emitted
  from the `with_persistence` wrapper, so every DSL step is covered).
- **One flat JSON schema** (`WorkflowEvent`), keyed by `run_id` so all events
  for a run share a partition and stay ordered.
- **Best-effort + optional.** `emit` swallows and logs producer errors —
  Postgres (written synchronously in the same activities) is the source of
  truth; the firehose is a lossy-tolerant analytics stream that must never
  fail a workflow. With no brokers configured (`HARNESSFLOW_EVENTS_BROKERS`
  unset) the factory returns a `NullEmitter` and the worker behaves exactly
  as before — so `make demo` needs no Redpanda.

Verified end-to-end: one research-assistant run produced 6 events
(`run.started`, 4× `step.completed`, `run.completed`) on the topic, all on
one partition keyed by run_id.

## Related ADRs

- [ADR-0003](../decisions/0003-skip-langchain.md) — why no LangChain
- [ADR-0004](../decisions/0004-skip-kafka-for-mvp.md) — Temporal+Redis for MVP, Redpanda firehose in Week 11

## TODO as we go

- [ ] Pricing table location & how it gets updated (manual? cron pull from a price feed?)
- [ ] Whitelist of tools allowed by `tool_call` activity (start with `github_read`, `web_fetch_readonly`)
- [ ] How does `verify` activity work — same LLMClient with a fixed judge prompt? Yes, plus structured output via Anthropic tool use.
