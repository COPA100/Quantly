# optional collector sidecar. the app sends otlp to localhost (containers in an
# awsvpc task share a network namespace), the collector scrapes the app's
# prometheus endpoint and exports traces to x-ray and metrics to cloudwatch as
# embedded metric format log events.

variable "enable_observability" {
  description = "run an aws otel collector sidecar and grant it x-ray and cloudwatch access"
  type        = bool
  default     = false
}

variable "metrics_target" {
  description = "host:port of the app's prometheus endpoint, scraped by the collector"
  type        = string
  default     = null
}

locals {
  collector_config = {
    receivers = merge(
      { otlp = { protocols = { http = { endpoint = "0.0.0.0:4318" } } } },
      var.metrics_target == null ? {} : {
        prometheus = {
          config = {
            scrape_configs = [{
              job_name        = var.name
              scrape_interval = "30s"
              static_configs  = [{ targets = [var.metrics_target] }]
            }]
          }
        }
      },
    )
    exporters = {
      awsxray = {}
      awsemf = {
        namespace      = "Quantly"
        log_group_name = "/ecs/${var.name}/metrics"
      }
    }
    service = {
      pipelines = merge(
        { traces = { receivers = ["otlp"], exporters = ["awsxray"] } },
        var.metrics_target == null ? {} : {
          metrics = { receivers = ["prometheus"], exporters = ["awsemf"] }
        },
      )
    }
  }

  collector = var.enable_observability ? [
    {
      name      = "otel-collector"
      image     = "public.ecr.aws/aws-observability/aws-otel-collector:v0.41.1"
      essential = false
      cpu       = 0

      environment = [
        { name = "AOT_CONFIG_CONTENT", value = yamlencode(local.collector_config) },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.this.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "otel"
        }
      }
    }
  ] : []
}

# the task role is what the sidecar runs as
resource "aws_iam_role_policy" "observability" {
  count = var.enable_observability ? 1 : 0

  name = "observability"
  role = aws_iam_role.task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # x-ray has no resource-level permissions for these actions
        Sid    = "WriteTraces"
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
          "xray:GetSamplingRules",
          "xray:GetSamplingTargets",
        ]
        Resource = "*"
      },
      {
        Sid    = "WriteEmfMetrics"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:log-group:/ecs/${var.name}/metrics:*"
      },
    ]
  })
}
