"""LLM pricing table — USD per million tokens.

Prices are point-in-time and must be reviewed when providers update theirs.
Keep this file small and inspectable; don't auto-pull from an external feed
without an ADR, since pricing drift will silently change recorded costs.

Verified-as-of: 2026-05-20 (rzarka1298). Update the date when refreshing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPrice:
    """Per-million-token prices in USD, plus the provider key."""

    provider: str
    input_per_million_usd: float
    output_per_million_usd: float


# Keep keys lowercase; LLMClient matches case-insensitively. Use the canonical
# model id, not the alias (e.g. "gpt-4o-2024-08-06", not "gpt-4o-latest"), so
# costs are reproducible.
PRICES: dict[str, ModelPrice] = {
    # OpenAI
    "gpt-4o": ModelPrice("openai", 2.50, 10.00),
    "gpt-4o-mini": ModelPrice("openai", 0.15, 0.60),
    # Anthropic
    "claude-haiku-4-5": ModelPrice("anthropic", 0.80, 4.00),
    "claude-sonnet-4-6": ModelPrice("anthropic", 3.00, 15.00),
    "claude-opus-4-7": ModelPrice("anthropic", 15.00, 75.00),
    # Local — free at the price layer; ops costs are out of scope here.
    "mock": ModelPrice("mock", 0.0, 0.0),
}


def cost_usd_cents(model: str, input_tokens: int, output_tokens: int) -> int:
    """Compute LLM call cost in integer USD cents.

    Unknown models are billed at 0 with a debug-friendly assumption: better to
    record 0 than to refuse the call. Logs/spans should make the unknown-model
    case visible.
    """
    price = PRICES.get(model.lower())
    if price is None:
        return 0
    total_usd = (
        input_tokens / 1_000_000 * price.input_per_million_usd
        + output_tokens / 1_000_000 * price.output_per_million_usd
    )
    return round(total_usd * 100)


def provider_for(model: str) -> str | None:
    """Look up the provider that serves a given model id, or None."""
    price = PRICES.get(model.lower())
    return price.provider if price else None
