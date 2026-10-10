# HarnessFlow dashboard

## Getting Started

Run the API and project runner from the repository root using the local development launcher, then open the dashboard at http://localhost:3000. To start only the dashboard:

```bash
pnpm install --frozen-lockfile
pnpm dev
```

`NEXT_PUBLIC_API_BASE_URL` defaults to `http://localhost:8080`. Set it before `pnpm build` when the API is hosted elsewhere. `NEXT_PUBLIC_JAEGER_URL` configures the navigation link to traces.

## Project workflow

The home page opens Projects. Add a product brief (pasted text or a Markdown/text file), project name, and absolute local Git repository path. Use an existing repository or initialize an empty repository before creating the project. The path refers to the machine running HarnessFlow.

Project creation does not execute the agent. Start a run from the project detail page; defaults are 30 coding attempts and four hours of active time. An optional model override and pull-request delivery setting are available.

The run page displays tasks, acceptance criteria, verification evidence, events, agent attempts, artifacts, branch/worktree paths, and delivery results. Pause at a checkpoint, then resume with clarification or additional limits. Blocked and exhausted runs can also resume. Canceling keeps recorded work and evidence available. Artifacts are viewable and downloadable.

Legacy workflow, run, eval, and analytics pages remain available in the navigation.

## Verification

```bash
pnpm lint
pnpm exec tsc --noEmit --incremental false
pnpm build
```

With a development server on port 3100 and Python Playwright/Chromium installed:

```bash
python3 tests/browser_project_smoke.py --url http://localhost:3100
```

This browser check uses mocked Connect RPC responses. It covers PRD file import, project creation, run defaults, evidence/artifacts, pause/clarify/extend/resume, cancellation, blocked/exhausted recovery, delivery, narrow-screen layout, and legacy timeline replay. It complements the real API/runner integration checks; it does not invoke Codex or modify repositories.
