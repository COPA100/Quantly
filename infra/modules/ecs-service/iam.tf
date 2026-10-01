# every service gets its own pair of roles, so the api and worker never share
# permissions and each can be scoped to exactly what it touches.

locals {
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Action    = "sts:AssumeRole"
        Principal = { Service = "ecs-tasks.amazonaws.com" }
      }
    ]
  })
}

# ---- execution role: used by ecs itself to start the task ----
# scoped to this service's own image repo and its own secrets, instead of the
# broad AmazonECSTaskExecutionRolePolicy managed policy.
resource "aws_iam_role" "execution" {
  name               = "${var.name}-execution"
  assume_role_policy = local.assume_role_policy
}

resource "aws_iam_role_policy" "execution" {
  name = "execution"
  role = aws_iam_role.execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          # the registry login token is account-wide, it cannot be scoped to a repo
          Sid      = "EcrLogin"
          Effect   = "Allow"
          Action   = "ecr:GetAuthorizationToken"
          Resource = "*"
        },
        {
          Sid    = "PullOwnImage"
          Effect = "Allow"
          Action = [
            "ecr:BatchCheckLayerAvailability",
            "ecr:BatchGetImage",
            "ecr:GetDownloadUrlForLayer",
          ]
          Resource = var.ecr_repository_arn
        },
      ],
      length(var.secrets) == 0 ? [] : [
        {
          Sid      = "ReadOwnSecrets"
          Effect   = "Allow"
          Action   = "ssm:GetParameters"
          Resource = values(var.secrets)
        },
      ],
    )
  })
}

# ---- task role: what the application code can do at runtime ----
resource "aws_iam_role" "task" {
  name               = "${var.name}-task"
  assume_role_policy = local.assume_role_policy
}

resource "aws_iam_role_policy" "task" {
  name   = "task"
  role   = aws_iam_role.task.id
  policy = var.task_policy_json
}
