# Development skills

## Repo-local product skills

The PRD coding harness is the primary product. It includes an invocation skill for
Codex at [`.agents/skills/harnessflow-project/SKILL.md`](../.agents/skills/harnessflow-project/SKILL.md)
and Claude Code at [`.claude/skills/harnessflow-project/SKILL.md`](../.claude/skills/harnessflow-project/SKILL.md).
Both route new requests and run controls through the `harnessflow` CLI; install the
CLI with `uv tool install --editable apps/cli`. The skill is a thin entry point, while
the local API and Temporal workflow own durable execution.
Run `make install-skills` to copy both skills into user-level discovery directories
for use from any workspace; the installer refuses to overwrite a different skill.

The final acceptance judge uses Anthropic when `ANTHROPIC_API_KEY` is configured and
falls back to a separate read-only Codex run otherwise. In the Anthropic path, the
service receives the PRD, frozen plan, actual diff, acceptance evidence, and
independent review findings. Those artifacts leave the local machine for Anthropic.
The judge is an additional semantic review; the frozen deterministic acceptance
commands must still pass on the delivered commit.

Installed 2026-10-10:

| Skill | Source | Use |
| --- | --- | --- |
| GSD Core 1.16.0 | [OpenGSD release manifest](https://github.com/open-gsd/gsd-core/blob/v1.16.0/package.json) | Phase planning, context artifacts, execution and verification workflows |
| webapp-testing | [Anthropic skill source](https://github.com/anthropics/skills/blob/main/skills/webapp-testing/SKILL.md) | Python Playwright browser checks, screenshots, and server lifecycle helper |
| vercel-react-best-practices | [Vercel skill source](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/SKILL.md) | Next.js fetching, rendering, and bundle performance guidance |

GSD was installed with `npx --yes @opengsd/gsd-core@1.16.0 --codex --global`.
The package integrity reported by npm was
`sha512-A3OgmNH8/M0eALNpKZp0bjP0L5puu6rne1keqdFaM+NvqybuYZ2kJOcUH+fCKu6FQBGV0fAUEUE1bs6xqRfF7Q==`.
Node 24+ and npm 10+ are required by the [release manifest](https://github.com/open-gsd/gsd-core/blob/v1.16.0/package.json).
The following counts and warnings are this session's installer observations, not
guarantees for every installation: the installer preserved 50 baseline user files,
installed 72 skills under the user's `.agents/skills`, and installed runtime assets,
agent roles and its SessionStart hook under `.codex`. It also wrote GSD defaults.
The installer reported unresolved `.claude` references in 42 assets; inspect a
workflow's resolved paths before using it. Codex context-warning hooks are unsupported.

The other two skills were installed with the Codex skill-installer helper into
`.codex/skills`. Installed skills become discoverable on the next turn/session.
Reuse the existing review, debugging and TDD skills rather than adding overlapping
frameworks. `.planning` holds portable intent/phase state; the project journal holds
implementation evidence. GSD is development tooling, not a production runtime dependency.

## Primary-source verification and recommended roles

Checked 2026-10-10 against the versioned GSD sources and the two skill owners'
current sources. The GSD README describes a phase loop of discussion, planning,
execution, verification, and shipping, with persistent context artifacts and fresh
agent contexts. This fits development of HarnessFlow and future milestone work;
installing it alone does not supply the product's durable execution engine.
[GSD 1.16.0 overview](https://github.com/open-gsd/gsd-core/blob/v1.16.0/README.md).

| HarnessFlow work | Recommended installed GSD skills | Boundary |
| --- | --- | --- |
| Understand the existing repository and old PRD | `gsd-onboard`, `gsd-map-codebase`, `gsd-ingest-docs` | Reconcile the new product intent with historical scope before planning |
| Specify and sequence implementation | `gsd-discuss-phase`, `gsd-plan-phase`, `gsd-ai-integration-phase` | Capture decisions, task plans, and AI evaluation requirements |
| Execute and verify a milestone | `gsd-execute-phase`, `gsd-code-review`, `gsd-verify-work`, `gsd-eval-review` | Review code and observable acceptance evidence; conversational UAT is not an automated completion predicate |
| Continue unattended development phases | `gsd-autonomous` | Its documented workflow still has decision/blocker gates; it is not an unconditional infinite loop |

The role mapping is our recommendation, based on the installed skill descriptions
and the [GSD command reference](https://github.com/open-gsd/gsd-core/blob/v1.16.0/docs/COMMANDS.md).

Two upstream documentation inconsistencies matter when reproducing this install:
the installation guide still says Node 18+, whereas the versioned package requires
24+; its Codex section lists `.codex/skills`, whereas the capability manifest routes
global skills to `.agents/skills`, matching this installation. Prefer the release
manifest and capability data for these details. The Codex guide confirms the
SessionStart update hook and lack of context-warning support.
[Installation guide](https://github.com/open-gsd/gsd-core/blob/v1.16.0/docs/how-to/install-on-your-runtime.md),
[Codex capability manifest](https://github.com/open-gsd/gsd-core/blob/v1.16.0/capabilities/codex/capability.json).

Anthropic's browser skill supplies a Python Playwright workflow, a `with_server.py`
helper, and guidance to inspect rendered state before interacting. We used that
approach for the dashboard's PRD intake, controls, evidence, and replay smoke test.
The committed test mocks RPC responses, so it verifies UI behavior rather than
proving a real agent run. [Skill source](https://github.com/anthropics/skills/blob/main/skills/webapp-testing/SKILL.md),
[project test](../apps/dashboard/tests/browser_project_smoke.py).

Vercel's skill prioritizes avoiding request waterfalls and oversized bundles,
then addresses server/client fetching and unnecessary renders. It is useful during
dashboard implementation and review; it supplies guidance, not a test runner or a
correctness certificate. [Skill source](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/SKILL.md).

## Runtime integration: current limit

The running product currently uses HarnessFlow-owned phase prompts, JSON contracts,
worktree management, and completion checks. It does **not** invoke GSD commands,
load GSD role instructions, or import `.planning` phase results into its state
machine. See [agent adapter](../apps/worker/harnessflow_worker/projects/agent.py)
and [phase engine](../apps/worker/harnessflow_worker/projects/engine.py). This is
a custom prompt-and-contract adapter inspired by staged development, not full
typed GSD workflow integration.

Separately, the installed Codex skill adapters explicitly distinguish generic
subagent dispatch from typed GSD role dispatch. This session's collaboration API
has no `agent_type` field, so injected role prompts would still be a generic-agent
workaround. Do not claim GSD's typed-agent guarantees from those calls. Local
primary evidence: `~/.agents/skills/gsd-autonomous/SKILL.md`, section C.

A future integration should map a pinned GSD plan's requirements, tasks, and
verification artifacts into HarnessFlow's validated contracts and record the GSD
version and role used. Temporal persistence, budgets, cancellation, worktree
ownership, and command-result verification should remain authoritative. This is
an architectural recommendation, not implemented functionality. No further skill
installation is needed for the current milestone.
