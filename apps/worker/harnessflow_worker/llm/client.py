"""HarnessFlow LLMClient — provider routing, declared fallback, OTel spans.

See ADR-0003 for why this is ~200 lines of in-house code rather than LangChain.
The class is intentionally small; resist the urge to abstract further.

Public surface (re-exported from harnessflow_worker.llm):
    LLMRequest        — what to call
    LLMResponse       — what came back
    LLMClient         — does the calling
    Provider          — Protocol for a single-shot text completion
    OpenAIProvider, AnthropicProvider, MockProvider
    build_default_client — env-driven factory used by the worker
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

import structlog
from opentelemetry import trace
from pydantic import BaseModel, Field

from harnessflow_worker.llm.pricing import (
    cost_usd_cents,
    provider_for,
)

log = structlog.get_logger()
_tracer = trace.get_tracer("harnessflow.llm")


# --- Public request / response shapes --------------------------------------


class LLMRequest(BaseModel):
    """A single completion request. Fallback fields come from the workflow YAML."""

    model: str
    prompt: str
    max_tokens: int | None = None
    temperature: float | None = None
    fallback_on_rate_limit: str | None = None
    fallback_on_5xx: str | None = None


class LLMResponse(BaseModel):
    """The completion result, with metering data persisted to workflow_steps."""

    model_used: str
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd_cents: int
    finish_reason: str
    fallback_used: bool = False


# --- Provider Protocol + concrete implementations --------------------------


@dataclass
class ProviderResponse:
    text: str
    input_tokens: int
    output_tokens: int
    finish_reason: str


class Provider(Protocol):
    """A single-shot text completion. Implementations live in this module."""

    name: str

    async def complete(  # pragma: no cover - protocol
        self,
        model: str,
        prompt: str,
        *,
        max_tokens: int | None,
        temperature: float | None,
    ) -> ProviderResponse: ...


class MockRateLimitError(Exception):
    """Raised by MockProvider for fault-injected models. The class name contains
    'RateLimit' so LLMClient._classify routes it through the rate-limit fallback,
    reproducing the 'kill the OpenAI key' demo without real credentials."""


class MockProvider:
    """Deterministic stand-in used when no provider credentials are configured.

    The pipeline (Go API → Temporal → Python activity → LLMClient → MockProvider
    → trace) still exercises end-to-end correctly; only the model output is fake.

    Fault injection: any model listed in $HARNESSFLOW_MOCK_FAIL_MODELS
    (comma-separated) raises MockRateLimitError, so a workflow that declares
    fallback_on_rate_limit visibly falls over to its backup model.
    """

    name = "mock"

    @staticmethod
    def _fail_models() -> set[str]:
        raw = os.getenv("HARNESSFLOW_MOCK_FAIL_MODELS", "")
        return {m.strip() for m in raw.split(",") if m.strip()}

    async def complete(
        self,
        model: str,
        prompt: str,
        *,
        max_tokens: int | None,
        temperature: float | None,
    ) -> ProviderResponse:
        del max_tokens, temperature
        if model in self._fail_models():
            raise MockRateLimitError(f"simulated rate limit (429) for {model}")
        text = f"[mock {model}] {prompt[:80]}"
        return ProviderResponse(
            text=text,
            # Token estimates: count whitespace words; close enough for the demo.
            input_tokens=max(1, len(prompt.split())),
            output_tokens=max(1, len(text.split())),
            finish_reason="stop",
        )


class OpenAIProvider:
    name = "openai"

    def __init__(self, client) -> None:  # type: ignore[no-untyped-def]
        self._client = client

    async def complete(
        self,
        model: str,
        prompt: str,
        *,
        max_tokens: int | None,
        temperature: float | None,
    ) -> ProviderResponse:
        kwargs: dict[str, object] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if temperature is not None:
            kwargs["temperature"] = temperature
        rsp = await self._client.chat.completions.create(**kwargs)
        choice = rsp.choices[0]
        usage = rsp.usage
        return ProviderResponse(
            text=choice.message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            finish_reason=choice.finish_reason or "stop",
        )


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, client) -> None:  # type: ignore[no-untyped-def]
        self._client = client

    async def complete(
        self,
        model: str,
        prompt: str,
        *,
        max_tokens: int | None,
        temperature: float | None,
    ) -> ProviderResponse:
        rsp = await self._client.messages.create(
            model=model,
            max_tokens=max_tokens or 1024,
            messages=[{"role": "user", "content": prompt}],
            **({"temperature": temperature} if temperature is not None else {}),
        )
        # Anthropic returns a list of content blocks; concat text blocks.
        text = "".join(block.text for block in rsp.content if block.type == "text")
        return ProviderResponse(
            text=text,
            input_tokens=rsp.usage.input_tokens,
            output_tokens=rsp.usage.output_tokens,
            finish_reason=rsp.stop_reason or "stop",
        )


# --- LLMClient -------------------------------------------------------------


class _RateLimitError(Exception):
    """Marker raised when the underlying provider reports a rate limit."""


class _ServerError(Exception):
    """Marker raised for provider 5xx errors that the fallback graph cares about."""


class LLMClient:
    """Calls a Provider with the right model, walking the YAML-declared fallback graph."""

    def __init__(self, providers: dict[str, Provider]) -> None:
        if not providers:
            raise ValueError("LLMClient: at least one provider required")
        self._providers = providers

    async def complete(self, req: LLMRequest) -> LLMResponse:
        attempts = [(req.model, "primary")]
        if req.fallback_on_rate_limit:
            attempts.append((req.fallback_on_rate_limit, "fallback_on_rate_limit"))
        if req.fallback_on_5xx:
            attempts.append((req.fallback_on_5xx, "fallback_on_5xx"))

        last_err: Exception | None = None
        for idx, (model, reason) in enumerate(attempts):
            provider = self._provider_for(model)
            if provider is None:
                last_err = ValueError(f"no provider registered for model {model!r}")
                continue
            try:
                return await self._call(
                    provider, model, req, fallback=idx > 0, attempt_reason=reason
                )
            except _RateLimitError as e:
                last_err = e
                if not req.fallback_on_rate_limit or idx > 0:
                    raise
                log.warning(
                    "rate_limit, falling back",
                    model=model,
                    fallback=req.fallback_on_rate_limit,
                )
                continue
            except _ServerError as e:
                last_err = e
                if not req.fallback_on_5xx:
                    raise
                # The fallback_on_5xx slot is at index 1 OR 2 depending on whether
                # rate-limit fallback exists; only try it once.
                if reason == "fallback_on_5xx":
                    raise
                log.warning("5xx, falling back", model=model, fallback=req.fallback_on_5xx)
                continue
        # Exhausted the fallback chain.
        raise last_err if last_err else RuntimeError("LLMClient: no attempts ran")

    def _provider_for(self, model: str) -> Provider | None:
        name = provider_for(model) or "mock"
        return self._providers.get(name) or self._providers.get("mock")

    async def _call(
        self,
        provider: Provider,
        model: str,
        req: LLMRequest,
        *,
        fallback: bool,
        attempt_reason: str,
    ) -> LLMResponse:
        with _tracer.start_as_current_span(
            f"llm.{provider.name}.complete",
            attributes={
                # OTel GenAI semantic conventions — keep these exact.
                "gen_ai.system": provider.name,
                "gen_ai.request.model": model,
                "gen_ai.operation.name": "chat",
                "harnessflow.attempt_reason": attempt_reason,
            },
        ) as span:
            if req.max_tokens is not None:
                span.set_attribute("gen_ai.request.max_tokens", req.max_tokens)
            if req.temperature is not None:
                span.set_attribute("gen_ai.request.temperature", req.temperature)
            try:
                rsp = await provider.complete(
                    model,
                    req.prompt,
                    max_tokens=req.max_tokens,
                    temperature=req.temperature,
                )
            except Exception as e:
                span.record_exception(e)
                raise self._classify(e) from e

            cents = cost_usd_cents(model, rsp.input_tokens, rsp.output_tokens)
            span.set_attribute("gen_ai.usage.input_tokens", rsp.input_tokens)
            span.set_attribute("gen_ai.usage.output_tokens", rsp.output_tokens)
            span.set_attribute("gen_ai.response.finish_reasons", [rsp.finish_reason])
            span.set_attribute("gen_ai.response.model", model)
            span.set_attribute("harnessflow.cost_usd_cents", cents)

            return LLMResponse(
                model_used=model,
                text=rsp.text,
                input_tokens=rsp.input_tokens,
                output_tokens=rsp.output_tokens,
                cost_usd_cents=cents,
                finish_reason=rsp.finish_reason,
                fallback_used=fallback,
            )

    # Classify provider-specific errors into the small enum the fallback graph
    # understands. Keeps provider plumbing isolated to one place.
    @staticmethod
    def _classify(err: Exception) -> Exception:
        msg = str(err).lower()
        cls_name = type(err).__name__
        if "ratelimit" in cls_name.lower() or "429" in msg or ("rate" in msg and "limit" in msg):
            return _RateLimitError(str(err))
        status = getattr(err, "status_code", None) or getattr(err, "status", None)
        if isinstance(status, int) and 500 <= status < 600:
            return _ServerError(f"{status}: {err}")
        if "internalserver" in cls_name.lower() or "serviceunavailable" in cls_name.lower():
            return _ServerError(str(err))
        return err


# --- Factory ---------------------------------------------------------------


def build_default_client() -> LLMClient:
    """Build an LLMClient from environment variables.

    OPENAI_API_KEY        — enables OpenAI models
    ANTHROPIC_API_KEY     — enables Anthropic models

    If neither is set, MockProvider handles everything and the pipeline still
    runs end-to-end — useful for CI and for first-time local setup.
    """
    providers: dict[str, Provider] = {"mock": MockProvider()}

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        from openai import AsyncOpenAI

        providers["openai"] = OpenAIProvider(AsyncOpenAI(api_key=openai_key))
        log.info("llm provider configured", provider="openai")

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        from anthropic import AsyncAnthropic

        providers["anthropic"] = AnthropicProvider(AsyncAnthropic(api_key=anthropic_key))
        log.info("llm provider configured", provider="anthropic")

    if len(providers) == 1:
        log.warning("no LLM keys set — using MockProvider for all models")

    return LLMClient(providers=providers)


# Silence unused-import linters when only re-exporting.
_ = Field
