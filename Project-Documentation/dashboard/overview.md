# Dashboard — Overview

**Location:** `apps/dashboard/` (Next.js 16, App Router, TypeScript).

**Responsibility:** UI for inspecting workflows, runs, traces, and evals. Same Connect services as the Go backend, via Connect-ES.

## Current state (2026-05-21) — Week 4 MVP shipped

Five live routes:

- `/` — landing with CTAs into Workflows and Runs.
- `/workflows` — list + inline "New workflow" YAML editor backed by `WorkflowService.CreateWorkflow`.
- `/workflows/[id]` — detail page with React Flow DAG (laid out via `dagre`), YAML viewer, and a "Run workflow" form that takes a `query` input.
- `/runs` — list of runs with 2s polling, status badges, total-cost columns.
- `/runs/[id]` — per-run step table (latency, in/out tokens, $-cost) with a deep-link to the Jaeger trace.

Stack: Next.js 16.2.6 App Router, TypeScript, Tailwind v4, `@xyflow/react` + `dagre` for the DAG, `@tanstack/react-query` for data, `@connectrpc/connect-web` + protobuf-es v2 for the RPC client. The generated TS Connect descriptors are copied into `src/gen/` by `make proto` (Turbopack disallows symlinks pointing outside the project root). Browser→API cross-origin is allowed by a permissive CORS middleware in `apps/api/internal/server/server.go`.

**Week 6 additions:**
- `/runs/[id]` shows an amber "Waiting for approval" banner + **Approve** button when a run is paused on an approval gate (calls `RunService.ApproveRun`).
- Step rows are expandable (`<details>`) into a **failure-analysis** view showing the step's error (if any), input preview (the rendered LLM prompt, with retrieved context), and output preview. Backed by the `input_preview`/`output_preview` columns added in migration 0002 and persisted by the worker's `with_persistence` wrapper.

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
| `/evals` | Eval comparison tables | Week 7 |
| `/analytics` | Cost trends, workflow scores over time | Week 9 |

## Key technical choices

- **Next.js 16 App Router** (16.2.6). Server Components for static reads where they help; everything live is client-side via TanStack Query.
- **TanStack Query** with 2s polling on in-progress runs. RSC fetch-everywhere is the wrong pattern for a real-time dashboard.
- **Connect-Web + protobuf-es v2** as the RPC client — same `.proto`-generated types as the Go server. No duplicate type definitions.
- **React Flow (`@xyflow/react`) + dagre** for DAG visualization. Auto-layout via `dagre` (not built into React Flow).
- **Tailwind v4** for styling. (No shadcn/ui yet — the surface is small enough that hand-rolled Tailwind suffices; revisit if the component count grows.)
- **No state library beyond TanStack Query** — Zustand/Redux would be overkill.

## Layout

- Top bar nav (in `src/app/layout.tsx`): HarnessFlow home, Workflows, Runs, Jaeger (link out). Evals/Analytics nav items are added when those pages land (Weeks 7/9).
- Body: route-specific content.
- Dark mode supported via Tailwind `dark:` and a top-bar toggle

## TODO as we go

- [ ] Real-time updates — polling first (week 5), upgrade to SSE/WS later only if perceptible lag
- [ ] Token/cost panel design — sparkline per model, total across run, breakdown by step
- [ ] DAG animation: pulsing for in-progress, green check for done, red x for failed. Smooth transitions, no jank.
- [ ] Settings page (post-MVP): API key rotation, dataset uploads, integration toggles
