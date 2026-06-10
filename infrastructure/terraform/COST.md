# Cost notes — demo environment

Target: **< $10/day** while running, and `terraform destroy` brings it to ~$0.
The demo is meant to stand up for a recording session, then be torn down.

## Rough daily estimate (us-east-1, on-demand)

| Resource | Spec | ~$/day |
| --- | --- | --- |
| EKS control plane | 1 cluster @ $0.10/hr | $2.40 |
| EC2 nodes | 2 × t3.medium @ ~$0.0416/hr | $2.00 |
| NAT gateway | 1 (single, not per-AZ) @ $0.045/hr + data | $1.10 |
| RDS Postgres | db.t4g.small single-AZ @ ~$0.032/hr | $0.80 |
| ElastiCache Redis | cache.t4g.micro @ ~$0.016/hr | $0.40 |
| EBS / gp3 | node + RDS storage | ~$0.30 |
| S3 + Secrets Manager | trivial at demo volume | ~$0.05 |
| **Total** | | **~$7/day** |

Estimates are list price and approximate; the point is the order of magnitude
and which knobs move it, not penny accuracy.

## The cost cuts (and what production would flip)

- **Single NAT gateway** (`single_nat_gateway = true`) — the biggest single
  cut. Production: one per AZ for availability.
- **2 AZs, not 3** — fewer subnets/ENIs; still multi-AZ enough for a demo.
- **RDS single-AZ** (`multi_az = false`) — halves the DB bill. Production: Multi-AZ.
- **Graviton burstable everywhere** (`t4g`/`t3`) — cheapest classes that fit.
- **`skip_final_snapshot` + `force_destroy`** — clean teardown without manual
  steps. Production: take the snapshot, protect the bucket.
- **public EKS endpoint** — no bastion cost. Production: private + VPN/bastion.

## Keeping the bill at zero

```bash
terraform destroy   # tears down everything; force_destroy/skip_final_snapshot
                    # mean no manual snapshot/bucket cleanup is needed
```

Per the ROADMAP, Week 12 is the only time this env is applied (apply Monday,
record demo, `terraform destroy` Friday).
