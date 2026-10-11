# Local project runs

## Product boundary

The primary product is a trusted developer's local PRD-to-verified-branch harness.
The maintained YAML workflow platform remains available as a foundation and demo.
For coding runs, authenticate Codex CLI and use an existing Git repository (an
empty `git init` is sufficient). `make dev` starts Postgres/Temporal in Docker and
API/worker/dashboard on the host. Project runs are separate from YAML workflows;
the dashboard begins at `/projects`.

The optional CLI is installed from the repository with
`uv tool install --editable apps/cli`. Run
`harnessflow run ./PRD.md --repo /absolute/path/to/repository` to submit the PRD
file to the local API and receive a run ID and dashboard URL. `harnessflow status`,
`resume`, `pause`, and `cancel` manage an existing run; `status --full` includes
the complete snapshot. Repo-local Codex and Claude Code skills are in
`.agents/skills/harnessflow-project/` and `.claude/skills/harnessflow-project/`.
They submit through the CLI; they do not replace the durable project runtime.
Run `make install-skills` to copy them into your user skill directories for use
from other repositories; existing differing files are not overwritten.
Codex sandboxed sessions need loopback network access to reach the local API.

## Durable execution

`ProjectService` persists intake and a run before starting a deterministic Temporal
workflow. A reconciliation loop retries interrupted starts and pending controls.
Each `project_tick` advances one phase: prepare, plan, plan review, implementation,
verification, independent review, judge, repair, or delivery. Temporal continues as new
after a bounded history. Waiting runs consume no coding attempts or active time.

Postgres owns snapshots and versioned pause/resume/cancel requests. Signals are only
wake-up hints. A control is cleared only if its version still matches. Resume adds
clarification and optionally extends limits; it does not silently start a new run.
Default limits are 30 implementation/repair attempts and four active hours.
Repeated no-progress work or the same failed checks three times becomes a blocker.

## Repository and subprocess ownership

Runs branch from committed HEAD into a separate `harnessflow/<run-id>` worktree.
Uncommitted changes in the original checkout are deliberately excluded and retained.
Empty repositories use a synthetic base commit without changing their original HEAD.
The worktree, attempt transcripts and evidence remain available after completion.
Use the dashboard's workspace path to inspect results; no automatic cleanup deletes work.

A database partial unique index reserves the repository even while a run is paused,
blocked or exhausted. A host file lock prevents retried activities writing concurrently.
Supervised subprocesses inherit that lock; a watchdog terminates child process groups
when their worker disappears or a deadline expires. Recovery checkpoints partial
edits and retries the unfinished task; it never promotes interrupted work to done.

## Completion and trust

A planner links requirements to tasks and executable argv checks. A separate review
accepts that plan before checks are frozen. Coding attempts cannot redefine them.
The supervisor records real exit codes, output and commit IDs; failed checks trigger
repair. A fresh read-only review and an explicit independent judge inspect the
implementation against the PRD. If `ANTHROPIC_API_KEY` is set, the judge uses
Anthropic; otherwise it uses a separate read-only Codex attempt. The Anthropic judge
receives the PRD, frozen plan, actual diff, acceptance evidence, and independent
review findings, so those materials leave the local machine for that provider.
Delivery still requires the deterministic frozen command checks to pass on the
delivered commit, a clean worktree, and a passing judge. Model judgment supplements
the command gate; it does not replace it. Delivery rechecks status and evidence
against HEAD before declaring completion.

This is evidence-backed automation, not proof that an arbitrary PRD has no defects.
LLM-generated acceptance criteria and reviews can miss requirements. Human review of
important changes remains appropriate. Run only trusted repositories/PRDs: local
host filesystem reads, dependency code, hooks and project commands are not a hosted
multi-tenant security boundary. The supported process contract excludes intentionally
daemonized/malicious tools that escape their supervised process group.

Codex uses fresh ephemeral sessions with read-only or workspace-write sandboxing;
approval policy is `never`, which denies forbidden requests instead of prompting.
This is not `--yolo`. Network access for coding is opt-in via
`HARNESSFLOW_PROJECT_NETWORK=true`; deterministic acceptance remains network-disabled.
Missing dependencies/access produce a resumable blocker. PR publication requires
the run's explicit option plus working Git/GitHub authentication. It is limited to
GitHub.com `origin` with matching fetch/push repositories and a saved base commit
equal to the current remote default-branch tip. Empty repos, nondefault branch
bases and stale remote tips stay local and block publication; the target is never
inferred from an unrelated `gh` remote. No merge or deploy.
Usage records observed token events; dollar cost is unknown, never fabricated as free.

## Verification

`make check` runs lint, tests, types and dashboard build. Worker integration tests
exercise real Git and commands with only the external coding boundary replaced.
The opt-in API persistence test requires `HARNESSFLOW_TEST_DATABASE_URL` and isolates
its schema. Browser acceptance covers intake, controls, blockers, evidence and replay.

With `make dev` running, `python3 scripts/project-smoke.py --kind new` and
`--kind existing` execute real Codex runs without publishing. They retain temporary
repositories and JSON evidence and independently execute behavioral assertions after
completion. These cost time/model usage and are deliberately not run in ordinary CI.
The completed release run and its exact commits are recorded in
[acceptance](acceptance.md).
