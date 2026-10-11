# WorkQueue

A small standard-library ticket queue for a local operations team. It stores a
JSON array of tickets. Existing teams use the command line and occasionally
import a CSV batch; the file format is deliberately simple enough to inspect.

```sh
python3 -m workqueue --file tickets.json add "Patch server" --priority high --due 2026-06-01 --tag ops
python3 -m workqueue --file tickets.json list
python3 -m workqueue --file tickets.json close 1
python3 -m workqueue --file tickets.json import-csv examples/incoming.csv
python3 -m unittest discover -s tests -v
```

Older JSON files may contain tickets without `due` or `tags`; these remain
valid. No dependency installation is needed.
