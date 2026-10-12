"""Existing ticket operations."""

from __future__ import annotations

from datetime import date

PRIORITIES = {"low", "medium", "high"}


def validate_due(value: str | None) -> str | None:
    if value is not None:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("due date must be a valid YYYY-MM-DD date") from exc
    return value


def add(records: list[dict], title: str, priority: str, due: str | None, tags: list[str]) -> dict:
    if not title.strip():
        raise ValueError("title cannot be empty")
    if priority not in PRIORITIES:
        raise ValueError("priority must be low, medium or high")
    validate_due(due)
    ticket = {
        "id": max((int(row["id"]) for row in records), default=0) + 1,
        "title": title.strip(),
        "status": "open",
        "priority": priority,
        "due": due,
        "tags": list(tags),
    }
    records.append(ticket)
    return ticket


def close(records: list[dict], ticket_id: int) -> dict:
    for ticket in records:
        if ticket["id"] == ticket_id:
            if ticket["status"] == "closed":
                raise ValueError(f"ticket {ticket_id} is already closed")
            ticket["status"] = "closed"
            return ticket
    raise ValueError(f"ticket {ticket_id} does not exist")


def listed(records: list[dict], status: str | None = None) -> list[dict]:
    return [row for row in records if status is None or row["status"] == status]
