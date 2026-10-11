#!/usr/bin/env python3
"""Install the repo's thin HarnessFlow skills for use from any workspace."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def identical(source: Path, target: Path) -> bool:
    source_files = {path.relative_to(source) for path in source.rglob("*") if path.is_file()}
    target_files = {path.relative_to(target) for path in target.rglob("*") if path.is_file()}
    return source_files == target_files and all(
        (source / relative).read_bytes() == (target / relative).read_bytes()
        for relative in source_files
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--home", type=Path, default=Path.home(), help="home directory to install into"
    )
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    locations = [
        ("Codex", ".agents/skills/harnessflow-project"),
        ("Claude Code", ".claude/skills/harnessflow-project"),
    ]
    destinations = []
    for host, location in locations:
        source = repo / location
        target = args.home.expanduser().resolve() / location
        if not source.is_dir():
            raise SystemExit(f"Missing {host} source skill: {source}")
        if target.exists() and (not target.is_dir() or not identical(source, target)):
            raise SystemExit(f"Existing {host} skill differs: {target}. Nothing was overwritten.")
        destinations.append((host, source, target))
    for host, source, target in destinations:
        if target.exists():
            print(f"{host}: already installed at {target}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
        print(f"{host}: installed at {target}")


if __name__ == "__main__":
    main()
