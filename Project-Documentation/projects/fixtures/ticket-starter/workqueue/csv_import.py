"""Batch import for the pre-existing CSV format."""

from __future__ import annotations

import csv
from pathlib import Path

from .service import add


def import_file(records: list[dict], path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["title", "priority", "due", "tags"]:
            raise ValueError("CSV columns must be title,priority,due,tags")
        rows = list(reader)
    for row in rows:
        add(
            records,
            row["title"],
            row["priority"],
            row["due"] or None,
            [tag for tag in row["tags"].split(";") if tag],
        )
    return len(rows)
