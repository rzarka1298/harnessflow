# Inventory report CLI

Build a small Python 3 standard-library project from this empty Git repository.

The package must expose `parse_rows(lines)`, `summarize(records)`, and
`render_report(records)` from `inventory.py`. Input rows are CSV with columns
`name,quantity,unit_price`; the first row is a header. Reject malformed rows,
negative quantities, and negative prices with a clear `ValueError`. Use decimal
arithmetic for money, not binary floating-point arithmetic.

`summarize` returns total quantity and total inventory value. `render_report`
lists items in case-insensitive alphabetical order with quantities, prices,
line values, and a final total formatted to two decimal places. Equal names
must retain input order.

Provide `python3 -m inventory INPUT.csv` as a CLI that prints the report to
stdout and exits nonzero with a readable error on invalid input. Add
standard-library `unittest` tests covering parsing, invalid input, arithmetic,
ordering, and the CLI. Include a README with run/test commands and a Python
cache `.gitignore`. Do not use third-party packages, network access, a UI,
deployment, or publication.

Acceptance must run behavioral assertions, including a CLI subprocess check
and a decimal arithmetic edge case (`0.10 + 0.20 == 0.30`).
