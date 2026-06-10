# Terraform — AWS demo environment

`envs/demo/` provisions the AWS substrate the HarnessFlow Helm chart deploys
onto: VPC, EKS, RDS Postgres, ElastiCache Redis, an S3 events bucket, and the
IRSA role the event-consumer uses to write to it. The Week-11 deliverable per
`Project-Documentation/ROADMAP.md`.

**Status: `plan`-only.** Per the ROADMAP, nothing is applied until Week 12.
The config is validated (`terraform init` + `terraform validate` pass against
the real AWS provider + community modules); a `plan`/`apply` needs AWS
credentials.

## Layout

| File | Contents |
| --- | --- |
| `versions.tf` | Terraform + provider version pins; backend note. |
| `providers.tf` | AWS provider, default tags, AZ slice locals. |
| `variables.tf` | All inputs, defaulted to the <$10/day demo sizing. |
| `vpc.tf` | `terraform-aws-modules/vpc` — 2 AZs, single NAT. |
| `eks.tf` | `terraform-aws-modules/eks` — 1 managed node group (t3.medium), IRSA enabled, core add-ons + EBS CSI. |
| `rds.tf` | Postgres 16, db.t4g.small, single-AZ; password in Secrets Manager. |
| `elasticache.tf` | Single-node Redis 7. |
| `s3.tf` | Events bucket (encrypted, private, 90-day lifecycle). |
| `iam.tf` | IRSA role for `harnessflow:harnessflow-event-consumer` → write the events bucket. |
| `outputs.tf` | kubeconfig command, RDS/Redis endpoints, bucket, role ARN. |
| `COST.md` | Daily cost estimate + which knobs cut it. |

## Usage

```bash
cd infrastructure/terraform/envs/demo
terraform init
terraform validate            # offline; no creds needed
terraform plan                # needs AWS creds
terraform apply               # Week 12 only
```

After `apply`, wire the Helm chart to the managed services using the outputs:

```bash
aws eks update-kubeconfig --region us-east-1 --name harnessflow-demo
helm install hf ../../helm/harnessflow -n harnessflow --create-namespace \
  --set postgresql.enabled=false --set redis.enabled=false \
  --set externalPostgres.host=$(terraform output -raw rds_endpoint) \
  --set externalRedis.host=$(terraform output -raw redis_endpoint) \
  ...
```

## Deliberate scoping choices

- **Local backend.** State is local for the demo. A real deployment uses an
  S3 backend + DynamoDB lock table — the right place for the secrets that
  inevitably land in state. Left as a one-block change in `versions.tf`.
- **`.terraform.lock.hcl` not committed.** Follows the repo's existing
  `.gitignore`. For a team/prod repo you'd commit it to pin provider hashes;
  `versions.tf` pins the version ranges either way.
- **Cost cuts** (single NAT, single-AZ RDS, burstable classes, public EKS
  endpoint) are catalogued in `COST.md` with their production counterparts.
- **No Temporal here.** Temporal runs in-cluster via the Helm chart's subchart
  (or a managed Temporal Cloud namespace). RDS/ElastiCache/S3 are the managed
  stand-ins for the chart's *bundled* Postgres/Redis/MinIO.
