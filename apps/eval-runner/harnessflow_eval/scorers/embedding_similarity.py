"""embedding_similarity scorer — cosine similarity between the expected answer
and the output, using ChromaDB's default all-MiniLM-L6-v2 embedding (offline,
deterministic, same model the retriever uses). Cosine is clamped to [0, 1]."""

from __future__ import annotations

import asyncio
import math
from typing import Any

from harnessflow_eval.types import Case, RunOutcome


class EmbeddingSimilarity:
    name = "embedding_similarity"

    def __init__(self) -> None:
        # Lazily constructed on first use so importing the module is cheap and
        # offline. chromadb's embedding function is untyped, hence Any.
        self._embed: Any = None

    def _embedder(self) -> Any:
        if self._embed is None:
            from chromadb.utils import embedding_functions

            self._embed = embedding_functions.DefaultEmbeddingFunction()
        return self._embed

    async def score(self, case: Case, outcome: RunOutcome) -> float:
        if not case.expected or not outcome.output:
            return 0.0
        return await asyncio.to_thread(self._cosine, case.expected, outcome.output)

    def _cosine(self, a_text: str, b_text: str) -> float:
        a, b = self._embedder()([a_text, b_text])
        dot = sum(x * y for x, y in zip(a, b, strict=True))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return float(max(0.0, min(1.0, dot / (na * nb))))
