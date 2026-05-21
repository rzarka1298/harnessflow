#!/usr/bin/env python3
"""Seed the local ChromaDB corpus from
apps/worker/harnessflow_worker/retrieval/corpus.jsonl.

Idempotent: the collection is recreated each run so re-seeding is safe.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_PATH = REPO_ROOT / "apps/worker/harnessflow_worker/retrieval/corpus.jsonl"


def main() -> int:
    if not CORPUS_PATH.exists():
        print(f"corpus not found at {CORPUS_PATH}", file=sys.stderr)
        return 1

    # Import only after we know we'll proceed — keeps non-chroma installs fast.
    sys.path.insert(0, str(REPO_ROOT / "apps/worker"))
    from harnessflow_worker.retrieval.chroma import COLLECTION_NAME, chroma_path

    import chromadb
    from chromadb.config import Settings

    rows: list[dict] = []
    with CORPUS_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    if not rows:
        print("corpus is empty", file=sys.stderr)
        return 1

    path = chroma_path()
    os.makedirs(path, exist_ok=True)
    client = chromadb.PersistentClient(path=path, settings=Settings(anonymized_telemetry=False))

    # Recreate from scratch so seeding is deterministic.
    if COLLECTION_NAME in {c.name for c in client.list_collections()}:
        client.delete_collection(COLLECTION_NAME)
    coll = client.create_collection(name=COLLECTION_NAME)

    ids = [f"doc-{i:04d}" for i in range(len(rows))]
    documents = [r["text"] for r in rows]
    metadatas = [{"source": r["source"]} for r in rows]
    coll.add(ids=ids, documents=documents, metadatas=metadatas)

    print(f"seeded {len(rows)} docs into {COLLECTION_NAME} at {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
