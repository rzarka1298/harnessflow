"""Scorer protocol."""

from __future__ import annotations

from typing import Protocol

from harnessflow_eval.types import Case, RunOutcome


class Scorer(Protocol):
    """A quality scorer: (Case, RunOutcome) -> score in [0.0, 1.0]."""

    name: str

    async def score(self, case: Case, outcome: RunOutcome) -> float: ...
