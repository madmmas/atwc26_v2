variable "github_org" {
  type        = string
  description = "GitHub organization or user that owns the repository."
}

variable "github_repo" {
  type        = string
  description = "Repository name (without org)."
}

variable "role_name" {
  type        = string
  description = "IAM role name for GitHub Actions OIDC."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags applied to the IAM role."
}

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "github_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_org}/${var.github_repo}:*"]
    }
  }
}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

resource "aws_iam_role" "github_actions" {
  name               = var.role_name
  assume_role_policy = data.aws_iam_policy_document.github_assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "admin" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}

data "aws_iam_policy_document" "iam_read_access" {
  statement {
    sid    = "AllowReadOidcProvider"
    effect = "Allow"
    actions = [
      "iam:GetOpenIDConnectProvider",
    ]
    resources = [
      aws_iam_openid_connect_provider.github.arn,
    ]
  }

  statement {
    sid    = "AllowReadRoleMetadata"
    effect = "Allow"
    actions = [
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListAttachedRolePolicies",
      "iam:ListRolePolicies",
    ]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/*-github-actions",
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/*-analytics-role",
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/*-predict-role",
    ]
  }
}

resource "aws_iam_role_policy" "iam_read_access" {
  name   = "${var.role_name}-iam-read"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.iam_read_access.json
}
