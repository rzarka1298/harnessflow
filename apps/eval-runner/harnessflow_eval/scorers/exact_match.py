"""exact_match scorer — 1.0 iff the output equals the expected answer
(case-insensitive, whitespace-normalized). Strict; best for closed-set answers."""

from __future__ import annotations

from harnessflow_eval.types import Case, RunOutcome


def _norm(s: str) -> str:
    return " ".join(s.split()).casefold()


class ExactMatch:
    name = "exact_match"

    async def score(self, case: Case, outcome: RunOutcome) -> float:
        if not case.expected:
            return 0.0
        return 1.0 if _norm(outcome.output) == _norm(case.expected) else 0.0
