# Workers — Overview

**Location:** `apps/worker/` (Python 3.12, managed by `uv`).

**Responsibility:** Long-running Python processes that register against the Temporal cluster and execute activities — the actual LLM calls, retrieval, tool execution, and verification. Workers are stateless; all durability is in Temporal.

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

## Related ADRs

- [ADR-0003](../decisions/0003-skip-langchain.md) — why no LangChain

## TODO as we go

- [ ] Pricing table location & how it gets updated (manual? cron pull from a price feed?)
- [ ] Whitelist of tools allowed by `tool_call` activity (start with `github_read`, `web_fetch_readonly`)
- [ ] How does `verify` activity work — same LLMClient with a fixed judge prompt? Yes, plus structured output via Anthropic tool use.
