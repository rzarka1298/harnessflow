"""Dataset loading. Datasets are JSONL files of Case records under
harnessflow_eval/datasets/<name>.jsonl."""

from __future__ import annotations

from pathlib import Path

from harnessflow_eval.types import Case

_DATASETS_DIR = Path(__file__).parent / "datasets"


def dataset_path(name: str) -> Path:
    """Resolve a dataset name (or a literal path) to a file."""
    p = Path(name)
    if p.exists():
        return p
    return _DATASETS_DIR / f"{name}.jsonl"


def load_cases(name: str) -> list[Case]:
    path = dataset_path(name)
    if not path.exists():
        raise FileNotFoundError(f"dataset not found: {path}")
    cases: list[Case] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                cases.append(Case.model_validate_json(line))
    return cases
