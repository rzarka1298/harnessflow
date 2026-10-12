# Requirements

- PRD-01: Accept a PRD and existing or empty local Git repository.
- RUN-01: Persist plans, requirements, tasks, evidence, attempts and checkpoints.
- RUN-02: Implement, verify and repair automatically within configurable limits.
- RUN-03: Pause, cancel, clarify and resume without duplicate repository writers.
- VERIFY-01: Require complete passing evidence tied to the delivered commit.
- VERIFY-02: Detect missing checks, malformed agent output and repeated failed checks.
- DELIVER-01: Preserve the original checkout and deliver a branch, diff and report.
- DELIVER-02: Optionally publish a GitHub PR; publication failure remains resumable.
- UI-01: Provide project intake, progress, controls and downloadable evidence.
- OPS-01: One documented local start command, genuine checks and general CI.
- SKILLS-01: Install pinned GSD plus browser-testing and React guidance.
- JUDGE-01: Record explicit requirement-level, read-only semantic judge evidence
  after independent review; preserve deterministic, commit-bound completion gates.
- JUDGE-02: Prefer Anthropic when configured and within the request bound; use a
  visibly attributed read-only Codex fallback otherwise.
- CLI-01: Launch and inspect durable runs from a local PRD file through an
  installable CLI.
- SKILLS-02: Provide thin Codex and Claude Code entry-point skills that invoke
  the CLI from a user's repository without owning execution themselves.

Release acceptance: demonstrate both a new project and an existing-project feature
with real Codex, in addition to deterministic lifecycle and browser tests.
The local release proves JUDGE-01, the Codex fallback of JUDGE-02, CLI-01 and
SKILLS-02. Anthropic behavior has mocked tests, but no live credentialed run.
