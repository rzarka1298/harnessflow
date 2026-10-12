"""A small persistent expense ledger, before the reporting feature is added."""

from __future__ import annotations

import argparse
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


def load_expenses(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def add_expense(path: Path, spent_on: str, category: str, amount: str) -> None:
    date.fromisoformat(spent_on)
    category = category.strip()
    if not category:
        raise ValueError("category must not be empty")
    try:
        money = Decimal(amount)
    except InvalidOperation as exc:
        raise ValueError("amount must be decimal money") from exc
    if not money.is_finite() or money <= 0 or money.as_tuple().exponent < -2:
        raise ValueError("amount must be positive money with at most two decimals")
    rows = load_expenses(path)
    rows.append({"date": spent_on, "category": category, "amount": f"{money:.2f}"})
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Store expenses in a JSON ledger")
    parser.add_argument("--file", type=Path, default=Path("expenses.json"))
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add")
    add.add_argument("date")
    add.add_argument("category")
    add.add_argument("amount")
    commands.add_parser("list")
    args = parser.parse_args()
    try:
        if args.command == "add":
            add_expense(args.file, args.date, args.category, args.amount)
        else:
            for row in load_expenses(args.file):
                print(f"{row['date']} | {row['category']} | {row['amount']}")
    except (ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
