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

**Week 9 additions:**
- `/runs/[id]/replay` — Gantt-style step timeline (each step is a bar
  positioned by its `started_at`/`ended_at`) with a scrubber + play button
  that time-travels through the run. The "focused step" panel below the
  timeline shows whichever step the cursor is currently inside, with its
  prompt/response previews and any error. Pure client-side computation
  from `RunService.GetRun(id)` — no API or schema changes were needed
  (step timestamps were already exposed on the Step proto).
- `/runs/[id]` now renders the workflow's DAG above the step table, with
  nodes colored by `StepStatus`: running pulses (Tailwind `animate-pulse`)
  with a blue tint, completed go solid green (left-stripe accent in the
  step-type color so you still see what kind of step it was), failed red,
  pending faded/dashed. Edges from a completed source to a running target
  use xyflow's `animated: true` dashed-flow style; edges from completed
  sources go solid green. The 2s polling that already drove the step
  table now also drives the DAG, so in-progress runs visibly tick.
- The page also picks up a "▶ Replay timeline" link in its header.
- Notable React-hooks tripwire: the lint rule (`react-hooks/purity`) bans
  `Date.now()` during render, so the replay page uses TanStack Query's
  `dataUpdatedAt` as its "now" reference instead. Stable per render and
  refreshes with the 2s poll on in-progress runs.
- Second tripwire: React Compiler's inferred-deps check rejects
  fine-grained `useMemo` deps like `wf.data?.workflow?.yamlSource` —
  use the broader `wf.data` reference and lean on `staleTime` to keep
  refetches cheap.

- Polish pass: shared `StateMessage` component (`LoadingState`,
  `EmptyState`, `ErrorState`, `InlineError`) under `src/components/`,
  used by every page that has a fetch. Each variant is a dashed-border
  panel with a Unicode glyph + title + body + optional CTA — kept
  hand-rolled rather than pulling in shadcn since the dashboard is
  already consistent with itself. Error states surface a `Retry` button
  that calls the failing query's `refetch()`. Empty states explain how
  to get data (e.g., `/evals` tells you to run `harnessflow-eval` or
  open a PR; `/runs` points at the in-app "Run workflow" button +
  `make demo`).
- Sticky top nav (`layout.tsx`): the header is now `sticky top-0 z-20`
  with `bg-white/85 backdrop-blur` so it stays visible on long pages
  (notably `/runs/[id]` with its DAG + steps + replay link).
- `/analytics` — cost / run-volume / eval-score trends. Three panels:
  daily LLM cost (USD bar chart), daily run volume by status (stacked
  bar: completed/failed/other), and eval overall_score over time (one
  line per workflow). Aggregation runs client-side off
  `RunService.ListRuns({pageSize: 500})` + `EvalService.ListEvalRuns({pageSize: 200})`
  — same pattern as `/runs`/`/evals`; at portfolio scale (~10–100 runs)
  this is fast and avoids adding an `AnalyticsService` RPC. The chart
  primitives are tiny hand-rolled inline-SVG components in
  `src/components/charts/` (kept the deps lean; recharts would have been
  ~150KB for two charts). `/analytics` nav link added.
- Layout: nav now reads Workflows · Runs · Evals · Analytics · Jaeger ↗.

Week 9 complete. Dark mode follows the OS preference (Tailwind `dark:`
classes are everywhere); a user-facing toggle was explicitly scoped out
for this milestone.

## Pages

| Path | Purpose | Built in |
| --- | --- | --- |
| `/` | Landing — health stats, recent runs, "Run demo" CTA | Week 4 |
| `/workflows` | List of workflows | Week 4 |
| `/workflows/[id]` | YAML viewer + DAG render + "Run" button | Week 4 |
| `/runs` | List of runs across workflows | Week 4 |
| `/runs/[id]` | Single run: DAG with state, step list with tokens/cost/latency, Jaeger link | Week 4–5 |
| `/runs/[id]/replay` | Run replay timeline: Gantt rows + scrubber + focused-step inspector | Week 9 |
| `/evals` | Eval-run list with overall score, scorer chips, latency/cost | Week 7 |
| `/evals/[id]` | Per-eval detail: stat strip + aggregate scores + per-case table | Week 7 |
| `/analytics` | Cost / run-volume / eval-score trends; client-side aggregation off `ListRuns` + `ListEvalRuns` | Week 9 |
| `/analytics` | Cost trends, workflow scores over time | Week 9 |

## Key technical choices

- **Next.js 16 App Router** (16.2.6). Server Components for static reads where they help; everything live is client-side via TanStack Query.
- **TanStack Query** with 2s polling on in-progress runs. RSC fetch-everywhere is the wrong pattern for a real-time dashboard.
- **Connect-Web + protobuf-es v2** as the RPC client — same `.proto`-generated types as the Go server. No duplicate type definitions.
- **React Flow (`@xyflow/react`) + dagre** for DAG visualization. Auto-layout via `dagre` (not built into React Flow).
- **Tailwind v4** for styling. (No shadcn/ui yet — the surface is small enough that hand-rolled Tailwind suffices; revisit if the component count grows.)
- **No state library beyond TanStack Query** — Zustand/Redux would be overkill.

## Layout

- Top bar nav (in `src/app/layout.tsx`): HarnessFlow home, Workflows, Runs, Evals, Analytics, Jaeger (link out).
- Body: route-specific content.
- Dark mode supported via Tailwind `dark:` and a top-bar toggle

## TODO as we go

- [ ] Real-time updates — polling first (week 5), upgrade to SSE/WS later only if perceptible lag
- [ ] Token/cost panel design — sparkline per model, total across run, breakdown by step
- [ ] DAG animation: pulsing for in-progress, green check for done, red x for failed. Smooth transitions, no jank.
- [ ] Settings page (post-MVP): API key rotation, dataset uploads, integration toggles
