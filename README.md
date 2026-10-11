# HarnessFlow

HarnessFlow turns a PRD and a local Git repository into a durable coding run: plan the work, implement it in an isolated worktree, run acceptance checks, and repair failures within an explicit attempt and time budget. The dashboard shows progress, verification evidence, artifacts, and blockers.

This is a local, single-user tool under active development. The primary product is the PRD coding harness, built on the existing Go + Temporal + Python workflow platform. The YAML workflow platform remains a maintained foundation and demo. Coding runs use your authenticated Codex CLI; YAML workflows, evaluations, traces, and analytics remain available.

## Start locally

Prerequisites: macOS or Linux; Docker with Compose v2 supporting `up --wait`; Go matching `apps/api/go.mod`; Python 3.12+ and [uv](https://docs.astral.sh/uv/); Node 22+ and pnpm 10; Git; [golang-migrate](https://github.com/golang-migrate/migrate); and an authenticated Codex CLI (`codex login`, then `codex login status`). Docker must be running.

```bash
git clone https://github.com/rzarka1298/harnessflow
cd harnessflow
cp .env.example .env
make dev
```

Open **http://127.0.0.1:3001/projects**. Register an absolute path to a local Git repository, paste the PRD, and start a run with attempt and duration limits. For a new project, create a directory and run `git init` first; no initial commit is required. Existing repositories start from committed HEAD: uncommitted files remain untouched and are not included in the run.

### CLI

The CLI submits a PRD file directly and prints the run ID and dashboard URL:

```bash
uv tool install --editable apps/cli
make install-skills
harnessflow run ./PRD.md --repo /absolute/path/to/repository
harnessflow status <run-id>
```

PRD paths may be absolute or relative to the current directory or repository. The API must be running (for example, via `make dev`). `make install-skills` installs the checked-in Codex and Claude Code skills to your user skill directories, making them available from other workspaces. The installer never overwrites a different existing skill. In Codex, invoke `$harnessflow-project` with the PRD path; in Claude Code, use `/harnessflow-project <PRD-path>`. They route requests through this CLI rather than starting an independent coding loop.
`harnessflow status` prints a compact summary; add `--full` for the complete run snapshot.
Codex sandboxed sessions need loopback network access to reach the local API (for
example, workspace-write with `sandbox_workspace_write.network_access=true`).

`make dev` installs locked dependencies, starts only Postgres and Temporal, applies migrations, builds the API, and starts the API, worker, and dashboard. It reads `.env` as literal `NAME=value` entries; exported environment variables take precedence. Shell expansion and `export` statements are unsupported. Application logs are in `.local/harnessflow/`. The launcher refuses occupied application ports and exits if one of its applications stops unexpectedly.

Ctrl-C stops the application process groups it started. Postgres and Temporal retain state; `make down` stops that infrastructure without deleting volumes. For a faster restart with dependencies already installed, run `python3 scripts/local-dev.py --skip-install`. `make tools-check` checks tooling, free application ports, and Codex login.

## Completion and boundaries

A run is complete only when every planned task is done, frozen acceptance commands pass on the delivered commit, the worktree is clean, and an independent read-only review and judge find no material gaps. The deterministic acceptance commands remain the required gate regardless of judge provider. When `ANTHROPIC_API_KEY` is configured, the judge sends the PRD, frozen plan, actual change diff, acceptance evidence, and independent review findings to Anthropic; otherwise it uses a separate read-only Codex attempt. Treat these materials as data sent to the configured provider. Defaults are 30 coding attempts and four active hours. Exhausted limits and missing access are resumable outcomes, not success. Pause or cancel from the run page; resume with clarification or additional budget when appropriate.

Implementation happens in an isolated Git worktree, preserving the source checkout. Review the generated diff and evidence before integrating changes. Codex runs with workspace restrictions; project network access is disabled by default. Set `HARNESSFLOW_PROJECT_NETWORK=true` only when the project requires network access, such as downloading dependencies. Runtime worktrees and artifacts default to `~/.local/share/harnessflow`; `HARNESSFLOW_DATA_DIR` can select an absolute alternate location.

Optional GitHub PR publication must be selected when starting the run and requires working Git/GitHub authentication. In this local release, it is limited to a GitHub.com `origin` whose fetch and push URLs identify the same repository, with the run's saved base commit equal to that repository's current default-branch tip. A new empty repository or a run started from a different/stale commit still delivers locally; publication blocks for clarification instead of guessing a PR target. Nothing auto-merges or deploys. Use only trusted repositories and PRDs; generated checks and model review reduce risk but cannot prove arbitrary software defect-free.

The local API and dashboard bind to loopback, and Compose ports are published only on `127.0.0.1`. This release does not provide multi-user authentication or tenant isolation. Keep it local. Temporal preserves orchestration progress, but the worker and host must remain available for work to advance.

## Development checks

```bash
make setup       # frozen Python and dashboard dependencies
make test        # launcher and Go/Python unit tests
make lint        # golangci-lint, Ruff, ESLint
make typecheck   # mypy and TypeScript
make build       # API and production dashboard
make check       # all of the above
```

Linters require `golangci-lint` v2.12.2. Contract changes additionally require Buf v1.69.0 and sqlc v1.31.1: `make proto sqlc` regenerates committed bindings. CI runs the quality checks and rejects generated-code drift. Launcher lifecycle/configuration checks use `python3 -m unittest discover -s scripts/tests -v`.

CI separately runs the dashboard's Playwright browser contract checks against a
production build. Local instructions are in [dashboard README](apps/dashboard/README.md).

## Existing workflow platform

The YAML workflow platform supports LLM calls, retrieval, model fallback, approvals, eval reports, run replay, and cost analytics. Run its deterministic smoke demo without provider credentials:

```bash
make demo
```

This explicitly enables mock LLMs, seeds the research corpus, runs one uniquely named workflow, prints its result, and stops the host applications it started. It has bounded startup and completion waits. Mock mode is for legacy workflow demos, not the PRD coding runtime. Real legacy LLM calls require `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in `.env`.

For the optional full observability stack, run `make up` and set `OTEL_EXPORTER_OTLP_ENDPOINT_GRPC=localhost:4317` before `make dev`. UIs: Temporal `:8233`, Jaeger `:16686`, Grafana `:3000`, Prometheus `:9090`, MinIO `:9001`, Redpanda console `:8085`. `make eval` requires `HARNESSFLOW_WORKFLOW_ID`; `make events-consume` runs the optional event firehose consumer. Helm and Terraform remain available for infrastructure experiments; cloud deployment is not required for local use.

## Architecture and development state

The Next.js dashboard calls typed Connect services on the Go API. Temporal coordinates durable workflows; Python workers execute coding and AI activities. Postgres stores projects, runs, and workflow records. Local artifacts hold repository changes and verification output.

See [STATUS](Project-Documentation/STATUS.md), [ROADMAP](Project-Documentation/ROADMAP.md), and the [decision index](Project-Documentation/decisions/INDEX.md) for current scope and rationale. The original [Harness PRD](Harness%20PRD.md) describes the earlier workflow-platform vision.

Apache 2.0 — see [LICENSE](LICENSE).
