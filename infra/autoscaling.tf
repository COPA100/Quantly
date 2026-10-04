# autoscaling for both services, all behind enable_autoscaling.
#
# worker: scales on backlog per worker (queue depth / running workers), a
# metric the queue_depth lambda below publishes every minute. cpu is the wrong
# signal for a queue consumer: a worker with an empty queue is idle, and a
# worker with a long queue is busy, but cpu cannot say how long the line is.
# backlog per worker can, and the target comes from the capacity model
# (docs/capacity.md): jobs one worker clears inside the acceptable wait.
#
# api: request count per target and cpu, the usual pair for a stateless service.

variable "enable_autoscaling" {
  description = "scale the worker on queue backlog and the api on request count and cpu"
  type        = bool
  default     = true
}

variable "worker_min_count" {
  description = "fewest worker tasks, 0 lets an idle stack cost nothing"
  type        = number
  default     = 0
}

variable "worker_max_count" {
  description = "most worker tasks"
  type        = number
  default     = 5
}

variable "worker_backlog_target" {
  description = "queued jobs per running worker to hold, from the capacity model (per-worker jobs/s times the wait budget in seconds)"
  type        = number
  default     = 20
}

variable "api_min_count" {
  description = "fewest api tasks"
  type        = number
  default     = 1
}

variable "api_max_count" {
  description = "most api tasks"
  type        = number
  default     = 4
}

variable "api_requests_per_target" {
  description = "requests per minute per api task to hold, the alb RequestCountPerTarget target"
  type        = number
  default     = 600
}

variable "api_cpu_target" {
  description = "average api cpu utilization percent to hold"
  type        = number
  default     = 60
}

locals {
  autoscaling_namespace = "Quantly"
}

# ---- queue depth publisher ----

data "archive_file" "queue_depth" {
  count = var.enable_autoscaling ? 1 : 0

  type        = "zip"
  source_file = "${path.module}/lambda/queue_depth/handler.py"
  output_path = "${path.module}/.build/queue_depth.zip"
}

resource "aws_security_group" "queue_depth" {
  count = var.enable_autoscaling ? 1 : 0

  name        = "${local.name}-queue-depth"
  description = "queue depth lambda, outbound to redis and the aws api endpoints"
  vpc_id      = module.network.vpc_id

  tags = { Name = "${local.name}-queue-depth" }
}

resource "aws_vpc_security_group_egress_rule" "queue_depth_all" {
  count = var.enable_autoscaling ? 1 : 0

  security_group_id = aws_security_group.queue_depth[0].id
  description       = "redis and the vpc endpoints"
  cidr_ipv4         = var.vpc_cidr
  ip_protocol       = "-1"
}

resource "aws_vpc_security_group_ingress_rule" "redis_from_queue_depth" {
  count = var.enable_autoscaling ? 1 : 0

  security_group_id            = module.network.redis_security_group_id
  description                  = "redis from the queue depth lambda"
  referenced_security_group_id = aws_security_group.queue_depth[0].id
  ip_protocol                  = "tcp"
  from_port                    = 6379
  to_port                      = 6379
}

# the lambda sits in the vpc to reach redis, and there is no nat gateway, so the
# two aws apis it calls go through interface endpoints. these bill hourly per
# subnet, which is another reason the stack is torn down between demos.
resource "aws_security_group" "queue_depth_endpoints" {
  count = var.enable_autoscaling ? 1 : 0

  name        = "${local.name}-queue-depth-endpoints"
  description = "https from the queue depth lambda to the interface endpoints"
  vpc_id      = module.network.vpc_id

  tags = { Name = "${local.name}-queue-depth-endpoints" }
}

resource "aws_vpc_security_group_ingress_rule" "endpoints_from_queue_depth" {
  count = var.enable_autoscaling ? 1 : 0

  security_group_id            = aws_security_group.queue_depth_endpoints[0].id
  description                  = "https from the lambda"
  referenced_security_group_id = aws_security_group.queue_depth[0].id
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
}

resource "aws_vpc_endpoint" "queue_depth" {
  for_each = var.enable_autoscaling ? toset(["ecs", "monitoring"]) : toset([])

  vpc_id              = module.network.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.${each.key}"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.network.public_subnet_ids
  security_group_ids  = [aws_security_group.queue_depth_endpoints[0].id]
  private_dns_enabled = true

  tags = { Name = "${local.name}-${each.key}" }
}

data "aws_iam_policy_document" "queue_depth_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "queue_depth" {
  count = var.enable_autoscaling ? 1 : 0

  name               = "${local.name}-queue-depth"
  assume_role_policy = data.aws_iam_policy_document.queue_depth_assume.json
}

# logs plus the network interfaces a vpc lambda needs
resource "aws_iam_role_policy_attachment" "queue_depth_vpc" {
  count = var.enable_autoscaling ? 1 : 0

  role       = aws_iam_role.queue_depth[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "queue_depth" {
  count = var.enable_autoscaling ? 1 : 0

  name = "queue-depth"
  role = aws_iam_role.queue_depth[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadWorkerCount"
        Effect   = "Allow"
        Action   = "ecs:DescribeServices"
        Resource = "arn:aws:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:service/${aws_ecs_cluster.this.name}/${module.worker.service_name}"
      },
      {
        Sid      = "PublishBacklogMetrics"
        Effect   = "Allow"
        Action   = "cloudwatch:PutMetricData"
        Resource = "*"
        Condition = {
          StringEquals = { "cloudwatch:namespace" = local.autoscaling_namespace }
        }
      }
    ]
  })
}

