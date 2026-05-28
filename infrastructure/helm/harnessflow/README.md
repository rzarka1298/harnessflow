# harnessflow chart

Helm chart that installs the three first-party HarnessFlow services
(`api`, `worker`, `dashboard`) and optionally pulls in upstream subcharts
for Postgres / Redis / Temporal so the stack is reachable end-to-end on a
fresh cluster.

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
| Subcharts (toggleable) | `postgresql`, `redis`, `temporal` from upstream maintainers. |

`helm template ... | grep '^kind:' | sort | uniq -c` against the bundled
install: 21 Services, 13 Deployments, 4 StatefulSets, 10 ConfigMaps, …
(everything beyond the three first-party Deployments comes from the
upstream subcharts).

## Quickstart — local kind cluster

> **Heads-up on the bundled DB/cache subcharts** — see "Known issue:
> Bitnami images" below. The bitnami `postgresql` / `redis` public images
> were pulled in the 2025 catalog migration, so the bundled path currently
> 404s on image pull. The smoke-test recipe below installs against plain
> `postgres` / `redis` Deployments (`infrastructure/kind/dev-deps.yaml`)
> via the chart's `external*` blocks. The Temporal subchart (heavy:
> Cassandra StatefulSet) is left off for the local smoke test; the
> api↔Temporal↔worker path is exercised by `make demo` on the
> docker-compose stack.

```bash
# 1. cluster + images
make kind-up          # kind create cluster --config infrastructure/kind/cluster.yaml
make kind-load        # docker build all three, kind load docker-image

# 2. plain pg + redis (stand-ins for the bitnami subcharts)
kubectl create namespace hf
kubectl apply -n hf -f infrastructure/kind/dev-deps.yaml
kubectl wait --for=condition=ready pod -l app=postgres -n hf --timeout=90s

# 3. install the chart against the external pg/redis
helm install hf infrastructure/helm/harnessflow \
  --namespace hf \
  --set images.registry=harnessflow --set images.tag=dev --set images.pullPolicy=Never \
  --set postgresql.enabled=false --set redis.enabled=false --set temporal.enabled=false \
  --set externalPostgres.host=postgres --set externalPostgres.existingSecret=hf-pg \
  --set externalRedis.host=redis \
  --set externalTemporal.host=temporal-frontend.hf.svc.cluster.local

# 4. verify
kubectl get pods -n hf
kubectl exec -n hf deploy/postgres -- psql -U harnessflow -d harnessflow -c '\dt'
kubectl -n hf port-forward svc/hf-harnessflow-dashboard 3000:3000 &
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3000/   # → 200
```

### Verified (2026-05-28, kind v0.31 / k8s v1.35)

- All three images build (`api` 42MB distroless, `dashboard` 307MB, `worker` 919MB).
- Chart installs; the **post-install migrate hook applies all 6 tables**
  to the in-cluster Postgres (`workflows`, `workflow_runs`,
  `workflow_steps`, `eval_runs`, `eval_result_cases`, `schema_migrations`).
- `dashboard` pod reaches `1/1 Running` and serves **HTTP 200**.
- `api` logs `postgres connected`, then exits only on
  `dial temporal-frontend…` — i.e. DB + config wiring are correct; the
  sole blocker is the deliberately-absent Temporal.

## Known issue: Bitnami images

The `postgresql` and `redis` dependencies are bitnami charts, and bitnami
moved their public images out of `docker.io/bitnami/*` during their 2025
catalog migration — so `helm install` with the bundled subcharts fails at
image pull (`docker.io/bitnami/postgresql:17.x: not found`).

Workarounds, cheapest first:
1. **External services** (what the smoke test does): set
   `postgresql.enabled=false` / `redis.enabled=false` and point the
   `externalPostgres` / `externalRedis` blocks at any reachable instance —
   managed (RDS/ElastiCache) in prod, or the plain Deployments in
   `infrastructure/kind/dev-deps.yaml` locally.
2. **Pin working images** via `--set
   postgresql.image.repository=…`/`tag=…` to a registry that still hosts
   them (e.g. the `bitnamilegacy` archive while it lasts).

Durable fix (tracked in `Project-Documentation/STATUS.md` / infra
overview TODO): swap the subchart provider, or vendor first-party
Postgres/Redis manifests so clone-and-run doesn't depend on bitnami.

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
| `templates/hpa-worker.yaml` | worker HPA (CPU + optional queue-depth). |
| `templates/NOTES.txt` | Post-install notes printed by `helm install`. |
| `Chart.lock` | Committed; pins subchart digests. |
| `charts/*.tgz` | Re-fetched via `helm dependency build`; not committed. |

## Status

- Chart renders cleanly (`helm lint`, `helm template` with both bundled
  and external dependency paths) and `kubectl --dry-run=client` accepts
  the manifests.
- **kind smoke-test passed** (2026-05-28) — images build + load, chart
  installs, post-install migrate hook creates the schema, dashboard
  serves HTTP 200, api connects to Postgres. See "Verified" above.
- Open follow-ups: (1) bundled-subchart image availability (see "Known
  issue: Bitnami images"); (2) stand up the Temporal subchart in-cluster
  for a full api↔worker run, or point at a managed Temporal; (3)
  Prometheus Adapter rule so the worker HPA scales on queue depth.
