"""Existing WorkQueue command-line interface."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import store
from .csv_import import import_file
from .formats import ticket_list
from .service import add, close, listed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local ticket queue")
    parser.add_argument("--file", type=Path, default=Path(".workqueue.json"))
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("add", help="add a ticket")
    create.add_argument("title")
    create.add_argument("--priority", choices=["low", "medium", "high"], default="medium")
    create.add_argument("--due")
    create.add_argument("--tag", action="append", default=[])
    listing = commands.add_parser("list", help="list tickets")
    listing.add_argument("--status", choices=["open", "closed"])
    closing = commands.add_parser("close", help="close a ticket")
    closing.add_argument("id", type=int)
    importing = commands.add_parser("import-csv", help="import a CSV batch")
    importing.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        records = store.load(args.file)
        if args.command == "add":
            ticket = add(records, args.title, args.priority, args.due, args.tag)
            store.save(args.file, records)
            print(f"Added #{ticket['id']}")
        elif args.command == "list":
            print(ticket_list(listed(records, args.status)))
        elif args.command == "close":
            ticket = close(records, args.id)
            store.save(args.file, records)
            print(f"Closed #{ticket['id']}")
        else:
            count = import_file(records, args.path)
            store.save(args.file, records)
            print(f"Imported {count} tickets")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0
