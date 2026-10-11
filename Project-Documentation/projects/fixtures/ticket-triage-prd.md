# WorkQueue due-ticket triage

Extend the existing standard-library Python WorkQueue project. This is an
established local CLI with separate storage, service, formatting, CSV import,
and tests. Preserve its JSON format and the behavior of `add`, `list`, `close`,
and `import-csv`. Do not replace the application or erase existing tickets.

Add this command:

```sh
python3 -m workqueue --file tickets.json triage --as-of 2026-06-01 [--tag ops] [--format text|json]
```

`--as-of` is required and must be a strict, valid `YYYY-MM-DD` calendar date.
Reject invalid dates with a readable nonzero CLI error. Include only open
tickets whose valid due date is on or before that date (inclusive); older
tickets without a due date are valid but not due. `--tag` filters by an exact
tag, not a substring or case-insensitive match. Omit it to include every tag.

Sort eligible tickets by priority (`high`, then `medium`, then `low`), followed
by due date ascending and numeric ID ascending. Text output (the default) is
one line per ticket in this exact form:

```text
#2 [high] 2026-05-30 Patch server (ops,security)
Total: 1
```

The parenthesized tags keep their stored order; show `-` when there are none.
An empty selection prints only `Total: 0`. JSON output must be one object with
keys `as_of`, `count`, and `tickets`. Each ticket object must have `id`, `title`,
`priority`, `due`, and `tags`, in the same sorted order as text. No other keys
are required. JSON output for an empty selection has an empty `tickets` array.
Repeated runs must produce identical output. Triage must not create or modify
the ticket file, including on invalid input.

Put filtering and ordering in a dedicated `workqueue/triage.py` module, wired
through the existing CLI. Add standard-library unit and subprocess tests with
actual JSON files covering mixed priorities and due dates, equal-priority ties,
closed and undated tickets, exact tags, both output formats, empty/missing
files, invalid dates, non-mutation, and compatibility with existing commands.
Update README with usage and examples. No third-party dependencies, network
access, UI, publication, or deployment.
