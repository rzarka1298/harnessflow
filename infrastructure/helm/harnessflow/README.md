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

```bash
# 1. spin up kind + ingress controller (Week-10 baseline)
kind create cluster --name harnessflow --config infrastructure/kind/cluster.yaml

# 2. build + load images (no registry needed for kind)
docker build -t harnessflow/api:dev      apps/api
docker build -t harnessflow/worker:dev   apps/worker
docker build -t harnessflow/dashboard:dev apps/dashboard
kind load docker-image --name harnessflow \
  harnessflow/api:dev harnessflow/worker:dev harnessflow/dashboard:dev

# 3. fetch chart deps
helm repo add bitnami  https://charts.bitnami.com/bitnami
helm repo add temporal https://go.temporal.io/helm-charts
helm dependency build infrastructure/helm/harnessflow

# 4. install
helm install hf infrastructure/helm/harnessflow \
  --namespace harnessflow --create-namespace \
  --set images.registry=harnessflow \
  --set images.tag=dev \
  --set images.pullPolicy=IfNotPresent \
  --set temporal.server.replicaCount=1 \
  --wait

# 5. smoke-test the deployment
kubectl -n harnessflow port-forward svc/hf-harnessflow-api 8080:8080 &
kubectl -n harnessflow port-forward svc/hf-harnessflow-dashboard 3000:3000 &
curl -s http://localhost:8080/readyz   # → {"status":"ready"}
open http://localhost:3000             # dashboard renders
```

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
  the resulting manifests.
- Real `kind` smoke-test is the Week-10 closing item — that exercises
  the full pull-image / migrate / start path; tracked in
  `Project-Documentation/STATUS.md`.
