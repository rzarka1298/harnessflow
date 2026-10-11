# Codex and Claude Code skill integration research

Date: 2026-10-10
Scope: current official skill documentation and the HarnessFlow project-run interfaces in this repository. This is a compatibility assessment, not a proposed commitment to a hosted service.

## Findings

### Invocation and arguments

| Host | Explicit invocation | Passing a PRD path | Invocation control |
| --- | --- | --- | --- |
| Codex CLI | `$skill-name`, or choose from `/skills`. Codex skills can also be selected implicitly from their description. | The docs describe including the skill directly in the prompt, but do not define a skill-specific argument interpolation syntax comparable to Claude's. Design the skill to instruct the agent to accept and validate the path supplied in the invocation prompt, then pass that path as a quoted CLI argument. | Skill discovery depends on `name` and a concise, scoped `description`; implicit matching is enabled. A skill can optionally add `agents/openai.yaml` UI metadata and invocation policy. |
| Claude Code | `/skill-name [arguments]`, at the start of the message, invokes directly. A repo skill is available from `.claude/skills/<name>/SKILL.md`. | Use `$ARGUMENTS` in the skill body; Claude replaces it with the text following the command. `/harnessflow ./docs/PRD.md` therefore supplies that path. | For a side-effecting run launcher, set `disable-model-invocation: true`: users can still invoke it manually, while Claude cannot decide to launch it automatically. |

Codex scans `.agents/skills/` from the current directory through repository ancestors and also supports `~/.agents/skills`. A checked-in repository skill is therefore the most direct Codex distribution for this project; skills can also be bundled with a Codex plugin for broader distribution. [Codex skills documentation](https://learn.chatgpt.com/docs/build-skills)

Claude Code scans `.claude/skills/` in the current directory and parent directories up to the repository root, and also supports `~/.claude/skills/`. Project skills can be checked into the repo. Claude's argument placeholders are explicitly documented. [Claude Code skills documentation](https://code.claude.com/docs/en/skills)

Both hosts can discover repo-local skills, but their lookup directories and argument conventions differ. Do not assume a single checked-in `SKILL.md` location will be discovered by both. For a shared source of truth, keep the workflow docs or helper script in a neutral project directory and add thin host-specific skill wrappers under `.agents/skills/` and `.claude/skills/`. Claude plugin packaging is an additional option when installable marketplace distribution is wanted; a plugin command is namespaced as `/plugin-name:skill-name`, which differs from the simple local `/harnessflow` spelling. [Claude Code plugin overview](https://code.claude.com/docs/en/plugins)

### Current HarnessFlow interface

The current project intake/run interface is the local Go API's Connect `ProjectService`; this repository does not currently expose a `harnessflow` command-line client. The service already has the core operations an adapter needs:

- `CreateProject` takes a name, repository path, and PRD text.
- `StartRun` takes a project ID plus attempt/time limits, optional model, and PR request flag.
- `GetRun` / `ListRuns` expose run state; `ControlRun` supports `pause`, `resume`, and `cancel` plus clarification/budget additions; `GetArtifacts` returns a snapshot.
- The dashboard is the current user-facing entry point, documented at `http://127.0.0.1:3001/projects` after local services start.

These facts are visible in [`project.proto`](../../packages/sdk/proto/harnessflow/project/v1/project.proto), [`projectservice.go`](../../apps/api/internal/server/projectservice.go), and the root [`README.md`](../../README.md). The README describes the application as a local, single-user tool, with API/worker/dashboard and Postgres/Temporal running locally; this is not presently a remote SaaS endpoint that a skill on an arbitrary machine can call. A helper CLI should target this local API and report missing/unavailable local services clearly.

The current web form accepts PRD text, whereas the proposed invocation references a local PRD file. The CLI must read the file on the user's machine and submit its contents to `CreateProject`, while separately using the current workspace/repository path. This means the durable run receives a PRD snapshot; it should not assume the worker can read an arbitrary path from the invoking machine later.

## Compatibility constraints and recommendations

1. Build one small, stable CLI around `ProjectService` before writing the skills. The minimum useful flow is `harnessflow run --prd ./path/to/PRD.md [--repo .]`, returning the run ID and dashboard URL promptly, plus `status`, `resume`, and `cancel` commands. Preserve existing API limits/defaults unless callers explicitly override them.
2. Keep host wrappers thin. Codex should tell the agent to resolve the supplied PRD path relative to the current workspace, confirm the file and repository, then invoke the CLI. Claude should use `$ARGUMENTS` (and `argument-hint: [prd-path]`) and `disable-model-invocation: true` to make run creation explicitly user-triggered.
3. Quote paths and avoid shell interpolation of model-provided strings. Prefer a CLI invocation with separate argv values; validate path existence and require an explicit repository when the current directory is not a Git repository. Print the resolved PRD and repo paths before starting a run, then return rather than polling for completion.
4. A CLI invocation from an agent must not expose or copy PRD contents into a prompt unnecessarily. The CLI reads the file and passes text to the local API; the skill only conveys the path. Do not claim remote use until an authenticated remote API and workspace-transfer design exist.
5. Test separately in each host: (a) discover the local skill (`$harnessflow` / `/harnessflow`), (b) pass a path with spaces, (c) reject missing/out-of-repo paths per chosen policy, (d) start a run and verify ID/dashboard link, (e) status/resume/cancel by ID, and (f) confirm the invocation does not wait for the long-running coding process. Also test a nested workspace because both products discover repo skills by walking parent directories, with different directory names.

## Primary sources

- OpenAI, [Build skills](https://learn.chatgpt.com/docs/build-skills): skill structure, explicit and implicit invocation, repository/user skill locations, and plugin distribution.
- Anthropic, [Extend Claude with skills](https://code.claude.com/docs/en/skills): project/personal locations, direct slash invocation, argument placeholders, and invocation policy.
- Anthropic, [Plugins overview](https://code.claude.com/docs/en/plugins): plugin packaging and namespaced skill commands.
- HarnessFlow repository source: [`ProjectService proto`](../../packages/sdk/proto/harnessflow/project/v1/project.proto), [`Go service`](../../apps/api/internal/server/projectservice.go), and [`README`](../../README.md).
