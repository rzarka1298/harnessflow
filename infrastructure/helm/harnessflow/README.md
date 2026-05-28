# harnessflow chart

Helm chart that installs the three first-party HarnessFlow services
(`api`, `worker`, `dashboard`), bundles first-party Postgres + Redis for
local/demo use, and optionally pulls in the upstream Temporal subchart so
the stack is reachable end-to-end on a fresh cluster.

This is the Week-10 deliverable per `Project-Documentation/ROADMAP.md`.

## What gets installed

| Resource | Notes |
| --- | --- |
| ConfigMap | Shared connection config (Postgres host/port/db/user, Temporal host/port, OTLP endpoint). |
| Secret (optional) | Holds LLM keys when `env.keys.create=true`. |
| Deployment + Service: api | Connect HTTP on port 8080; `/healthz` + `/readyz` probes. |
| Deployment: worker | Temporal worker; no Service (it's a consumer). |
| HorizontalPodAutoscaler: worker | CPU-based; opts into `temporal_workflow_task_queue_backlog` once Prometheus Adapter is installed. |
| Deployment + Service (+ Ingress): dashboard | Next.js standalone server on port 3000. |
| Deployment + Service + Secret: postgres | Bundled first-party Postgres (`postgresql.enabled`). Skip + use `externalPostgres` for managed RDS. |
| Deployment + Service: redis | Bundled first-party Redis (`redis.enabled`). Skip + use `externalRedis` for ElastiCache. |
| Job + ConfigMap: migrate | Post-install/upgrade hook that applies the DB schema. |
| Subchart (toggleable) | `temporal` (official `temporalio/temporal` chart). |

The bundled install (temporal off) renders to 5 Deployments (api, worker,
dashboard, postgres, redis), 4 Services, 2 ConfigMaps, 1 Secret, 1 Job,
1 HPA. Turning the Temporal subchart on adds its full resource set.

## Quickstart — local kind cluster

> The bundled Postgres + Redis are first-party plain Deployments on the
> official `postgres:16-alpine` / `redis:7-alpine` images (see
> `templates/postgres.yaml`, `templates/redis.yaml`) — no subcharts, so
> `helm install` works clone-and-run. The Temporal subchart (heavy:
> Cassandra StatefulSet) is left off for the local smoke test; the
> api↔Temporal↔worker path is exercised by `make demo` on the
> docker-compose stack.

```bash
# 1. cluster + images
make kind-up          # kind create cluster --config infrastructure/kind/cluster.yaml
make kind-load        # docker build all three, kind load docker-image

# 2. install — bundled pg/redis, temporal off
helm install hf infrastructure/helm/harnessflow \
  --namespace hf --create-namespace \
  --set images.registry=harnessflow --set images.tag=dev --set images.pullPolicy=Never \
  --set temporal.enabled=false \
  --set externalTemporal.host=temporal-frontend.hf.svc.cluster.local

# 3. verify
kubectl get pods -n hf
kubectl exec -n hf deploy/hf-harnessflow-postgres -- psql -U harnessflow -d harnessflow -c '\dt'
kubectl -n hf port-forward svc/hf-harnessflow-dashboard 3000:3000 &
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3000/   # → 200
```

### Verified (2026-05-28, kind v0.31 / k8s v1.35)

- All three images build (`api` 42MB distroless, `dashboard` 307MB, `worker` 919MB).
- Chart installs **with the bundled first-party Postgres + Redis** (both
  `1/1 Running`); the post-install migrate hook applies all 6 tables to
  the bundled Postgres (`workflows`, `workflow_runs`, `workflow_steps`,
  `eval_runs`, `eval_result_cases`, `schema_migrations`).
- `dashboard` pod reaches `1/1 Running` and serves **HTTP 200**.
- `api` logs `postgres connected`, then exits only on
  `dial temporal-frontend…` — i.e. DB + config wiring are correct; the
  sole blocker is the deliberately-absent Temporal.

## Why first-party Postgres/Redis (not subcharts)

These were bitnami subcharts originally. Bitnami moved their public images
out of `docker.io/bitnami/*` in the 2025 catalog migration, so the bundled
subchart path started 404-ing on image pull. Rather than chase the
`bitnamilegacy` archive (itself being sunset), we replaced them with plain
Deployments on the official Docker Library images:

- **Durable** — library images don't get pulled out from under us.
- **Right-sized** — the bundled DB only ever serves local/demo; production
  sets `postgresql.enabled=false` / `redis.enabled=false` and points
  `externalPostgres` / `externalRedis` at managed RDS / ElastiCache, where
  bitnami's production hardening would have lived anyway.
- **Consistent** — same images as the docker-compose dev stack.

The trade-off: the bundled DB is single-replica with `emptyDir` by default
(set `postgresql.persistence.enabled=true` for a PVC). That's intentional —
production = external managed services.

## External dependencies

Set the corresponding `*.enabled` to `false` and provide an `external*`
block to point at a managed service:

```yaml
postgresql:
  enabled: false
externalPostgres:
  host: hf-prod.cluster-xxx.us-east-1.rds.amazonaws.com
  port: 5432
  database: harnessflow
  user: harnessflow
  existingSecret: hf-rds-password   # k8s Secret with key `postgres-password`
```

The chart's helpers (`_helpers.tpl`) switch the rendered hostnames at
template time, so the api + worker pods see the same env vars
regardless of which path is taken.

## HPA on Temporal queue depth

The worker HPA defaults to CPU-based autoscaling. The "right" signal for
a Temporal-worker fleet is task-queue backlog — a worker IO-bound on LLM
calls can sit at near-idle CPU while still being the bottleneck.

Enable the queue-depth metric by:

1. Install [Prometheus Adapter] in the cluster.
2. Add a rule that maps the Temporal SDK metric
   `temporal_workflow_task_queue_backlog_count` (sampled by the OTel
   collector, exported to Prometheus, see
   `Project-Documentation/infrastructure/overview.md` for the pipeline)
   to a custom metric named `temporal_workflow_task_queue_backlog` on
   the worker Deployment's Pods.
3. Set `worker.autoscaling.queueDepth.enabled=true` in `values.yaml`.

The HPA's `behavior:` block is tuned for that signal — scale up
aggressively (4 pods / 30s, 30s stabilization) and back down gently
(1 pod / 60s, 5-min stabilization) so we don't thrash on transient
bursts.

[Prometheus Adapter]: https://github.com/kubernetes-sigs/prometheus-adapter

## Files

| Path | Purpose |
| --- | --- |
| `Chart.yaml` | Chart metadata + subchart deps. |
| `values.yaml` | Defaults, fully commented. |
| `templates/_helpers.tpl` | Name / label / dependency-routing helpers. |
| `templates/configmap.yaml` | Shared env config (Postgres + Temporal hosts, OTLP endpoint). |
| `templates/secret-llm-keys.yaml` | Optional in-chart LLM-keys secret. |
| `templates/api-deployment.yaml` | api Deployment + Service. |
| `templates/worker-deployment.yaml` | worker Deployment. |
| `templates/dashboard-deployment.yaml` | dashboard Deployment + Service + optional Ingress. |
| `templates/postgres.yaml` | Bundled first-party Postgres (Deployment + Service + Secret + optional PVC). |
| `templates/redis.yaml` | Bundled first-party Redis (Deployment + Service). |
| `templates/migrate-job.yaml` | Post-install/upgrade hook Job applying the vendored migrations. |
| `templates/hpa-worker.yaml` | worker HPA (CPU + optional queue-depth). |
| `templates/NOTES.txt` | Post-install notes printed by `helm install`. |
| `files/migrations/*.up.sql` | Vendored from `apps/api/migrations` via `make helm-sync-migrations`. |
| `Chart.lock` | Committed; pins the Temporal subchart digest. |
| `charts/*.tgz` | Re-fetched via `helm dependency build`; not committed. |

## Status

- Chart renders cleanly (`helm lint`, `helm template` with both bundled
  and external dependency paths) and `kubectl --dry-run=client` accepts
  the manifests.
- **kind smoke-test passed** (2026-05-28) — images build + load, chart
  installs with bundled first-party Postgres + Redis, post-install migrate
  hook creates the schema, dashboard serves HTTP 200, api connects to
  Postgres. See "Verified" above.
- Open follow-ups: (1) stand up the Temporal subchart in-cluster for a
  full api↔worker run, or point at a managed Temporal; (2) Prometheus
  Adapter rule so the worker HPA scales on queue depth.
