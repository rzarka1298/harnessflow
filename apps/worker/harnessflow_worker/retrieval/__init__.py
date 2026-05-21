"""Retrieval backend for the ``retrieve`` activity.

Uses ChromaDB in embedded mode with persistent storage under
``$HARNESSFLOW_CHROMA_PATH`` (default ``./data/chroma``). The corpus is
seeded by ``scripts/seed-chroma.py`` from
``harnessflow_worker/retrieval/corpus.jsonl``; the activity opens the
collection read-only and runs a similarity query per call.
"""

from harnessflow_worker.retrieval.chroma import (
    COLLECTION_NAME,
    chroma_path,
    open_collection,
    query,
)

__all__ = ["COLLECTION_NAME", "chroma_path", "open_collection", "query"]
