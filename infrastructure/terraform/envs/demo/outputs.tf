output "region" {
  description = "AWS region."
  value       = var.region
}

output "cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS API server endpoint."
  value       = module.eks.cluster_endpoint
}

output "configure_kubectl" {
  description = "Command to write a kubeconfig context for this cluster."
  value       = "aws eks update-kubeconfig --region ${var.region} --name ${module.eks.cluster_name}"
}

output "rds_endpoint" {
  description = "RDS Postgres endpoint (host:port). Feed into externalPostgres.host."
  value       = aws_db_instance.postgres.address
}

output "db_secret_arn" {
  description = "Secrets Manager ARN holding the DB master credentials."
  value       = aws_secretsmanager_secret.db.arn
}

output "redis_endpoint" {
  description = "ElastiCache Redis primary endpoint. Feed into externalRedis.host."
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address
}

output "events_bucket" {
  description = "S3 bucket for firehose Parquet. Feed into HARNESSFLOW_EVENTS_S3_BUCKET."
  value       = aws_s3_bucket.events.bucket
}

output "events_consumer_role_arn" {
  description = "IRSA role ARN for the event-consumer service account."
  value       = module.events_consumer_irsa.iam_role_arn
}
