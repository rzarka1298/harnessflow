provider "aws" {
  region = var.region

  default_tags {
    tags = merge(
      {
        Project     = "harnessflow"
        Environment = var.environment
        ManagedBy   = "terraform"
      },
      var.tags,
    )
  }
}

# Shared locals: common name + the AZ slice we spread subnets across.
data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  name = "${var.name}-${var.environment}"
  # Two AZs is enough for a demo and keeps NAT/subnet cost down.
  azs = slice(data.aws_availability_zones.available.names, 0, 2)
}
