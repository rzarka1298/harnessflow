# ADR-0009: Durable local coding projects

Status: Accepted (2026-10-10)

## Decision

HarnessFlow now targets local developers who submit a PRD and receive a verified
software branch. Keep the existing YAML workflow platform compatible and add a
separate ProjectService and HarnessFlowProjectRun Temporal workflow. This supersedes
the old roadmap's AWS-first release priority and ADR-0008's YAML-only restriction
for this new capability. The legacy workflow optimizer remains a separate idea.

Go owns the API and durable scheduler. Python executes one checkpointed project
phase per activity. Postgres holds requirements, tasks, control revisions, snapshots
and verification evidence; local artifacts and Git worktrees hold code and transcripts.
Codex CLI is the first coding adapter. GSD Core organizes development phases and
context; it does not replace the runtime's state machine or completion predicate.

## Completion and recovery

Completion requires every frozen acceptance command to pass at the exact delivered
commit and an independent read-only review to find no material gaps. A model's
completion message is not sufficient. Time/attempt exhaustion and missing access
remain resumable. Defaults: 30 coding attempts, four active hours, three repeated
failures without progress. The original developer checkout is preserved.

One repository writer is enforced by a database uniqueness constraint and an OS
file lock inherited by a process supervisor. The supervisor kills descendants on
worker death or deadline. Control requests have revisions so a stale attempt cannot
consume a newer request. Temporal retries infrastructure failures; logical blockers
become explicit run states. Long workflow histories continue as new.

## Trust and compatibility

The first release is for trusted local repositories on macOS/Linux. Loopback bind,
Host validation and restricted browser origins guard the unauthenticated local API.
Codex's native sandbox confines code/check execution; worktrees alone are not a
security boundary. Remote service access, tenancy, automatic merge/deployment and
cloud provisioning are outside this release. PR publication is an explicit run option.
For v1 it requires a GitHub.com `origin` with matching fetch/push repository identity
and a saved base commit equal to that origin's current default-branch tip; otherwise
the verified local branch remains available and publication blocks rather than
guessing a target.

Existing YAML workflows remain available; mock LLM output requires an explicit
demo setting. Coding projects always use the real adapter, except injected test fixtures.
Token usage is reported when available; unknown monetary cost is shown as unknown.
