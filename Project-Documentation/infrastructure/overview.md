# Infrastructure — Overview

**Current cloud status:** the Helm/Terraform stack is a historical demo
template, not a deployable PRD coding service. See [cloud readiness](cloud-readiness.md)
for the repository/workspace/security gaps and the pre-apply gates. No AWS
resources were provisioned by this audit.

**Locations:** `docker-compose.yml` + `infrastructure/{otel,prometheus,grafana,postgres}/` are the daily driver. `infrastructure/helm/harnessflow/` + `infrastructure/kind/` landed in Week 10. `infrastructure/terraform/` is Week 11.

## Local product runtime (2026-10-10)

`make dev` is the local PRD-harness entrypoint. `scripts/local-dev.py` reads
literal `.env` values, validates tools and Codex authentication, installs frozen
dependencies, starts only Compose Postgres + Temporal with a 180-second health
deadline, applies all API migrations, then owns the API, worker, and dashboard
process groups. Application startup is bounded and any child exit shuts down
the other owned applications. Ctrl-C leaves database volumes and infrastructure
available; `make down` stops containers. Logs and the launcher lock live in the
gitignored `.local/harnessflow/` directory.

The API binds `127.0.0.1:8080` (port configurable), the dashboard binds
`127.0.0.1:3001`, and all Compose published ports bind loopback. Dashboard origin
and API URL are set together by the launcher. `.env` uses no shell evaluation;
exported variables take precedence. An empty `OTEL_EXPORTER_OTLP_ENDPOINT_GRPC`
disables optional observability. The coding runtime uses Codex CLI authentication;
API provider keys only serve legacy YAML LLM workflows.

`make demo` uses the same launcher with explicit legacy mock mode, bounded API
polling, a unique workflow name, and owned cleanup. `make test`, `make lint`,
`make typecheck`, and `make build` execute real checks. `.github/workflows/ci.yml`
runs them on pushes/PRs and checks generated proto/schema/sqlc drift. Launcher
tests cover literal config handling, process ownership, and bounded waits.

The full `make up` infrastructure stack remains optional. Redis, the firehose,
MinIO, Grafana, Jaeger, and Prometheus are not prerequisites for PRD coding jobs.

## Historical workflow-platform stack

Week 1 Day 3 complete — the docker-compose dev stack is up and verified. `make up` starts the core services (postgres, redis, temporal, temporal-ui, otel-collector, jaeger, prometheus, grafana, minio; Redpanda + console added in Week 11), all healthchecked. Verified: every UI returns 200, Temporal gRPC frontend reports `SERVING`, all 3 Prometheus scrape targets are `up`, Grafana datasources (Prometheus + Jaeger) are provisioned, and an OTLP test span flows app → otel-collector → Jaeger.

Config files: `infrastructure/otel/collector-config.yaml`, `infrastructure/prometheus/prometheus.yml`, `infrastructure/grafana/provisioning/{datasources,dashboards}/`. Makefile targets `up`/`down`/`logs`/`ps`/`restart`/`nuke` are live.

Application services run on the host under `make dev`; Compose owns dependencies.
Helm and Terraform describe the earlier cloud deployment experiments below.

**Responsibility:** Three deployment surfaces:
1. **Local development** — `docker-compose up`. Daily driver. Week 1.
2. **Local Kubernetes (kind)** — `helm install harnessflow ./infrastructure/helm/harnessflow`. Week 10.
3. **AWS EKS template** — static checks only; do not apply until the cloud-readiness gates are met.

## docker-compose stack

Services in `docker-compose.yml`:

| Service | Image | Port | Purpose |
| --- | --- | --- | --- |
| postgres | `postgres:16-alpine` | 5432 | App state + Temporal persistence (separate DBs) |
| temporal | `temporalio/auto-setup` | 7233, 8233 (UI) | Workflow engine |
| redis | `redis:7-alpine` | 6379 | Ephemeral pub/sub, rate limits |
| otel-collector | `otel/opentelemetry-collector-contrib` | 4317 (gRPC), 4318 (HTTP) | OTLP receiver, fanout |
| jaeger | `jaegertracing/all-in-one` | 16686 (UI) | Trace storage + UI |
| prometheus | `prom/prometheus` | 9090 | Metrics scrape + storage |
| grafana | `grafana/grafana` | 3000 | Dashboards (provisioned) |
| minio | `minio/minio` | 9000, 9001 (UI) | S3-compatible storage (+ event-firehose Parquet sink) |
| redpanda | `redpandadata/redpanda` | 19092 (Kafka), 9644 (admin) | Event-firehose substrate (ADR-0004), KRaft dev mode |
| redpanda-console | `redpandadata/console` | 8085 | Topic/message inspector UI |
| api | (local build) | 8080 | Go orchestrator |
| worker | (local build) | — | Python Temporal worker |
| dashboard | (local build) | 3001 | Next.js (port 3001 to avoid Grafana clash) |

