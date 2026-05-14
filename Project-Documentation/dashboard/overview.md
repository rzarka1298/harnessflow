# Dashboard — Overview

**Location:** `apps/dashboard/` (Next.js 15, App Router, TypeScript).

**Responsibility:** UI for inspecting workflows, runs, traces, and evals. Same Connect services as the Go backend, via Connect-ES.

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

- **Next.js 15 App Router.** Server Components for static reads where they help; everything live is client-side via TanStack Query.
- **TanStack Query** with 2s polling on in-progress runs. RSC fetch-everywhere is the wrong pattern for a real-time dashboard.
- **Connect-ES** as the RPC client — same `.proto`-generated types as the Go server. No duplicate type definitions.
- **React Flow + dagre** for DAG visualization. Auto-layout via `dagre` (not built into React Flow). Half-day budget to get layout right.
- **shadcn/ui + Tailwind**. Install only the components used; no bulk import.
- **No state library beyond TanStack Query** — Zustand/Redux would be overkill.

## Layout

- Sidebar nav: Workflows, Runs, Evals, Analytics, Docs (link out)
- Top bar: project name, environment indicator, link to GitHub repo
- Body: route-specific content
- Dark mode supported via Tailwind `dark:` and a top-bar toggle

## TODO as we go

- [ ] Real-time updates — polling first (week 5), upgrade to SSE/WS later only if perceptible lag
- [ ] Token/cost panel design — sparkline per model, total across run, breakdown by step
- [ ] DAG animation: pulsing for in-progress, green check for done, red x for failed. Smooth transitions, no jank.
- [ ] Settings page (post-MVP): API key rotation, dataset uploads, integration toggles
