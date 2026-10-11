# ADR-0010: CLI and independent judge for local coding projects

Status: Proposed (Codex path validated on feature branch; live Anthropic call pending)

## Context

The PRD coding harness is the primary product, while the YAML workflow platform is
kept as a maintained foundation and demo. A file-based CLI and repo-local agent
skills provide a direct path into durable project runs. Completion needs both
repeatable command evidence and an independent semantic review of PRD coverage.

## Decision

Install the local Python CLI with `uv tool install --editable apps/cli`. Use
`harnessflow run <prd-file> --repo <repository>` to submit a PRD file to the local
API, and use its status/control commands for existing runs. Repo-local Codex and
Claude Code skills route requests through this CLI; they do not orchestrate coding
themselves.

Run an explicit read-only judge after acceptance commands and independent review.
When `ANTHROPIC_API_KEY` is configured and the diff fits the 200,000-character
request bound, use Anthropic; otherwise use a separate read-only Codex attempt
that can inspect the full repository. The recorded verdict names the provider, so
this fallback is visible rather than an independent-provider claim. The Anthropic
request contains the PRD, frozen plan, actual
diff, acceptance evidence, and independent review findings. Users must treat those
materials as data sent to the configured external provider.
The Anthropic request polls durable controls and heartbeats throughout the call.

The frozen deterministic acceptance commands remain mandatory and unchanged by
judge provider or output. Completion requires the commands to pass at the delivered
commit and the judge to pass every requirement without findings.

## Consequences

Developers can start and manage durable runs from a PRD file or supported local
agent skill. Anthropic offers a distinct review context when configured; fallback
remains available with authenticated Codex. The provider call adds external data
transfer and model usage when Anthropic is configured. A judge pass supplements
command evidence and is not a correctness guarantee.

The CLI and Codex fallback were exercised end to end with an empty and a three-task
repository fixture. The Anthropic path still needs a live credentialed validation;
tests currently mock its response. The maintained YAML workflow demo continues to
use its existing setup.

## Alternatives considered

- Keep intake dashboard-only: leaves shell and agent-skill use cases without a direct
  interface.
- Treat passing commands as the only completion gate: misses qualitative PRD gaps.
- Make Anthropic mandatory: prevents operation when no Anthropic key is available.
- Let model judgment replace command checks: weakens deterministic verification.
