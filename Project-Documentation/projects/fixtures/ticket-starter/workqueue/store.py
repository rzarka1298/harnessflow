"""JSON storage for local tickets."""

from __future__ import annotations

import json
from pathlib import Path


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ValueError("ticket file must contain an array of objects")
    return records


def save(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
