# EKS via the community module. One managed node group on t3.medium — enough
# to run the HarnessFlow services + a bundled Temporal for the demo, sized for
# the <$10/day target (see COST.md).
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.24"

  cluster_name    = local.name
  cluster_version = var.kubernetes_version

  # Public endpoint so `kubectl`/`helm` work from a laptop during the demo.
  # A production env would make this private + reach it through a bastion/VPN.
  cluster_endpoint_public_access = true

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # IRSA: the module provisions the OIDC provider we attach pod roles to
  # (see iam.tf).
  enable_irsa = true

  # Grant the apply-er admin on the cluster so day-one kubectl works.
  enable_cluster_creator_admin_permissions = true

  eks_managed_node_groups = {
    default = {
      instance_types = [var.node_instance_type]
      capacity_type  = "ON_DEMAND"

      desired_size = var.node_desired_size
      min_size     = var.node_min_size
      max_size     = var.node_max_size

      # Room for image layers + ephemeral workflow data.
      disk_size = 30
    }
  }

  # Core add-ons. Pinned-by-module default versions; the demo doesn't override.
  cluster_addons = {
    coredns    = {}
    kube-proxy = {}
    vpc-cni    = {}
    aws-ebs-csi-driver = {
      # Lets PVCs (e.g. the chart's bundled Postgres) bind gp3 volumes.
      service_account_role_arn = module.ebs_csi_irsa.iam_role_arn
    }
  }
}

# IRSA role for the EBS CSI driver (managed add-on needs S3-like perms on EBS).
module "ebs_csi_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.44"

  role_name             = "${local.name}-ebs-csi"
  attach_ebs_csi_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:ebs-csi-controller-sa"]
    }
  }
}
