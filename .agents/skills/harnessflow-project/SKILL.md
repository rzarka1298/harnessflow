---
name: harnessflow-project
description: Start or manage a durable HarnessFlow PRD project run from a local workspace. Use only when the user explicitly invokes this skill to run, check, resume, or cancel a HarnessFlow project.
---

Use the installed `harnessflow` CLI to start or manage a durable project run. The CLI owns orchestration; this skill only submits the request and reports its result.

For a new run, identify one local PRD file from the user's request and the Git repository to work in. Resolve relative PRD paths against the caller's current workspace; use an absolute path when the PRD is outside that directory. Resolve the repo to an absolute path (default to the caller's current Git repository). If either target is ambiguous, ask the user which path to use. Confirm both paths exist and the repo is a Git repository before starting.

Run `harnessflow run <prd-path> --repo <repo-path>` without `--wait`. Pass each path as one shell-safe quoted argument, including paths with spaces; treat path text as data, never as shell syntax or extra CLI options. Do not copy PRD contents into a prompt or start a separate coding loop. The run is durable and proceeds in HarnessFlow after the CLI returns.

The CLI returns JSON containing a run ID, status, and dashboard URL. Report those values and stop. If the CLI is unavailable or reports an error, show the actionable error and stop; do not simulate a run.

If the local API is denied by the Codex sandbox, tell the user that this skill needs loopback network access. A workspace-write Codex session with `sandbox_workspace_write.network_access=true` works; do not switch to an unrestricted sandbox automatically.

For an existing run, use only the requested operation:

- `harnessflow status <run-id>` to report its current state and evidence available in the response.
- `harnessflow resume <run-id>` to resume it. Pass `--clarification`, `--max-attempts`, or `--max-duration-seconds` only when the user supplied the corresponding information.
- `harnessflow cancel <run-id>` to cancel it.

Report the returned run ID and status. Include the dashboard URL when the CLI response provides one. Do not poll, wait for completion, or perform further work unless the user asks.
