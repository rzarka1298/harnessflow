"""Pydantic activity I/O types — wire-compatible with the Go API's
internal/workflow types.go (matched by JSON field names).

These are intentionally separate from the Pydantic models generated from the
JSON schema (packages/sdk/gen/python/workflow_schema.py). The generated
``Step`` describes the DSL surface; this module defines the activity contract.
Keep field names in lockstep with the Go side — they're serialized via JSON
through Temporal's data converter.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RetryPolicy(BaseModel):
    """Mirrors schema.RetryPolicy from the gen'd Go module."""

    model_config = ConfigDict(extra="ignore")

    type: str = "static"
    max_attempts: int = 3
    fallback_to_static: bool = True


class Step(BaseModel):
    """Mirrors schema.Step from the gen'd Go module.

    All step-type-specific fields are optional; the activity that handles a
    given step type validates the fields it cares about (e.g. llm_call needs
    model + prompt).
    """

    model_config = ConfigDict(extra="ignore")

    type: str
    after: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    retry_policy: RetryPolicy | None = None
    # llm_call fields
    model: str | None = None
    prompt: str | None = None
    fallback_on_rate_limit: str | None = None
    fallback_on_5xx: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    # retrieve fields
    source: str | None = None
    top_k: int = 5
    # tool_call fields
    tools: list[str] = Field(default_factory=list)
    # verify fields
    criteria: str | None = None


class ActivityResult(BaseModel):
    """Mirrors apps/api/internal/workflow/types.go ActivityResult."""

    model_config = ConfigDict(extra="ignore")

    output: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd_cents: int = 0


class ActivityInput(BaseModel):
    """Mirrors apps/api/internal/workflow/types.go ActivityInput.

    Go marshals a nil ``map`` as JSON ``null``, not ``{}``; the validator
    below coerces ``null`` to an empty dict so Pydantic accepts the wire
    shape produced by the orchestrator without any Go-side changes.
    """

    model_config = ConfigDict(extra="ignore")

    run_id: str
    step_name: str
    step: Step
    run_inputs: dict[str, str] = Field(default_factory=dict)
    prior_outputs: dict[str, ActivityResult] = Field(default_factory=dict)

    @field_validator("run_inputs", "prior_outputs", mode="before")
    @classmethod
    def _none_is_empty(cls, v: Any) -> Any:
        return {} if v is None else v
