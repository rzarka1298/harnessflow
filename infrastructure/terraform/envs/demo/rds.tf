# RDS Postgres — the production stand-in for the chart's bundled Postgres.
# Helm install on EKS sets postgresql.enabled=false and points
# externalPostgres at this instance (host from the rds_endpoint output,
# password from Secrets Manager).

resource "random_password" "db" {
  length  = 24
  special = false # avoid URL-encoding pain in the DATABASE_URL
}

# Master credentials live in Secrets Manager, not in state-as-plaintext-var.
# (They're still in state — that's inherent to Terraform — so the real
# hardening is an encrypted S3 backend, noted in the README.)
resource "aws_secretsmanager_secret" "db" {
  name = "${local.name}-db"
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db.result
    dbname   = "harnessflow"
  })
}

resource "aws_db_subnet_group" "this" {
  name       = "${local.name}-db"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "rds" {
  name        = "${local.name}-rds"
  description = "Postgres access from the EKS node security group only."
  vpc_id      = module.vpc.vpc_id

  ingress {
    description     = "Postgres from EKS nodes"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_instance" "postgres" {
  identifier     = "${local.name}-pg"
  engine         = "postgres"
  engine_version = var.postgres_version
  instance_class = var.postgres_instance_class

  allocated_storage = var.postgres_allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = "harnessflow"
  username = var.db_username
  password = random_password.db.result
  port     = 5432

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  multi_az               = false # demo: single-AZ to halve cost

  # Demo lifecycle: skip the final snapshot + allow destroy without manual
  # steps. A production env flips both.
  skip_final_snapshot = true
  deletion_protection = false

  backup_retention_period = 1
  apply_immediately       = true
}
