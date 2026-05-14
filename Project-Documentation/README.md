# Project Documentation

Internal dev journal for the HarnessFlow project. This is where every non-trivial decision, subsystem design, and session-handoff context lives. It is **not** the public-facing docs — those are in `docs/`.

## How to use this folder

| File / Folder | When to touch it | Who reads it |
| --- | --- | --- |
| [`STATUS.md`](./STATUS.md) | **Every working session — at the end.** Update DONE / IN FLIGHT / NEXT. | Future Claude, future you, anyone resuming work |
| [`ROADMAP.md`](./ROADMAP.md) | Only when the 14-week plan changes (rare). | Anyone planning the next phase |
| [`decisions/`](./decisions/) | When you make a non-trivial architectural or technical choice. ADR format. | Recruiters skimming for engineering judgment; future you 6 months from now |
| `<area>/` (orchestration, workers, observability, evals, dashboard, infrastructure, research, demo) | Same PR as the code change for that area. Doc-as-you-go. | Future Claude picking up that subsystem |
| [`journal/`](./journal/) | Optional. Daily one-page notes. | Just you — for retrospection |

## Subfolder map

| Folder | Subsystem | First file written | Owner ADRs |
| --- | --- | --- | --- |
| `orchestration/` | Go API + Temporal compiler + YAML DSL | `overview.md` | 0001, 0002 |
| `workers/` | Python workers + LLMClient + retrieval | `overview.md` | 0003 |
| `observability/` | OTel collector, Jaeger, Prometheus, Grafana | `overview.md` | 0005 |
| `evals/` | Eval framework + CI gate | `overview.md` | 0006 |
| `dashboard/` | Next.js dashboard | `overview.md` | — |
| `infrastructure/` | docker-compose, Helm, Terraform | `overview.md` | 0004 |
| `research/` | Weeks 13–14 research extensions | `overview.md` | 0007, 0008 |
| `demo/` | Research-assistant demo workflow | `overview.md` | — |
| `decisions/` | All ADRs | `INDEX.md` | — |
| `journal/` | Daily notes (optional) | — | — |

## ADR format

Use MADR-lite. File name: `NNNN-kebab-slug.md`.

```markdown
# ADR-NNNN: Title
Date: YYYY-MM-DD
Status: Proposed | Accepted | Superseded by ADR-MMMM

## Context
What problem are we solving? What constraints apply?

## Decision
The decision, in one or two sentences.

## Consequences
What this enables. What this forecloses. Operational implications.

## Alternatives considered
What we looked at and rejected. One sentence each.
```

ADRs are accepted on merge to `main`. Superseded ADRs are not deleted — their status changes to `Superseded by ADR-MMMM` and the superseding ADR explains why.
