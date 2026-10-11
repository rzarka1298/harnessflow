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

## Judge and CLI follow-up (2026-10-10)

The updated local stack ran an explicit requirement-level Codex judge after
read-only review and frozen command checks. No Anthropic key was configured;
the independent-provider path was validated with a mocked API response only.

| Fixture | Entry point / run | Delivered commit | Evidence and external check |
| --- | --- | --- | --- |
| Empty greeting project | `scripts/project-smoke.py --kind new` / `8d737edf-e7f0-46b1-8366-e500d7c31088` | `eec28591445e3839aba4de687fe7dd5b0cb1ec56` | Four checks passed at HEAD; judge passed all four requirements; five unittest cases and smoke assertions passed. |
| Three-task inventory PRD | `harnessflow run Project-Documentation/projects/fixtures/inventory-prd.md` / `fcd68133-d769-4e59-a026-7cbd826d8640` | `f6fc7030648992ef46606e14c10ebd788471040b` | Four checks passed at HEAD after one repair; judge passed all six requirements; ten unittest cases and separate Decimal/order assertions passed. |

The CLI returned a dashboard URL immediately, and `harnessflow status` reported
the final judge provider and commit. The inventory run had three dependent tasks,
four coding attempts, and a repair cycle. Both original checkouts retained an
unborn HEAD and no files; the generated branches stayed in isolated worktrees.
The run snapshots and model transcripts remain local rather than being committed.
The Codex skill was invoked from a different workspace and successfully reported
the completed run when loopback network access was enabled in its sandbox. A
read-only Codex sandbox denied loopback access. On 2026-10-11, the installed
Claude Code skill was invoked from the separate inventory workspace using Haiku
and reported the greeting run's completed status, branch, commit, judge provider,
and dashboard URL. The first invocation's $0.15 budget was too low for the host
context; a $0.50 cap completed successfully. No repository files were changed.

Draft [PR #3](https://github.com/rzarka1298/harnessflow/pull/3) passed its GitHub
checks and GitGuardian check on 2026-10-11. It remains unmerged.
