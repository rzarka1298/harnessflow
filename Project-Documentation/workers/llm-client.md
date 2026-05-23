# The LLMClient

`apps/worker/harnessflow_worker/llm/client.py` — the in-house client every LLM
activity calls. Deliberately small and explicit; no LangChain (see
[ADR-0003](../decisions/0003-skip-langchain.md)).

## Why in-house

LangChain (and similar) hide retries, prompt mutation, and provider quirks
behind abstractions that leak in production and complicate OTel instrumentation.
We want three things the wrapper layer obscures: exact control of the fallback
graph, GenAI-semconv spans we own, and per-call cost accounting. That's ~120
lines of routing/fallback logic plus thin provider shims — comparable in volume
to wiring a framework, clearer in intent.

## Shape

- `LLMRequest` — model, prompt, optional max_tokens/temperature, and the
  declared fallbacks (`fallback_on_rate_limit`, `fallback_on_5xx`).
- `LLMResponse` — `model_used`, text, input/output tokens, `cost_usd_cents`,
  `finish_reason`, `fallback_used`.
- `Provider` (Protocol) — one `complete()` method. Implementations:
  `OpenAIProvider`, `AnthropicProvider`, `MockProvider`.
- `LLMClient` — picks a provider per model, walks the fallback graph, emits
  spans + cost.
- `build_default_client()` — env factory: registers OpenAI/Anthropic when
  their keys are set, always registers Mock, and falls back to Mock-for-all
  when no keys exist (so CI and first-run local dev work offline).

## Provider routing

By model id, via the pricing table's `provider_for(model)` (`gpt-*` → openai,
`claude-*` → anthropic, `mock` → mock). Unknown models route to Mock so the
pipeline never hard-fails on a typo; the span/logs make the unknown-model case
visible.

## Fallback graph (self-healing)

`complete()` builds an ordered attempt list: `[primary, fallback_on_rate_limit?,
fallback_on_5xx?]`. On a provider error it classifies (`_classify`) into a
rate-limit or 5xx marker and advances to the matching fallback exactly once;
otherwise it re-raises. The model that actually answered is recorded as
`model_used` with `fallback_used=True`.

Reproducible demo without real keys: `MockProvider` raises a simulated rate
limit for any model in `$HARNESSFLOW_MOCK_FAIL_MODELS`, so a workflow with
`fallback_on_rate_limit` visibly fails over (see `overview.md`).

## Observability

Each attempt opens a span `llm.<provider>.complete` with OTel GenAI semantic
conventions: `gen_ai.system`, `gen_ai.request.model`, `gen_ai.request.max_tokens`,
`gen_ai.request.temperature`, `gen_ai.usage.{input,output}_tokens`,
`gen_ai.response.finish_reasons`, `gen_ai.response.model`, plus the custom
`harnessflow.cost_usd_cents`. The `llm_call`/`verify` activities additionally
emit the `harnessflow_llm_tokens_total` / `harnessflow_llm_cost_usd_total`
metrics (see [observability/overview.md](../observability/overview.md)).

## Cost accounting

`pricing.py` holds a pinned per-million-token price table (dated
`verified-as-of`). `cost_usd_cents(model, in, out)` returns integer cents;
unknown models bill 0 (and are visible in logs). Don't auto-pull prices from a
feed without an ADR — silent price drift would corrupt recorded costs.

## Deliberately NOT here

Prompt templating beyond trivial `{{inputs.x}}` / `{{steps.NAME.output}}`
substitution (done in `llm_call`), streaming, tool-use orchestration, and
memory. Each is added behind its own decision when a workflow needs it.
