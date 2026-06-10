# S3 bucket for the event firehose's Parquet output (ADR-0004). The
# event-consumer writes here in place of MinIO; the bucket name flows into the
# consumer's HARNESSFLOW_EVENTS_S3_BUCKET.

resource "aws_s3_bucket" "events" {
  bucket        = "${local.name}-events-${data.aws_caller_identity.current.account_id}"
  force_destroy = true # demo: allow `terraform destroy` to empty + drop it
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket_public_access_block" "events" {
  bucket                  = aws_s3_bucket.events.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "events" {
  bucket = aws_s3_bucket.events.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Expire raw event Parquet after 90 days — analytics demos don't need an
# unbounded retention bill.
resource "aws_s3_bucket_lifecycle_configuration" "events" {
  bucket = aws_s3_bucket.events.id
  rule {
    id     = "expire-raw-events"
    status = "Enabled"
    filter {
      prefix = "workflow-events/"
    }
    expiration {
      days = 90
    }
  }
}
