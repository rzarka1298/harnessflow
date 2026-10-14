# Cloud readiness for PRD project runs

Status (2026-10-13): **not ready to apply or expose publicly**. This is a
repository-side assessment, not an AWS deployment or a real-model acceptance
result. The primary product is the PRD-to-code runner; the older YAML workflow
platform remains a maintained foundation/demo.

## What works today

- Local API intake registers a PRD and an absolute Git repository path.
- A Temporal worker performs bounded, resumable work in a Git worktree,
  verifies acceptance commands, asks a judge, and records a delivery commit.
- The CLI/skill path can target a repository in the user's workspace.
- A keyless GitHub Actions preflight has exercised the model gateway boundary.
  Its real-model leg remains pending an environment `OPENAI_API_KEY` from the
  project owner.
- The Helm chart and Terraform template pass syntax/render validation. External
  Postgres now defaults to TLS (`sslmode=require`), while bundled local
  Postgres retains `disable`. The EKS template now defaults to a version in
  standard support as of this assessment. CI checks these contracts without
  AWS credentials.

## Gaps before a useful cloud deployment

| Gate | Current implementation | Required decision or work |
| --- | --- | --- |
| Repository locality | API canonicalizes a path on its own filesystem; the worker later opens that same path. Separate pods do not share it. | Decide whether cloud workers clone an authorized remote repository or users keep local workers connected to a hosted control plane. Design intake, authentication, delivery, and isolation accordingly. |
| Worker runtime | `apps/worker/Dockerfile` contains Python dependencies, but not the Codex CLI or Git. | Build a version-pinned, non-root coding image with Git/Codex and run a containerized end-to-end project fixture. |
| Durable workspaces | Worker writes `HARNESSFLOW_DATA_DIR` worktrees and checkpoints on local disk. Helm mounts no per-run persistent workspace. | Define per-run persistent storage or a recoverable remote Git/artifact design; verify retries across pod rescheduling. |
| Model credentials | CI uses a separate loopback gateway to keep the key out of the coding process. Helm currently injects LLM keys into the worker's environment. | Reproduce the gateway boundary and use an out-of-band secret manager; do not put real keys in Helm values. |
| Database identity | External RDS connections now require TLS encryption. | Mount a trusted RDS CA and test `verify-full` from API, worker, and migration Job before public deployment. |
| Database state | Terraform generates an RDS master password and keeps it in local state, even though it also writes Secrets Manager. | Bootstrap restricted, encrypted, versioned remote state with lockfiles; consider RDS-managed master password. |
| Cache security | Single-node ElastiCache template and chart client configuration do not establish TLS/auth. | Add client TLS/auth first, then compatible ElastiCache configuration; test pub/sub. |
| Edge and access | EKS API endpoint is public; application ingress/auth and tenant isolation are not established. | Choose single-user versus multi-user trust model, restrict cluster access, and design authenticated application entry points. |
| Cost and deploy | Old `$7/day` estimate predates the current EKS version lifecycle and lacks model usage. | Reprice, set a budget/alerts, validate a plan, then request explicit go-live approval before provisioning. |

These are separate from the pending real-model acceptance gate. Supplying the
OpenAI key later will exercise that CI path, but will not by itself make the
cloud deployment safe or functional.

## Suggested sequence

1. Finish the local real-model acceptance run once the owner supplies the
   protected environment secret; investigate any failures.
2. Confirm the cloud product shape (remote repository clones or local agents
   with a hosted control plane) and single-user/multi-user boundary.
3. Implement the chosen repository/workspace/credential architecture and run
   containerized project-run acceptance, including worker replacement.
4. Harden Terraform state, database identity, cache transport, cluster and
   application access; review current cost and obtain deployment approval.
5. Only then create AWS resources, deploy, and verify one bounded end-to-end
   run before considering broader access.

Primary-source evidence and current AWS/Helm guidance: [cloud-readiness
research](../research/cloud-readiness-primary-sources.md).
