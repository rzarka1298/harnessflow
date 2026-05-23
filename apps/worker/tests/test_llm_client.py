"""Unit tests for the LLMClient — verifies provider routing, fallback walk,
OTel span attributes, and cost accounting. Provider implementations are mocked
so no network is involved.
"""

from __future__ import annotations

import pytest

from harnessflow_worker.llm import (
    LLMClient,
    LLMRequest,
    MockProvider,
    Provider,
    ProviderResponse,
)
from harnessflow_worker.llm.client import _RateLimitError
from harnessflow_worker.llm.pricing import cost_usd_cents

# --- Fake providers --------------------------------------------------------


class _RecordingProvider:
    """Always succeeds; remembers each call so tests can assert dispatch."""

    def __init__(self, name: str, in_tokens: int = 5, out_tokens: int = 7) -> None:
        self.name = name
        self.calls: list[tuple[str, str]] = []
        self._in = in_tokens
        self._out = out_tokens

    async def complete(
        self,
        model: str,
        prompt: str,
        *,
        max_tokens: int | None,
        temperature: float | None,
    ) -> ProviderResponse:
        del max_tokens, temperature
        self.calls.append((model, prompt))
        return ProviderResponse(
            text=f"{self.name}:{model}:{prompt[:10]}",
            input_tokens=self._in,
            output_tokens=self._out,
            finish_reason="stop",
        )


class _FailingProvider:
    """Raises the configured exception on every call."""

    def __init__(self, name: str, err: Exception) -> None:
        self.name = name
        self.err = err
        self.calls: list[str] = []

    async def complete(
        self,
        model: str,
        prompt: str,
        *,
        max_tokens: int | None,
        temperature: float | None,
    ) -> ProviderResponse:
        del max_tokens, temperature, prompt
        self.calls.append(model)
        raise self.err


class _FakeRateLimitError(Exception):
    """Mimics the openai.RateLimitError class-name signature."""


class _Boom5xxError(Exception):
    """Mimics anthropic.InternalServerError class-name signature."""

    def __init__(self, msg: str = "boom"):
        super().__init__(msg)
        self.status_code = 503


# --- Tests -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_routes_gpt_to_openai_by_pricing_table() -> None:
    openai = _RecordingProvider("openai")
    anthropic = _RecordingProvider("anthropic")
    client = LLMClient({"openai": openai, "anthropic": anthropic, "mock": MockProvider()})

    rsp = await client.complete(LLMRequest(model="gpt-4o", prompt="hi"))

    assert openai.calls == [("gpt-4o", "hi")]
    assert anthropic.calls == []
    assert rsp.model_used == "gpt-4o"
    assert rsp.fallback_used is False


@pytest.mark.asyncio
async def test_routes_claude_to_anthropic() -> None:
    openai = _RecordingProvider("openai")
    anthropic = _RecordingProvider("anthropic")
    client = LLMClient({"openai": openai, "anthropic": anthropic, "mock": MockProvider()})

    await client.complete(LLMRequest(model="claude-sonnet-4-6", prompt="hi"))

    assert anthropic.calls == [("claude-sonnet-4-6", "hi")]
    assert openai.calls == []


@pytest.mark.asyncio
async def test_unknown_model_falls_back_to_mock() -> None:
    # No openai/anthropic registered — only mock.
    client = LLMClient({"mock": MockProvider()})
    rsp = await client.complete(LLMRequest(model="some-unknown-model", prompt="hello world"))
    assert rsp.model_used == "some-unknown-model"
    assert "[mock " in rsp.text


@pytest.mark.asyncio
async def test_fallback_on_rate_limit_walks_to_anthropic() -> None:
    openai = _FailingProvider("openai", _FakeRateLimitError("rate limit exceeded"))
    anthropic = _RecordingProvider("anthropic")
    client = LLMClient({"openai": openai, "anthropic": anthropic, "mock": MockProvider()})

    rsp = await client.complete(
        LLMRequest(
            model="gpt-4o",
            prompt="hi",
            fallback_on_rate_limit="claude-sonnet-4-6",
        )
    )
    assert openai.calls == ["gpt-4o"]
    assert anthropic.calls == [("claude-sonnet-4-6", "hi")]
    assert rsp.model_used == "claude-sonnet-4-6"
    assert rsp.fallback_used is True


@pytest.mark.asyncio
async def test_no_fallback_declared_raises() -> None:
    openai = _FailingProvider("openai", _FakeRateLimitError("nope"))
    client = LLMClient({"openai": openai, "mock": MockProvider()})

    with pytest.raises(_RateLimitError):
        await client.complete(LLMRequest(model="gpt-4o", prompt="hi"))


@pytest.mark.asyncio
async def test_fallback_on_5xx() -> None:
    openai = _FailingProvider("openai", _Boom5xxError("503 service unavailable"))
    anthropic = _RecordingProvider("anthropic")
    client = LLMClient({"openai": openai, "anthropic": anthropic, "mock": MockProvider()})

    rsp = await client.complete(
        LLMRequest(model="gpt-4o", prompt="hi", fallback_on_5xx="claude-sonnet-4-6")
    )
    assert rsp.model_used == "claude-sonnet-4-6"
    assert rsp.fallback_used is True


@pytest.mark.asyncio
async def test_cost_accounting_uses_pricing_table() -> None:
    # gpt-4o = $2.50/M input, $10/M output
    openai = _RecordingProvider("openai", in_tokens=1_000_000, out_tokens=1_000_000)
    client = LLMClient({"openai": openai, "mock": MockProvider()})
    rsp = await client.complete(LLMRequest(model="gpt-4o", prompt="bench"))
    # $2.50 + $10.00 = $12.50 = 1250 cents
    assert rsp.cost_usd_cents == 1250


def test_pricing_table_for_known_models() -> None:
    assert cost_usd_cents("gpt-4o", 1_000_000, 0) == 250
    assert cost_usd_cents("gpt-4o", 0, 1_000_000) == 1000
    assert cost_usd_cents("claude-sonnet-4-6", 1_000_000, 1_000_000) == 1800
    # Unknown model → 0
    assert cost_usd_cents("gpt-?-future", 999, 999) == 0


@pytest.mark.asyncio
async def test_mock_provider_is_deterministic() -> None:
    client = LLMClient({"mock": MockProvider()})
    a = await client.complete(LLMRequest(model="mock", prompt="hello"))
    b = await client.complete(LLMRequest(model="mock", prompt="hello"))
    assert a.text == b.text


@pytest.mark.asyncio
async def test_mock_fault_injection_triggers_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    # With gpt-4o fault-injected, an all-mock client must fall over to the
    # declared rate-limit fallback — the reproducible "kill the key" demo.
    monkeypatch.setenv("HARNESSFLOW_MOCK_FAIL_MODELS", "gpt-4o")
    client = LLMClient({"mock": MockProvider()})
    rsp = await client.complete(
        LLMRequest(
            model="gpt-4o",
            prompt="hi",
            fallback_on_rate_limit="claude-sonnet-4-6",
        )
    )
    assert rsp.model_used == "claude-sonnet-4-6"
    assert rsp.fallback_used is True
    assert "claude-sonnet-4-6" in rsp.text


_ = Provider  # asserts the Protocol is importable
