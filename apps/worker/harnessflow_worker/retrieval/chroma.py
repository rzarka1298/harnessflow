"""Embedded ChromaDB retrieval — read path used by the ``retrieve`` activity.

Chroma's default embedding function (all-MiniLM-L6-v2 via ONNX) is used so
the retrieval pipeline runs without any external API call. This keeps the
demo self-contained and reproducible.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings

COLLECTION_NAME = "harnessflow-corpus"


def chroma_path() -> str:
    """Resolve the on-disk ChromaDB path."""
    return os.environ.get(
        "HARNESSFLOW_CHROMA_PATH",
        os.path.join(os.getcwd(), "data", "chroma"),
    )


def open_collection(create: bool = False) -> Collection:
    """Open (or create) the corpus collection. ``create=True`` is for the seeder."""
    client = chromadb.PersistentClient(
        path=chroma_path(),
        settings=Settings(anonymized_telemetry=False),
    )
    if create:
        return client.get_or_create_collection(name=COLLECTION_NAME)
    return client.get_collection(name=COLLECTION_NAME)


@dataclass
class Hit:
    """One retrieved document."""

    text: str
    source: str
    distance: float


def query(text: str, top_k: int = 5) -> list[Hit]:
    """Run a similarity query and return the top hits."""
    coll = open_collection()
    rsp = coll.query(query_texts=[text], n_results=top_k)
    out: list[Hit] = []
    docs = rsp.get("documents") or [[]]
    metas = rsp.get("metadatas") or [[]]
    dists = rsp.get("distances") or [[]]
    if not docs or not docs[0]:
        return out
    for doc, meta, dist in zip(docs[0], metas[0], dists[0], strict=False):
        source = str((meta or {}).get("source", "(unknown)"))
        out.append(Hit(text=doc, source=source, distance=float(dist)))
    return out
