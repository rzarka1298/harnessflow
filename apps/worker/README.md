# apps/worker

HarnessFlow Python worker. Registers against the Temporal cluster and executes
activities: `llm_call`, `retrieve`, `tool_call`, `verify`.

Managed with [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync              # install deps into .venv
uv run harnessflow-worker   # run the worker
uv run ruff check .  # lint
uv run mypy .        # type-check
uv run pytest        # tests
```

See `Project-Documentation/workers/overview.md` for the design.
