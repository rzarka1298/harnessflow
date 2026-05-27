# Dashboard — Overview

**Location:** `apps/dashboard/` (Next.js 16, App Router, TypeScript).

**Responsibility:** UI for inspecting workflows, runs, traces, and evals. Same Connect services as the Go backend, via Connect-ES.

## Current state (2026-05-27) — Week 7 evals page added

Seven live routes:

- `/` — landing with CTAs into Workflows and Runs.
- `/workflows` — list + inline "New workflow" YAML editor backed by `WorkflowService.CreateWorkflow`.
- `/workflows/[id]` — detail page with React Flow DAG (laid out via `dagre`), YAML viewer, and a "Run workflow" form that takes a `query` input.
- `/runs` — list of runs with 2s polling, status badges, total-cost columns.
- `/runs/[id]` — per-run step table (latency, in/out tokens, $-cost) with a deep-link to the Jaeger trace.
- `/evals` — eval-run leaderboard (overall score, per-scorer chips tinted by quality, p50/p95 latency, total cost), newest first; polls `EvalService.ListEvalRuns` every 5s.
- `/evals/[id]` — per-eval detail: stat strip (overall, p50, p95, cost), aggregate scorer chips, and a per-case table from `GetEvalRun.case_results` (each row expands to the output preview).

Stack: Next.js 16.2.6 App Router, TypeScript, Tailwind v4, `@xyflow/react` + `dagre` for the DAG, `@tanstack/react-query` for data, `@connectrpc/connect-web` + protobuf-es v2 for the RPC client. The generated TS Connect descriptors are copied into `src/gen/` by `make proto` (Turbopack disallows symlinks pointing outside the project root). Browser→API cross-origin is allowed by a permissive CORS middleware in `apps/api/internal/server/server.go`.

**Week 6 additions:**
- `/runs/[id]` shows an amber "Waiting for approval" banner + **Approve** button when a run is paused on an approval gate (calls `RunService.ApproveRun`).
- Step rows are expandable (`<details>`) into a **failure-analysis** view showing the step's error (if any), input preview (the rendered LLM prompt, with retrieved context), and output preview. Backed by the `input_preview`/`output_preview` columns added in migration 0002 and persisted by the worker's `with_persistence` wrapper.

**Week 7 additions:**
- `/evals` and `/evals/[id]` (see above) wired through a new `evalClient` in `src/lib/rpc.ts`. Same Connect-Web + protobuf-es v2 transport as `runClient`/`workflowClient`; enum/int64 wire-format handled the same way as `/runs` (numeric enum comparisons, `Number(bigint)` for int64 millisecond and cent fields). The optional two-run comparison view (`/evals?compare=<a>&<b>`) is still pending — the backend already produces it via `render_markdown(report, baseline)` in `apps/eval-runner`.

Live run-state animation on the DAG and run-replay timeline scrubbing land Week 9.

## Pages

| Path | Purpose | Built in |
| --- | --- | --- |
| `/` | Landing — health stats, recent runs, "Run demo" CTA | Week 4 |
| `/workflows` | List of workflows | Week 4 |
| `/workflows/[id]` | YAML viewer + DAG render + "Run" button | Week 4 |
| `/runs` | List of runs across workflows | Week 4 |
| `/runs/[id]` | Single run: DAG with state, step list with tokens/cost/latency, Jaeger link | Week 4–5 |
| `/runs/[id]/replay` | Run replay timeline scrubber | Week 9 |
| `/evals` | Eval-run list with overall score, scorer chips, latency/cost | Week 7 |
| `/evals/[id]` | Per-eval detail: stat strip + aggregate scores + per-case table | Week 7 |
| `/analytics` | Cost trends, workflow scores over time | Week 9 |

## Key technical choices

- **Next.js 16 App Router** (16.2.6). Server Components for static reads where they help; everything live is client-side via TanStack Query.
- **TanStack Query** with 2s polling on in-progress runs. RSC fetch-everywhere is the wrong pattern for a real-time dashboard.
- **Connect-Web + protobuf-es v2** as the RPC client — same `.proto`-generated types as the Go server. No duplicate type definitions.
- **React Flow (`@xyflow/react`) + dagre** for DAG visualization. Auto-layout via `dagre` (not built into React Flow).
- **Tailwind v4** for styling. (No shadcn/ui yet — the surface is small enough that hand-rolled Tailwind suffices; revisit if the component count grows.)
- **No state library beyond TanStack Query** — Zustand/Redux would be overkill.

## Layout

- Top bar nav (in `src/app/layout.tsx`): HarnessFlow home, Workflows, Runs, Evals, Jaeger (link out). The Analytics nav item lands in Week 9.
- Body: route-specific content.
- Dark mode supported via Tailwind `dark:` and a top-bar toggle

## TODO as we go

- [ ] Real-time updates — polling first (week 5), upgrade to SSE/WS later only if perceptible lag
- [ ] Token/cost panel design — sparkline per model, total across run, breakdown by step
- [ ] DAG animation: pulsing for in-progress, green check for done, red x for failed. Smooth transitions, no jank.
- [ ] Settings page (post-MVP): API key rotation, dataset uploads, integration toggles
