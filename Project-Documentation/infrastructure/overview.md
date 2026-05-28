# Infrastructure — Overview

**Locations:** `docker-compose.yml` + `infrastructure/{otel,prometheus,grafana,postgres}/` are the daily driver. `infrastructure/helm/harnessflow/` + `infrastructure/kind/` landed in Week 10. `infrastructure/terraform/` is Week 11.

## Current state (2026-05-15)

Week 1 Day 3 complete — the docker-compose dev stack is up and verified. `make up` starts 9 services (postgres, redis, temporal, temporal-ui, otel-collector, jaeger, prometheus, grafana, minio), all healthchecked. Verified: every UI returns 200, Temporal gRPC frontend reports `SERVING`, all 3 Prometheus scrape targets are `up`, Grafana datasources (Prometheus + Jaeger) are provisioned, and an OTLP test span flows app → otel-collector → Jaeger.

Config files: `infrastructure/otel/collector-config.yaml`, `infrastructure/prometheus/prometheus.yml`, `infrastructure/grafana/provisioning/{datasources,dashboards}/`. Makefile targets `up`/`down`/`logs`/`ps`/`restart`/`nuke` are live.

Not yet in compose: `api`, `worker`, `dashboard` — they run on the host against this stack until wired in (api Week 2, worker Week 3, dashboard Week 4). Helm and Terraform are untouched (Weeks 10–11).

**Responsibility:** Three deployment surfaces:
1. **Local development** — `docker-compose up`. Daily driver. Week 1.
2. **Local Kubernetes (kind)** — `helm install harnessflow ./infrastructure/helm/harnessflow`. Week 10.
3. **Production AWS EKS** — `terraform apply && helm install ...`. Week 12 demo only.

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
| minio | `minio/minio` | 9000, 9001 (UI) | S3-compatible storage |
| api | (local build) | 8080 | Go orchestrator |
| worker | (local build) | — | Python Temporal worker |
| dashboard | (local build) | 3001 | Next.js (port 3001 to avoid Grafana clash) |

Healthchecks on every service. `make up` blocks until everything is healthy.

## Helm chart (Week 10 — landed)

`infrastructure/helm/harnessflow/`:

- `Chart.yaml` — chart metadata + subchart deps (`bitnami/postgresql`,
  `bitnami/redis`, `temporalio/temporal`). Jaeger / Prometheus / Grafana
  are intentionally out of scope here; they install separately (e.g. via
  `prometheus-community/kube-prometheus-stack`) so observability stays a
  cluster-wide concern, not bound to a single app's lifecycle.
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
- **Upstream snag:** the bundled bitnami `postgresql`/`redis` images 404
  (2025 bitnami catalog migration), so the smoke test installs against
  plain `postgres`/`redis` Deployments (`infrastructure/kind/dev-deps.yaml`)
  via the chart's `external*` blocks. Tracked as a follow-up — swap the
  subchart provider or vendor first-party DB manifests. `helm lint` clean;
  `helm template` renders both dependency paths; manifests pass
  `kubectl apply --dry-run=client`.

Convenience targets in the repo `Makefile`: `helm-deps`, `helm-lint`,
`helm-template`, `kind-up`, `kind-down`, `kind-load`.

## kind cluster

`infrastructure/kind/cluster.yaml` — minimal two-node config (one
control-plane + one worker) with port mappings on 30080/30081 so the
dashboard and api are reachable on localhost without `kubectl
port-forward` once the install completes.

## Terraform

`infrastructure/terraform/envs/demo/`:

- `vpc.tf` — `terraform-aws-modules/vpc/aws` module
- `eks.tf` — `terraform-aws-modules/eks/aws` module, one node group, t3.medium
- `rds.tf` — Postgres 16, db.t4g.small, gp3
- `elasticache.tf` — Redis cluster, single node
- `s3.tf` — bucket for workflow artifacts
- `iam.tf` — IRSA role for worker pod (S3 access)
- `outputs.tf` — kubeconfig output, RDS endpoint, S3 bucket name

Cost target: <$10/day when running. Document in `COST.md`.

## Related ADRs

- [ADR-0004](../decisions/0004-skip-kafka-for-mvp.md) — why Temporal+Redis, not Kafka, for MVP

## TODO as we go

- [x] Decide whether to use Temporal Helm chart or write our own manifests — using the upstream `temporalio/temporal` chart as a dependency.
- [ ] Decide ingress: ALB on EKS, port-forward on kind, host-port on docker-compose
- [ ] Backup story for RDS — `automated_backup_retention_period = 7` is fine for a demo
- [ ] EKS node-group instance type — t3.medium is enough for the demo workload; document why
- [x] Real `kind` install + smoke-test run (Week-10 closeout) — passed 2026-05-28; see above.
- [ ] Bitnami subchart images 404 (2025 catalog migration) — swap subchart provider or vendor first-party Postgres/Redis manifests so the bundled path works clone-and-run.
- [ ] Stand up the Temporal subchart in-cluster (or point at a managed Temporal) for a full api↔worker run on kind.
- [ ] Prometheus Adapter rule for `temporal_workflow_task_queue_backlog` so the worker HPA can scale on queue depth, not CPU
