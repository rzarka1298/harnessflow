# Pinned tool + provider versions. Pin majors so `terraform init` is
# reproducible; the demo env never auto-jumps a provider major.
terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
    cloudinit = {
      source  = "hashicorp/cloudinit"
      version = "~> 2.3"
    }
  }

  # Backend intentionally left local for the demo. A real deployment would use
  # an S3 backend + DynamoDB lock table; documented in the env README so the
  # omission is a choice, not an oversight.
}
