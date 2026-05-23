"""Core eval types shared by the runner, scorers, and reporters."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Case(BaseModel):
    """One labelled dataset case."""

    id: str
    inputs: dict[str, str] = Field(default_factory=dict)
    # Reference answer for exact_match / embedding_similarity.
    expected: str = ""
    # Natural-language rubric for llm_judge (falls back to `expected`).
    criteria: str = ""


class RunOutcome(BaseModel):
    """What a single workflow run produced, distilled for scoring."""

    output: str
    latency_ms: int = 0
    cost_usd_cents: int = 0
    status: str = ""


class CaseResult(BaseModel):
    """Per-case scores plus the run outcome that produced them."""

    case_id: str
    scores: dict[str, float] = Field(default_factory=dict)
    outcome: RunOutcome
