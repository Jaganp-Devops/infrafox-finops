# ---------------------------------------------------------------------------
# IAM Role for the InfraFox EC2 instance.
#
# Design principle: custom least-privilege policy, NOT the AWS-managed
# "ReadOnlyAccess" policy. ReadOnlyAccess grants read access to essentially
# every service in AWS (SES, Route53, RDS, dozens more InfraFox never
# touches). That's a bigger blast radius than this app needs, and "I scoped
# this myself" is a stronger interview answer than "I attached the AWS
# managed policy."
#
# No IAM user, no access keys anywhere. The EC2 instance assumes this role
# via an instance profile, and boto3 picks up temporary credentials
# automatically from the instance metadata service.
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "infrafox_ec2_role" {
  name               = "infrafox-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json

  tags = {
    Name = "infrafox-ec2-role"
  }
}

# ---------------------------------------------------------------------------
# Custom policy: exactly what the FinOps scan engine needs to read, nothing
# else. No Terminate*, Delete*, Stop*, Modify*, Put*, or write actions of
# any kind. This is intentionally a read-only MVP per the project spec —
# remediation actions come later, behind human approval, as a separate role.
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "infrafox_readonly" {
  statement {
    sid    = "CostExplorerRead"
    effect = "Allow"
    actions = [
      "ce:GetCostAndUsage",
      "ce:GetCostForecast",
      "ce:GetDimensionValues",
      "ce:GetTags",
    ]
    resources = ["*"] # Cost Explorer API does not support resource-level scoping
  }

  statement {
    sid    = "EC2DescribeOnly"
    effect = "Allow"
    actions = [
      "ec2:DescribeInstances",
      "ec2:DescribeVolumes",
      "ec2:DescribeSecurityGroups",
      "ec2:DescribeAddresses",
      "ec2:DescribeSnapshots",
      "ec2:DescribeTags",
      "ec2:DescribeRegions",
    ]
    resources = ["*"] # Describe* actions do not support resource-level scoping
  }

  statement {
    sid    = "CloudWatchReadOnly"
    effect = "Allow"
    actions = [
      "cloudwatch:GetMetricData",
      "cloudwatch:GetMetricStatistics",
      "cloudwatch:ListMetrics",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "TaggingReadOnly"
    effect = "Allow"
    actions = [
      "tag:GetResources",
      "tag:GetTagKeys",
      "tag:GetTagValues",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "BudgetsReadOnly"
    effect = "Allow"
    actions = [
      "budgets:ViewBudget",
      "budgets:DescribeBudgetPerformanceHistory",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "PricingReadOnly"
    effect = "Allow"
    actions = [
      "pricing:GetProducts",
      "pricing:DescribeServices",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "SSMParameterReadForSecrets"
    effect = "Allow"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
    ]
    # Scoped to only the infrafox namespace in Parameter Store — this is how
    # the DuckDNS token and any other runtime secret get to the instance
    # without ever touching source code or Terraform state.
    resources = [
      "arn:aws:ssm:${var.aws_region}:*:parameter/infrafox/*"
    ]
  }
}

resource "aws_iam_policy" "infrafox_readonly" {
  name        = "infrafox-finops-readonly"
  description = "Least-privilege read-only access for the InfraFox FinOps scan engine."
  policy      = data.aws_iam_policy_document.infrafox_readonly.json
}

resource "aws_iam_role_policy_attachment" "infrafox_readonly_attach" {
  role       = aws_iam_role.infrafox_ec2_role.name
  policy_arn = aws_iam_policy.infrafox_readonly.arn
}

# SSM Session Manager access — lets you administer the box without opening
# SSH at all if you choose to go that route later. Cheap to include now
# (free), and it's the AWS-managed policy for exactly this narrow purpose,
# so no least-privilege objection here.
resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.infrafox_ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "infrafox_ec2_profile" {
  name = "infrafox-ec2-profile"
  role = aws_iam_role.infrafox_ec2_role.name
}
