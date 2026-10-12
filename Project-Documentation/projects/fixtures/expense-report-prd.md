# Expense category report for an existing CLI

Extend this existing Python 3 standard-library expense ledger. Keep the current
`add` and `list` commands and their stored JSON format working; do not replace the
application or erase existing expenses.

Add a `report` command to `expenses.py`, invoked as:

```sh
python3 expenses.py --file ledger.json report [--from YYYY-MM-DD] [--to YYYY-MM-DD]
```

The report must include only expenses whose dates fall in the inclusive range.
Either bound may be omitted. Reject malformed dates and a `--from` date after
`--to` with a readable nonzero CLI error. Do not modify the ledger when reporting.

Group included expenses by exact category name. Render category lines in
case-insensitive alphabetical order as `Category: 12.34`, followed by
`Total: 12.34`. Use `Decimal` arithmetic for the stored money strings, not binary
floating point. An empty selection prints only `Total: 0.00`. Keep all values at
two decimal places. The report must be deterministic on repeated runs.

Put the aggregation and rendering functions in a new `reports.py` module and wire
the CLI command to it. Add standard-library `unittest` coverage for filtering,
grouping, decimal arithmetic, empty selection, invalid ranges, and compatibility
with the existing `add` and `list` commands. Update the README with report usage.
Acceptance checks must execute behavior, including a CLI subprocess check with
an actual JSON ledger. No third-party packages, network access, UI, publication,
or deployment.
