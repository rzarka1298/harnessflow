# Deterministic multi-task project-run acceptance fixture

The worker suite now has a public-boundary fixture at
`apps/worker/tests/test_project_acceptance_fixture.py`. It drives the production
project engine through a temporary Git repository and durable-copy in-memory
store. Only the coding/review/judge model responses are deterministic fakes;
worktree preparation, task scheduling, Git checkpoints, frozen command execution,
repair routing, judge adapter wiring, and delivery remain real.

The fixture's small inventory-report PRD has three ordered tasks and three
requirement-linked behavioral checks. Its first implementation stores quantity
as text, so checks fail and route the run into repair. The repair fixes the
parser; all checks must then pass at one exact commit before independent review,
the requirement-level judge, and delivery can complete. Assertions also cover
the complete task list, four implementation/repair attempts, judge call count,
all requirement verdicts, generated report behavior, and preservation of the
original checkout.

Run it with:

```sh
uv run --project apps/worker pytest -q apps/worker/tests/test_project_acceptance_fixture.py
```

This is deterministic acceptance evidence for engine state transitions, not a
replacement for the real-Codex integration trials in
[`../projects/acceptance.md`](../projects/acceptance.md). It does not measure
model quality or provider behavior; those require separately authorized and
credentialed runs.
