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

  # Template only. Bootstrap an encrypted, versioned S3 backend with S3
  # lockfiles before applying. The local backend contains the DB password.
}
