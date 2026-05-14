# Infrastructure — Overview

**Locations:** `docker-compose.yml`, `infrastructure/helm/`, `infrastructure/terraform/`, `infrastructure/kubernetes/`.

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

## Helm chart

`infrastructure/helm/harnessflow/`:

- `Chart.yaml` declares dependencies on upstream charts (`bitnami/postgresql`, `temporalio/temporal`, `bitnami/redis`, `jaegertracing/jaeger`, `prometheus-community/kube-prometheus-stack`, `grafana/grafana`).
- `templates/` contains our own Deployments/Services: `api`, `worker`, `dashboard`, `eval-runner`.
- `values.yaml` — defaults
- `values.dev.yaml` — kind cluster overrides (small resources)
- `values.eks.yaml` — EKS overrides (autoscaling, IRSA roles, ALB ingress)
- HPA on `worker` keyed on Temporal task-queue depth via a custom Prometheus metric.

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

- [ ] Decide whether to use Temporal Helm chart or write our own manifests (probably the chart)
- [ ] Decide ingress: ALB on EKS, port-forward on kind, host-port on docker-compose
- [ ] Backup story for RDS — `automated_backup_retention_period = 7` is fine for a demo
- [ ] EKS node-group instance type — t3.medium is enough for the demo workload; document why
