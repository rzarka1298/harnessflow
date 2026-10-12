"""Existing human-readable ticket lines."""


def ticket_line(ticket: dict) -> str:
    due = ticket.get("due") or "-"
    tags = ",".join(ticket.get("tags", [])) or "-"
    return (
        f"#{ticket['id']} [{ticket['status']}] {ticket['priority']} "
        f"{due} {ticket['title']} ({tags})"
    )


def ticket_list(tickets: list[dict]) -> str:
    if not tickets:
        return "No tickets"
    return "\n".join(ticket_line(ticket) for ticket in tickets)
