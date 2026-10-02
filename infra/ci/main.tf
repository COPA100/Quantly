# what github actions needs before it can plan or apply the main stack: a
# bucket for the remote state and two roles it assumes through oidc, so no
# long-lived aws keys are ever stored in github. like the budget, this is its
# own small root with its own local state: it is applied once by hand and has
# to outlive every `terraform destroy` of the stack.

terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
}

# ---- remote state ----

resource "aws_s3_bucket" "state" {
  # bucket names are global, the account id keeps this one unique
  bucket = "${var.project}-tfstate-${local.account_id}"

  # losing the state while the stack is up means cleaning it up by hand
  lifecycle {
    prevent_destroy = true
  }
}

# every apply writes a new version, so a bad one can be rolled back
resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id

  versioning_configuration {
    status = "Enabled"
  }
}

# the state holds the db password and jwt secret in plain text
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket = aws_s3_bucket.state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---- github oidc ----

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

locals {
  # trust policy for a role only this repo can assume, and only from workflow
  # runs whose oidc subject matches (a branch, or any pull request)
  trust = {
    for name, subject in {
      plan   = "repo:${var.github_repository}:pull_request"
      deploy = "repo:${var.github_repository}:ref:refs/heads/${var.deploy_branch}"
    } :
    name => jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Effect    = "Allow"
          Action    = "sts:AssumeRoleWithWebIdentity"
          Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
          Condition = {
            StringEquals = {
              "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
              "token.actions.githubusercontent.com:sub" = subject
            }
          }
        }
      ]
    })
  }
}

# ---- plan role: pull requests, read only ----
# a pr can run unreviewed code, so the role it gets can look but not touch.
# plans run with -lock=false, which is why it needs no write on the state.
resource "aws_iam_role" "plan" {
  name               = "${var.project}-ci-plan"
  assume_role_policy = local.trust["plan"]
}

resource "aws_iam_role_policy_attachment" "plan_read_only" {
  role       = aws_iam_role.plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

# ---- deploy role: main only, applies the stack and pushes images ----
# broad on purpose, terraform manages nearly every service the stack uses. the
# guard is the trust policy: only a run on the deploy branch can assume it.
resource "aws_iam_role" "deploy" {
  name               = "${var.project}-ci-deploy"
  assume_role_policy = local.trust["deploy"]
}

resource "aws_iam_role_policy_attachment" "deploy_power_user" {
  role       = aws_iam_role.deploy.name
  policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}

# PowerUserAccess leaves iam out. the stack creates task and execution roles,
# so allow managing roles, but only ones under the project's name prefix.
resource "aws_iam_role_policy" "deploy_iam" {
  name = "manage-project-roles"
  role = aws_iam_role.deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ManageProjectRoles"
        Effect = "Allow"
        Action = [
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:GetRole",
          "iam:TagRole",
          "iam:UntagRole",
          "iam:UpdateAssumeRolePolicy",
          "iam:PutRolePolicy",
          "iam:GetRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:ListRolePolicies",
          "iam:ListAttachedRolePolicies",
          "iam:ListInstanceProfilesForRole",
        ]
        Resource = "arn:aws:iam::${local.account_id}:role/${var.project}-*"
      },
      {
        # hand those roles to ecs tasks and nothing else
        Sid      = "PassProjectRolesToEcs"
        Effect   = "Allow"
        Action   = "iam:PassRole"
        Resource = "arn:aws:iam::${local.account_id}:role/${var.project}-*"
        Condition = {
          StringEquals = { "iam:PassedToService" = "ecs-tasks.amazonaws.com" }
        }
      },
    ]
  })
}