Core state services have healthchecks. `make up` starts the full stack in the
background; `make dev` explicitly waits for its required Postgres/Temporal healthchecks.

## Event firehose (Week 11 — landed, ADR-0004)

The analytics path the PRD wanted from Kafka, built on Redpanda (single-binary
KRaft Kafka) without the operational weight. One topic,
`harnessflow.workflow.events`:

- **Producer:** the worker (`harnessflow_worker/events.py`) emits run/step
  lifecycle events, best-effort + optional. See `workers/overview.md`.
- **Consumer:** `apps/event-consumer/` (uv app) drains the topic and writes
  date-partitioned Parquet to S3 — MinIO locally
  (`s3://harnessflow-events/workflow-events/dt=YYYY-MM-DD/*.parquet`), real S3
  on EKS (Terraform-managed bucket, IRSA for credentials). At-least-once
  (write-then-commit); fixed Arrow schema so the column set is stable across
  batches.

Verified end-to-end locally: a research-assistant run emitted 6 events;
`make events-consume` drained them to one Parquet object in MinIO (6 rows,
15 columns, correct per-event fields), read back valid via pyarrow.

## Helm chart (Week 10 — landed)

`infrastructure/helm/harnessflow/`:

- `Chart.yaml` — chart metadata + the one subchart dep
  (`temporalio/temporal`). Postgres + Redis are first-party templates
  (see below), not subcharts. Jaeger / Prometheus / Grafana are
  intentionally out of scope here; they install separately (e.g. via
  `prometheus-community/kube-prometheus-stack`) so observability stays a
  cluster-wide concern, not bound to a single app's lifecycle.
