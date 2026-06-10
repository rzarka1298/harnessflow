# IRSA role for the event-consumer pod — write access to the events bucket,
# no static AWS keys in the cluster. The pod's ServiceAccount is annotated
# with this role ARN (eks.amazonaws.com/role-arn); the Helm chart's
# event-consumer service account wires it via values.

data "aws_iam_policy_document" "events_writer" {
  statement {
    sid       = "ListEventsBucket"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.events.arn]
  }
  statement {
    sid    = "WriteEventObjects"
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:AbortMultipartUpload",
    ]
    resources = ["${aws_s3_bucket.events.arn}/*"]
  }
}

resource "aws_iam_policy" "events_writer" {
  name   = "${local.name}-events-writer"
  policy = data.aws_iam_policy_document.events_writer.json
}

# The IRSA role itself, trust-scoped to a single namespace/service-account on
# this cluster's OIDC provider.
module "events_consumer_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.44"

  role_name = "${local.name}-events-consumer"

  role_policy_arns = {
    events_writer = aws_iam_policy.events_writer.arn
  }

  oidc_providers = {
    main = {
      provider_arn = module.eks.oidc_provider_arn
      # Namespace:ServiceAccount the consumer runs under. Matches the Helm
      # release namespace + the event-consumer SA name.
      namespace_service_accounts = ["harnessflow:harnessflow-event-consumer"]
    }
  }
}
