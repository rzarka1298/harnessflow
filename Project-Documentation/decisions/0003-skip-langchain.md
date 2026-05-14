# ADR-0003: No LangChain — build a thin in-house LLMClient

Date: 2026-05-14
Status: Accepted

## Context

The Python workers need to call OpenAI and Anthropic from inside Temporal activities. The default "do what everyone else does" choice is LangChain (or LangGraph). LangChain promises provider-agnostic abstractions, prompt templating, tool routing, memory, and more.

In practice, LangChain's abstractions have well-known issues for production AI infra work:
- Frequent breaking API changes
- Hidden behavior (retries, prompt mutations) that complicate OTel instrumentation
- A heavy import graph that slows worker startup
- Negative perception at the target-recruiter companies (Anthropic and OpenAI engineering teams have publicly expressed skepticism of high-level orchestrator libs)

## Decision

**No LangChain anywhere in the project.** Use the official `openai` and `anthropic` Python SDKs directly. Build a single, deliberately small `LLMClient` (`apps/worker/harnessflow_worker/llm/client.py`, target ~200 lines) that:

1. Maps model name → provider (string-prefix routing, no plugin system).
2. Walks a declared fallback graph from the YAML (`fallback_on_rate_limit`, `fallback_on_5xx`).
3. Emits OpenTelemetry spans with [`gen_ai.*`](./0005-otel-genai-semconv.md) attributes.
4. Computes $-cost from a small in-repo price table.
5. Enforces per-run budget cap (raises non-retryable on exceed).

## Consequences

- **Enables:** low-level control over retries, observability, cost accounting, and prompt construction. Worker startup stays fast. We can adopt new SDK features the same day the providers ship them.
- **Forecloses:** the LangChain ecosystem of prebuilt tools/chains. Acceptable: most are either trivial to reimplement or not what we want.
- **Operational:** when a new provider is added (e.g., Google), it's a new file in `llm/` plus a routing rule — no abstraction tax.
- **Recruiter signal:** "We rejected LangChain because we wanted control over the OTel + cost + fallback layer" is a strong, defensible position at Anthropic, OpenAI, and Temporal interviews.

## Alternatives considered

- **LangChain / LangGraph.** Rejected — see context.
- **LiteLLM.** Rejected: gives us only the routing layer; we'd still need our own fallback graph, OTel, and cost accounting. The 200-line LLMClient is comparable in volume and clearer in intent.
- **Instructor.** Used selectively for structured output (the week-14 mutation agent), not as a generic LLM wrapper.