resource "aws_cloudwatch_log_group" "queue_depth" {
  count = var.enable_autoscaling ? 1 : 0

  name              = "/aws/lambda/${local.name}-queue-depth"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "queue_depth" {
  count = var.enable_autoscaling ? 1 : 0

  function_name    = "${local.name}-queue-depth"
  role             = aws_iam_role.queue_depth[0].arn
  runtime          = "python3.13"
  handler          = "handler.handler"
  filename         = data.archive_file.queue_depth[0].output_path
  source_code_hash = data.archive_file.queue_depth[0].output_base64sha256
  timeout          = 20
  memory_size      = 128

  vpc_config {
    subnet_ids         = module.network.public_subnet_ids
    security_group_ids = [aws_security_group.queue_depth[0].id]
  }

  environment {
    variables = {
      REDIS_HOST       = module.redis.address
      REDIS_PORT       = tostring(module.redis.port)
      REDIS_DB         = "1" # the celery broker db, see common_environment
      QUEUE_NAME       = "celery"
      ECS_CLUSTER      = aws_ecs_cluster.this.name
      ECS_SERVICE      = module.worker.service_name
      METRIC_NAMESPACE = local.autoscaling_namespace
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.queue_depth,
    aws_iam_role_policy_attachment.queue_depth_vpc,
    aws_vpc_endpoint.queue_depth,
  ]
}

resource "aws_cloudwatch_event_rule" "queue_depth" {
  count = var.enable_autoscaling ? 1 : 0

  name                = "${local.name}-queue-depth"
  description         = "publish queue depth and backlog per worker every minute"
  schedule_expression = "rate(1 minute)"
}

resource "aws_cloudwatch_event_target" "queue_depth" {
  count = var.enable_autoscaling ? 1 : 0

  rule = aws_cloudwatch_event_rule.queue_depth[0].name
  arn  = aws_lambda_function.queue_depth[0].arn
}

resource "aws_lambda_permission" "queue_depth" {
  count = var.enable_autoscaling ? 1 : 0

  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.queue_depth[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.queue_depth[0].arn
}

# ---- worker: target tracking on backlog per worker ----

resource "aws_appautoscaling_target" "worker" {
  count = var.enable_autoscaling ? 1 : 0

  service_namespace  = "ecs"
  scalable_dimension = "ecs:service:DesiredCount"
  resource_id        = "service/${aws_ecs_cluster.this.name}/${module.worker.service_name}"
  min_capacity       = var.worker_min_count
  max_capacity       = var.worker_max_count
}

resource "aws_appautoscaling_policy" "worker_backlog" {
  count = var.enable_autoscaling ? 1 : 0

  name               = "${local.name}-worker-backlog"
  policy_type        = "TargetTrackingScaling"
  service_namespace  = aws_appautoscaling_target.worker[0].service_namespace
  scalable_dimension = aws_appautoscaling_target.worker[0].scalable_dimension
  resource_id        = aws_appautoscaling_target.worker[0].resource_id

  target_tracking_scaling_policy_configuration {
    target_value = var.worker_backlog_target

    customized_metric_specification {
      metric_name = "BacklogPerWorker"
      namespace   = local.autoscaling_namespace
      statistic   = "Average"

      dimensions {
        name  = "Service"
        value = module.worker.service_name
      }
    }

    # out fast, in slow: a job that outlives its worker is retried, but a task
    # that starts and stops every minute wastes a cold start each time
    scale_out_cooldown = 60
    scale_in_cooldown  = 300
  }
}

# ---- api: target tracking on request count per target and on cpu ----

resource "aws_appautoscaling_target" "api" {
  count = var.enable_autoscaling ? 1 : 0

  service_namespace  = "ecs"
  scalable_dimension = "ecs:service:DesiredCount"
  resource_id        = "service/${aws_ecs_cluster.this.name}/${module.api.service_name}"
  min_capacity       = var.api_min_count
  max_capacity       = var.api_max_count
}

resource "aws_appautoscaling_policy" "api_requests" {
  count = var.enable_autoscaling ? 1 : 0

  name               = "${local.name}-api-requests"
  policy_type        = "TargetTrackingScaling"
  service_namespace  = aws_appautoscaling_target.api[0].service_namespace
  scalable_dimension = aws_appautoscaling_target.api[0].scalable_dimension
  resource_id        = aws_appautoscaling_target.api[0].resource_id

  target_tracking_scaling_policy_configuration {
    target_value = var.api_requests_per_target

    predefined_metric_specification {
      predefined_metric_type = "ALBRequestCountPerTarget"
      resource_label         = "${aws_lb.api.arn_suffix}/${aws_lb_target_group.api.arn_suffix}"
    }

    scale_out_cooldown = 60
    scale_in_cooldown  = 300
  }
}

resource "aws_appautoscaling_policy" "api_cpu" {
  count = var.enable_autoscaling ? 1 : 0

  name               = "${local.name}-api-cpu"
  policy_type        = "TargetTrackingScaling"
  service_namespace  = aws_appautoscaling_target.api[0].service_namespace
  scalable_dimension = aws_appautoscaling_target.api[0].scalable_dimension
  resource_id        = aws_appautoscaling_target.api[0].resource_id

  target_tracking_scaling_policy_configuration {
    target_value = var.api_cpu_target

    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }

    scale_out_cooldown = 60
    scale_in_cooldown  = 300
  }
}

output "queue_depth_function_name" {
  description = "the lambda that publishes Quantly/QueueDepth and BacklogPerWorker, null when autoscaling is off"
  value       = one(aws_lambda_function.queue_depth[*].function_name)
}
