# Real-Codex release acceptance

Run on 2026-10-10 against the local Go API, Temporal, Postgres, Python worker and
Codex CLI 0.159.2. `scripts/project-smoke.py` created the fixtures through the
public ProjectService, waited for durable completion, checked untouched original
checkouts, and independently executed behavior in the generated branches. The
smoke runs did not publish or merge anything.

| Fixture | Run | Delivered commit | Frozen checks | External behavior |
| --- | --- | --- | --- | --- |
| Empty `git init`, unborn HEAD | `c07c8da3-b6f0-4f69-b4b9-a89f5c39cdd2` | `2566e27163df7f3b9538b2089ffcbbc958e4317f` | 5 passing at HEAD | 10 `unittest` cases passed |
| Existing repo with uncommitted personal note | `71659e53-289b-405c-891a-3eb75dc7be09` | `21e74032ee76050e8db770a38f1c483ef78f7021` | 3 passing at HEAD | 5 `unittest` cases passed |

Each snapshot reports `completed`, a passing independent review, and five
implementation/repair attempts. The first fixture kept its original HEAD unborn;
the second kept its original commit and uncommitted `personal-notes.txt`. The
worktrees and JSON responses are retained locally under `HARNESSFLOW_DATA_DIR`
and the smoke script's printed temporary fixture paths. They are not committed:
run transcripts can contain PRD, code and model output.

These are intentionally small release fixtures, not a guarantee that any PRD can
be fully implemented. The sessions also exercised blocked/resumed paths while
integration issues were fixed. A fresh run need not have the same attempts or
model-generated plan. See [overview](overview.md) for limits and trust boundaries.
