"""Quality scorers — each maps a (Case, RunOutcome) to a 0.0-1.0 score.

Latency and cost are not scorers; they're reported directly from RunOutcome.
"""

from harnessflow_eval.scorers.base import Scorer
from harnessflow_eval.scorers.embedding_similarity import EmbeddingSimilarity
from harnessflow_eval.scorers.exact_match import ExactMatch
from harnessflow_eval.scorers.llm_judge import LLMJudge

__all__ = ["EmbeddingSimilarity", "ExactMatch", "LLMJudge", "Scorer"]
