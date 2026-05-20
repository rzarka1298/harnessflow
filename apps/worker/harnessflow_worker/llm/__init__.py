"""In-house LLM client.

The HarnessFlow ``LLMClient`` is intentionally small and explicit — ~200 lines
of Python that handles provider routing, declared model fallback, OpenTelemetry
GenAI semantic-convention spans, and per-call cost accounting. No LangChain.
See ADR-0003 for the rationale.
"""

from harnessflow_worker.llm.client import (
    LLMClient,
    LLMRequest,
    LLMResponse,
    MockProvider,
    Provider,
    ProviderResponse,
    build_default_client,
)

__all__ = [
    "LLMClient",
    "LLMRequest",
    "LLMResponse",
    "MockProvider",
    "Provider",
    "ProviderResponse",
    "build_default_client",
]