- `templates/postgres.yaml` + `templates/redis.yaml` — bundled
  first-party Postgres (Deployment + Service + Secret + optional PVC) and
  Redis (Deployment + Service) on the official `postgres:16-alpine` /
  `redis:7-alpine` images, gated by `postgresql.enabled` / `redis.enabled`.
  These replaced the bitnami subcharts after the 2025 bitnami catalog
  migration pulled their public images (`helm install` 404'd on pull).
  The bundled DB serves local/demo only — production sets the flags false
  and points `externalPostgres` / `externalRedis` at managed RDS /
  ElastiCache, where bitnami's hardening would have lived anyway.
- `values.yaml` — fully commented defaults. Per-service blocks for `api`
  / `worker` / `dashboard`, plus `external{Postgres,Redis,Temporal}`
  blocks that activate when the matching subchart is toggled off.
- `templates/_helpers.tpl` — name / label / image / dependency-routing
  helpers (one place to flip bundled-vs-external hostnames).
- `templates/configmap.yaml` — shared connection config used by api +
  worker so swapping a subchart for an external instance updates both
  in one place.
- `templates/secret-llm-keys.yaml` — optional in-chart LLM-keys secret
  (set `env.keys.create=true`); production should point at an
  out-of-band Secret via `env.keys.existing`.
- `templates/api-deployment.yaml` — Deployment + Service; `/healthz` +
  `/readyz` probes; password injected via env-from on the Postgres
  secret + assembled into `DATABASE_URL` at container start.
- `templates/worker-deployment.yaml` — Deployment (no Service — it's a
  Temporal consumer). Same DATABASE_URL pattern as api.
- `templates/dashboard-deployment.yaml` — Deployment + Service + optional
  Ingress for the Next.js standalone server.
- `templates/hpa-worker.yaml` — worker HPA. CPU is the safe default;
  opting into `worker.autoscaling.queueDepth.enabled` adds a Pods
  metric on `temporal_workflow_task_queue_backlog` (requires Prometheus
  Adapter + a rule mapping the Temporal SDK metric — see the chart README).
- `templates/NOTES.txt` — post-install instructions printed by Helm.

- `templates/migrate-job.yaml` — DB schema as a **post-install /
  post-upgrade** hook Job (golang-migrate) plus a normal ConfigMap that
  renders the vendored `files/migrations/*.up.sql`. It's post-install,
  not pre-install, because the bundled Postgres is a main resource that
  doesn't exist during the pre-install phase — a pre-install hook
  deadlocks waiting for a DB (and an envFrom ConfigMap) that aren't there
  yet. A `wait-for-postgres` init container (`pg_isready`) handles the
  race so the Job doesn't burn its backoffLimit. Migrations are vendored
  via `make helm-sync-migrations` (copies of `apps/api/migrations/*`).

**kind smoke-test — passed 2026-05-28** (kind v0.31, k8s v1.35):
- All three images build (`api` 42MB distroless, `dashboard` 307MB,
  `worker` 919MB). Fixed two build bugs found here: the api Dockerfile
  now builds from the repo root (it needs `packages/sdk/gen/go` via
  go.work — the old `apps/api`-context build couldn't resolve it), and
  the dashboard Dockerfile disables pnpm 10's strict build-script check
  for the optional native deps `sharp`/`unrs-resolver`.
- Chart installs; the post-install migrate hook applies all 6 tables to
  in-cluster Postgres; the `dashboard` pod reaches `1/1 Running` and
  serves HTTP 200; the `api` logs `postgres connected` and exits only on
  the deliberately-absent Temporal.
- Re-verified 2026-05-28 after replacing the bitnami pg/redis subcharts
  with first-party templates: the **bundled path now installs
  clone-and-run** (no `external*` flags) — `hf-harnessflow-postgres` and
  `hf-harnessflow-redis` both `1/1 Running`, migrate hook creates all 6
  tables in the bundled Postgres, api logs `postgres connected`. `helm
  lint` clean; `helm template` renders.

Convenience targets in the repo `Makefile`: `helm-deps`, `helm-lint`,
`helm-template`, `kind-up`, `kind-down`, `kind-load`.

## kind cluster

`infrastructure/kind/cluster.yaml` — minimal two-node config (one
control-plane + one worker) with port mappings on 30080/30081 so the
dashboard and api are reachable on localhost without `kubectl
port-forward` once the install completes.

## Terraform (Week 11 — landed, plan-only)

`infrastructure/terraform/envs/demo/` — the AWS substrate the Helm chart
deploys onto. **`plan`-only**: validated via `terraform init` +
`terraform validate` against the real AWS provider + community modules;
nothing is applied until Week 12 (per the ROADMAP).

- `versions.tf` / `providers.tf` — version pins, AWS provider, default tags,
  AZ-slice locals. Local backend for the template; encrypted S3 state with
  lockfiles is required before apply.
- `variables.tf` — all inputs, including an EKS version in standard support
  as of 2026-10-13; historical cost assumptions need repricing.
- `vpc.tf` — `terraform-aws-modules/vpc`, 2 AZs, **single NAT** (the big cost cut).
- `eks.tf` — `terraform-aws-modules/eks`, one managed node group (t3.medium),
  `enable_irsa`, core add-ons + EBS CSI driver (so PVCs bind gp3).
- `rds.tf` — Postgres 16, db.t4g.small, single-AZ, gp3-encrypted; master
  password generated by Terraform → Secrets Manager (not a plaintext var).
- `elasticache.tf` — single-node Redis 7 (transient pub/sub; no HA needed).
- `s3.tf` — events bucket (private, SSE, 90-day lifecycle) for the firehose Parquet.
- `iam.tf` — IRSA role scoped to `harnessflow:harnessflow-event-consumer` →
  write the events bucket (no static keys in-cluster).
- `outputs.tf` — `update-kubeconfig` command, RDS/Redis endpoints, bucket,
  IRSA role ARN — fed straight into the Helm `external*` values.

The managed RDS / ElastiCache / S3 are the production stand-ins for the
chart's *bundled* Postgres / Redis / MinIO: install on EKS with
`postgresql.enabled=false redis.enabled=false` and point the `external*`
blocks at the Terraform outputs.

The historical ~$7/day estimate is not a current quote. Reprice the full
stack, including model usage, before any deployment; see
`infrastructure/terraform/COST.md`.

## Related ADRs

- [ADR-0004](../decisions/0004-skip-kafka-for-mvp.md) — why Temporal+Redis, not Kafka, for MVP

## TODO as we go

- [x] Decide whether to use Temporal Helm chart or write our own manifests — using the upstream `temporalio/temporal` chart as a dependency.
- [ ] Decide ingress: ALB on EKS, port-forward on kind, host-port on docker-compose
- [ ] Backup story for RDS — `automated_backup_retention_period = 7` is fine for a demo
- [ ] EKS node-group instance type — t3.medium is enough for the demo workload; document why
- [x] Real `kind` install + smoke-test run (Week-10 closeout) — passed 2026-05-28; see above.
- [x] Bitnami subchart images 404 (2025 catalog migration) — replaced with first-party Postgres/Redis templates; bundled path verified clone-and-run on kind 2026-05-28.
- [ ] Stand up the Temporal subchart in-cluster (or point at a managed Temporal) for a full api↔worker run on kind.
- [ ] Prometheus Adapter rule for `temporal_workflow_task_queue_backlog` so the worker HPA can scale on queue depth, not CPU
